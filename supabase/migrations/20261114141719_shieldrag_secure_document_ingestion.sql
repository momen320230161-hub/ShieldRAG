-- Trusted-backend-only write operations. User-scoped RLS remains unchanged.
create function public.shield_register_document(
    p_actor uuid, p_id uuid, p_original_name text, p_storage_path text,
    p_sha256 text, p_visibility text
) returns setof public.documents
language plpgsql security invoker set search_path = ''
as $function$
declare
    v_document public.documents%rowtype;
begin
    if not exists(select 1 from public.profiles where id=p_actor and role in ('student','admin')) then
        raise sqlstate 'PT403' using message='Registered profile required';
    end if;
    if p_id is null or p_sha256 is null or p_sha256 !~ '^[0-9a-f]{64}$'
        or p_visibility is null or p_visibility not in ('public','restricted')
        or p_original_name is null or length(p_original_name) not between 5 and 200
        or p_storage_path is null or p_storage_path not in (
            'ingestions/' || p_actor::text || '/' || p_id::text || '.pdf',
            'ingestions/' || p_actor::text || '/' || p_id::text || '.txt') then
        raise sqlstate 'PT422' using message='Invalid document registration';
    end if;
    insert into public.documents(id,uploaded_by,original_name,storage_path,sha256,
                                  visibility,review_status,index_status)
    values(p_id,p_actor,p_original_name,p_storage_path,p_sha256,
           p_visibility::public.shield_visibility,'pending','not_indexed')
    returning * into v_document;
    insert into public.security_events(user_id,document_id,event_type,decision,reason)
    values(p_actor,p_id,'document_uploaded','review','Document uploaded for review');
    return next v_document;
end;
$function$;
revoke all on function public.shield_register_document(uuid,uuid,text,text,text,text)
    from public,anon,authenticated;
grant execute on function public.shield_register_document(uuid,uuid,text,text,text,text)
    to service_role;

create function public.shield_review_document(
    p_actor uuid, p_id uuid, p_decision text, p_verified_sha256 text, p_reason text default null
) returns setof public.documents
language plpgsql security invoker set search_path = ''
as $function$
declare
    v_document public.documents%rowtype;
begin
    if not exists(select 1 from public.profiles where id=p_actor and role='admin') then
        raise sqlstate 'PT403' using message='Admin required';
    end if;
    if p_decision is null or p_decision not in ('approved','rejected') then
        raise sqlstate 'PT422' using message='Invalid review decision';
    end if;
    if p_decision='rejected' and
        (p_reason is null or length(btrim(p_reason)) not between 1 and 1000) then
        raise sqlstate 'PT422' using message='Rejection reason required';
    end if;
    -- Serialize competing reviewers. Storage I/O/hash verification happens before
    -- this short transaction; the expected hash is rechecked under the row lock.
    select * into v_document from public.documents where id=p_id for update;
    if not found then
        raise sqlstate 'PT404' using message='Document not found';
    end if;
    if v_document.review_status <> 'pending' then
        raise sqlstate 'PT409' using message='Only pending documents can be reviewed';
    end if;
    if p_decision='approved' and
        (p_verified_sha256 is null or v_document.sha256 is null
         or p_verified_sha256 <> v_document.sha256) then
        raise sqlstate 'PT409' using message='Document integrity check failed';
    end if;
    update public.documents
    set review_status=p_decision::public.shield_review_status,
        reviewed_by=p_actor, reviewed_at=clock_timestamp(), index_status='not_indexed'
    where id=p_id
    returning * into v_document;
    insert into public.security_events(user_id,document_id,event_type,decision,reason)
    values(p_actor,p_id,'document_' || p_decision,
           case when p_decision='approved' then 'allow' else 'deny' end,
           case when p_decision='approved' then 'Stored SHA-256 verified' else btrim(p_reason) end);
    return next v_document;
end;
$function$;
revoke all on function public.shield_review_document(uuid,uuid,text,text,text)
    from public,anon,authenticated;
grant execute on function public.shield_review_document(uuid,uuid,text,text,text)
    to service_role;
