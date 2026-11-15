-- Audit integrity denials independently from the failed approval transaction.
-- Reuse security_events.id for internal retry deduplication; no new table/policy.
create function public.shield_record_integrity_failure(
    p_actor uuid, p_document_id uuid, p_event_id uuid, p_failure text,
    p_expected_sha256 text, p_storage_path text, p_observed_sha256 text default null
) returns uuid
language plpgsql security invoker set search_path = ''
as $function$
declare
    v_document public.documents%rowtype;
    v_event public.security_events%rowtype;
    v_reason text;
begin
    if not exists(select 1 from public.profiles where id=p_actor and role='admin') then
        raise sqlstate 'PT403' using message='Admin required';
    end if;
    v_reason := case p_failure
        when 'sha256_mismatch' then 'SHA-256 mismatch detected'
        when 'stored_object_missing' then 'Stored object is missing'
        when 'stored_size_exceeded' then 'Stored object exceeds size limit'
        when 'stored_hash_missing' then 'Stored SHA-256 is missing'
        when 'invalid_storage_reference' then 'Stored object reference is invalid'
    end;
    if p_event_id is null or v_reason is null then
        raise sqlstate 'PT422' using message='Invalid integrity audit operation';
    end if;
    select * into v_document from public.documents where id=p_document_id for share;
    if not found then
        raise sqlstate 'PT404' using message='Document not found';
    end if;
    if p_expected_sha256 is distinct from v_document.sha256
        or p_storage_path is distinct from v_document.storage_path then
        raise sqlstate 'PT409' using message='Document association changed';
    end if;
    if p_failure='sha256_mismatch' and (
        v_document.sha256 is null or p_observed_sha256 is null
        or p_observed_sha256 !~ '^[0-9a-f]{64}$'
        or p_observed_sha256=v_document.sha256) then
        raise sqlstate 'PT422' using message='Hash mismatch evidence required';
    end if;
    if p_failure='stored_hash_missing' and v_document.sha256 is not null then
        raise sqlstate 'PT422' using message='Missing stored hash required';
    end if;
    insert into public.security_events(id,user_id,document_id,event_type,decision,reason)
    values(p_event_id,p_actor,p_document_id,'document_integrity_failure','deny',v_reason)
    on conflict(id) do nothing;
    select * into v_event from public.security_events where id=p_event_id;
    if not found or v_event.user_id is distinct from p_actor
        or v_event.document_id is distinct from p_document_id
        or v_event.event_type <> 'document_integrity_failure'
        or v_event.decision <> 'deny' or v_event.reason is distinct from v_reason then
        raise sqlstate 'PT409' using message='Audit operation association conflict';
    end if;
    -- Never change review/index status, and never raise the HTTP 409 denial here:
    -- the audit must commit before Python rejects approval. Replays are safe even
    -- if another authorized review subsequently changes the document state.
    return p_event_id;
end;
$function$;
revoke all on function public.shield_record_integrity_failure(uuid,uuid,uuid,text,text,text,text)
    from public,anon,authenticated;
grant execute on function public.shield_record_integrity_failure(uuid,uuid,uuid,text,text,text,text)
    to service_role;
