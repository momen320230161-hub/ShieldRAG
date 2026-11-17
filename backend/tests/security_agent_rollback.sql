-- Authorized SQL operator only; all synthetic rows roll back.
begin;
do $test$
declare
 student uuid:=gen_random_uuid(); admin uuid:=gen_random_uuid(); doc uuid:=gen_random_uuid();
 event uuid:=gen_random_uuid(); actual integer;
begin
 insert into auth.users(id,email) values(student,student::text||'@example.invalid'),(admin,admin::text||'@example.invalid');
 update public.profiles set role='admin' where id=admin;
 insert into public.documents(id,uploaded_by,original_name,storage_path,sha256,visibility,review_status,index_status,
  indexed_sha256,external_processing_authorized)
 values(doc,admin,'synthetic.txt',gen_random_uuid()::text||'.txt',repeat('a',64),'restricted','approved','indexed',repeat('a',64),true);
 if has_function_privilege('anon','public.shield_record_security_decision(uuid,uuid,text,text,text,text,uuid)','execute')
  or has_function_privilege('authenticated','public.shield_record_security_decision(uuid,uuid,text,text,text,text,uuid)','execute') then
  raise exception 'User can execute audit RPC'; end if;
 perform public.shield_record_security_decision(student,event,'input','block','instruction_override','shield-security-v1',null);
 perform public.shield_record_security_decision(student,event,'input','block','instruction_override','shield-security-v1',null);
 select count(*) into actual from public.security_events where id=event and user_id=student
  and event_type='prompt_injection_detected' and decision='deny' and reason='instruction_override;policy=shield-security-v1';
 if actual<>1 then raise exception 'Audit content or deduplication failed'; end if;
 begin
  perform public.shield_record_security_decision(admin,event,'input','block','instruction_override','shield-security-v1',null);
  raise exception 'Rebound event accepted';
 exception when sqlstate 'PT409' then null; end;
 begin
  perform public.shield_record_security_decision(student,gen_random_uuid(),'context','block','classifier_attack','shield-security-v1',doc);
  raise exception 'Student associated restricted content';
 exception when sqlstate 'PT403' then null; end;
 perform public.shield_record_security_decision(admin,gen_random_uuid(),'context','block','classifier_attack','shield-security-v1',doc);
 begin
  perform public.shield_record_security_decision(student,gen_random_uuid(),'input','block','raw confidential prompt','shield-security-v1',null);
  raise exception 'Unbounded audit reason accepted';
 exception when sqlstate 'PT422' then null; end;
 begin
  perform public.shield_record_security_decision(student,gen_random_uuid(),'input','allow','classifier_attack','shield-security-v1',null);
  raise exception 'Contradictory decision accepted';
 exception when sqlstate 'PT422' then null; end;
 perform set_config('request.jwt.claims',json_build_object('sub',student,'role','authenticated')::text,true);
 set local role authenticated;
 update public.security_events set reason='forged' where id=event;
 if (select reason from public.security_events where id=event)<>'instruction_override;policy=shield-security-v1' then
  raise exception 'User modified audit'; end if;
 if exists(select 1 from public.security_events where document_id=doc and user_id=admin) then raise exception 'Cross-user audit leaked'; end if;
 reset role;
end;$test$;
rollback;
