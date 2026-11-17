-- Narrow trusted audit writes; no new table, grants on tables or RLS changes.
create function public.shield_record_security_decision(p_actor uuid,p_event_id uuid,p_stage text,
 p_decision text,p_reason text,p_version text,p_document_id uuid default null)
returns uuid language plpgsql security invoker set search_path='' as $$
declare v_role public.shield_role; v_type text; v_decision text; v_reason text; e public.security_events;
begin
 select role into v_role from public.profiles where id=p_actor;
 if not found or v_role not in ('student','admin') then
  raise sqlstate 'PT403' using message='Registered actor required'; end if;
 if p_event_id is null or p_stage is null or p_stage not in ('input','context','output','error')
  or p_decision is null or p_decision not in ('allow','block','review')
  or p_version is distinct from 'shield-security-v1'
  or p_reason is null or p_reason not in ('no_threat_detected','instruction_override',
   'authority_spoofing','prompt_extraction','credential_exfiltration','role_spoofing',
   'encoded_instruction','classifier_attack','classifier_review','protected_credential',
   'model_unavailable','classifier_error','provider_unavailable','invalid_source_support') then
  raise sqlstate 'PT422' using message='Invalid security decision'; end if;
 if (p_decision='allow') is distinct from (p_reason='no_threat_detected')
  or (p_stage='error' and (p_decision<>'block' or p_reason not in ('model_unavailable','classifier_error','provider_unavailable')))
  or (p_stage<>'error' and p_reason in ('model_unavailable','classifier_error','provider_unavailable')) then
  raise sqlstate 'PT422' using message='Inconsistent security decision'; end if;
 if p_document_id is not null then
  -- Uploader metadata rights do not grant restricted-content audit association.
  perform 1 from public.documents d where d.id=p_document_id and d.review_status='approved'
   and d.index_status='indexed' and d.indexed_sha256=d.sha256 and d.external_processing_authorized
   and (d.visibility='public' or v_role='admin') for share;
  if not found then raise sqlstate 'PT403' using message='Document association denied'; end if;
 end if;
 v_type:=case when p_stage='error' then 'security_agent_error'
  when p_decision='allow' then 'security_agent_allowed'
  when p_stage='input' then 'prompt_injection_detected'
  when p_stage='context' then 'indirect_injection_detected'
  else 'security_agent_blocked' end;
 v_decision:=case p_decision when 'block' then 'deny' else p_decision end;
 v_reason:=p_reason||';policy='||p_version;
 insert into public.security_events(id,user_id,document_id,event_type,decision,reason)
 values(p_event_id,p_actor,p_document_id,v_type,v_decision,v_reason) on conflict(id) do nothing;
 select * into e from public.security_events where id=p_event_id;
 if not found or e.user_id is distinct from p_actor or e.document_id is distinct from p_document_id
  or e.event_type is distinct from v_type or e.decision is distinct from v_decision
  or e.reason is distinct from v_reason then
  raise sqlstate 'PT409' using message='Audit association conflict'; end if;
 return p_event_id;
end;$$;
revoke all on function public.shield_record_security_decision(uuid,uuid,text,text,text,text,uuid)
 from public,anon,authenticated;
grant execute on function public.shield_record_security_decision(uuid,uuid,text,text,text,text,uuid) to service_role;
