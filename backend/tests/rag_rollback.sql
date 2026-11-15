-- Authorized SQL operator only. Every synthetic row is rolled back.
begin;
do $test$
declare
 actor uuid:=gen_random_uuid(); student uuid:=gen_random_uuid(); doc uuid:=gen_random_uuid();
 job uuid:=gen_random_uuid(); stale uuid:=gen_random_uuid();
 vector jsonb:=to_jsonb(array_fill(1/sqrt(768.0),array[768]));
 good jsonb; bad jsonb; actual integer;
begin
 insert into auth.users(id,email) values(actor,actor::text||'@example.invalid'),(student,student::text||'@example.invalid');
 update public.profiles set role='admin' where id=actor;
 insert into public.documents(id,uploaded_by,original_name,storage_path,sha256,review_status)
 values(doc,actor,'synthetic.txt',gen_random_uuid()::text||'.txt',repeat('a',64),'approved');
 perform public.shield_begin_index(actor,doc,job,repeat('a',64),'gemini-embedding-001',repeat('b',64),true);
 begin
  perform public.shield_begin_index(actor,doc,stale,repeat('a',64),'gemini-embedding-001',repeat('b',64),true);
  raise exception 'Concurrent lease accepted';
 exception when sqlstate 'PT409' then null; end;
 good:=jsonb_build_array(jsonb_build_object('chunk_index',0,'page_number',null,'content','Synthetic atomic fact','embedding',vector));
 bad:=good||jsonb_build_array(jsonb_build_object('chunk_index',1,'page_number',null,'content','Invalid second chunk','embedding',jsonb_build_array(1)));
 begin
  perform public.shield_publish_index(actor,doc,job,repeat('a',64),bad);
  raise exception 'Malformed vector accepted';
 exception when sqlstate 'PT422' then null; end;
 if exists(select 1 from public.document_chunks where document_id=doc) then raise exception 'Partial chunks published'; end if;
 if (select index_status from public.documents where id=doc)<>'processing' then raise exception 'Partial status committed'; end if;
 perform public.shield_publish_index(actor,doc,job,repeat('a',64),good);
 perform public.shield_fail_index(actor,doc,job);
 if (select index_status from public.documents where id=doc)<>'indexed' then raise exception 'Stale failure clobbered published index'; end if;
 perform public.shield_begin_index(actor,doc,stale,repeat('a',64),'gemini-embedding-001',repeat('b',64),true);
 select count(*) into actual from public.document_chunks where document_id=doc;
 if actual<>1 then raise exception 'Cached retry duplicated chunks'; end if;
 -- Legacy/orphaned chunks must remain invisible while processing or unverified.
 update public.documents set index_status='processing',index_operation_id=job,
  index_started_at=clock_timestamp()-interval '11 minutes' where id=doc;
 perform set_config('request.jwt.claims',json_build_object('sub',student,'role','authenticated')::text,true);
 set local role authenticated;
 if exists(select 1 from public.document_chunks where document_id=doc) then raise exception 'Processing chunks leaked'; end if;
 reset role;
 perform public.shield_begin_index(actor,doc,stale,repeat('a',64),'gemini-embedding-001',repeat('b',64),true);
 perform public.shield_fail_index(actor,doc,job);
 if (select index_operation_id from public.documents where id=doc)<>stale then raise exception 'Stale failure clobbered lease'; end if;
 perform public.shield_publish_index(actor,doc,stale,repeat('a',64),good);
 perform set_config('request.jwt.claims',json_build_object('sub',student,'role','authenticated')::text,true);
 set local role authenticated;
 select count(*) into actual from public.document_chunks where document_id=doc;
 if actual<>1 then raise exception 'Published public index unavailable'; end if;
 reset role;
 update public.documents set external_processing_authorized=false where id=doc;
 set local role authenticated;
 if exists(select 1 from public.document_chunks where document_id=doc) then raise exception 'Unconsented content leaked'; end if;
 reset role;
end;$test$;
rollback;
