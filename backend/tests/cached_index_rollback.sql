-- Authorized SQL operator; synthetic rows only, rolled back in full.
begin;
do $test$
declare
 actor uuid:=gen_random_uuid(); student uuid:=gen_random_uuid(); doc uuid:=gen_random_uuid();
 job uuid:=gen_random_uuid(); later uuid:=gen_random_uuid(); stale uuid:=gen_random_uuid();
 event uuid:=gen_random_uuid(); chunks_before uuid[]; snapshot jsonb; d public.documents;
 vector jsonb:=to_jsonb(array_fill(1/sqrt(768.0),array[768])); good jsonb;
begin
 insert into auth.users(id,email) values(actor,actor::text||'@example.invalid'),(student,student::text||'@example.invalid');
 update public.profiles set role='admin' where id=actor;
 insert into public.documents(id,uploaded_by,original_name,storage_path,sha256,review_status)
 values(doc,actor,'synthetic.txt',gen_random_uuid()::text||'.txt',repeat('a',64),'approved');
 good:=jsonb_build_array(jsonb_build_object('chunk_index',0,'page_number',null,'content','Synthetic cached fact','embedding',vector));
 perform public.shield_begin_index(actor,doc,job,repeat('a',64),'gemini-embedding-001',repeat('b',64),true);
 perform public.shield_publish_index(actor,doc,job,repeat('a',64),good);
 if (select index_revision_id from public.documents where id=doc) is distinct from job then raise exception 'Publication revision missing'; end if;
 select to_jsonb(x) into snapshot from public.documents x where id=doc;
 select array_agg(id order by id) into chunks_before from public.document_chunks where document_id=doc;
 perform public.shield_begin_index(actor,doc,stale,repeat('a',64),'gemini-embedding-001',repeat('b',64),true);
 if (select to_jsonb(x) from public.documents x where id=doc) is distinct from snapshot then raise exception 'Cache hit mutated document'; end if;
 perform public.shield_fail_index(actor,doc,stale);
 perform public.shield_fail_index(actor,doc,job);
 if (select to_jsonb(x) from public.documents x where id=doc) is distinct from snapshot then raise exception 'Stale job changed completed index'; end if;
 -- Old Task 04 cache tokens must not make an indexed row destructively cleanable.
 update public.documents set index_operation_id=stale where id=doc;
 perform public.shield_fail_index(actor,doc,stale);
 if (select index_status from public.documents where id=doc)<>'indexed' then raise exception 'Legacy cache token changed index'; end if;
 update public.documents set index_operation_id=null where id=doc;
 perform public.shield_invalidate_index(actor,doc,job,event,'sha256_mismatch',repeat('a',64),
  (select storage_path from public.documents where id=doc),repeat('c',64));
 perform public.shield_invalidate_index(actor,doc,job,event,'sha256_mismatch',repeat('a',64),
  (select storage_path from public.documents where id=doc),repeat('c',64));
 if (select index_status from public.documents where id=doc)<>'failed' then raise exception 'Integrity failure did not revoke retrieval'; end if;
 if (select array_agg(id order by id) from public.document_chunks where document_id=doc) is distinct from chunks_before then raise exception 'Integrity denial deleted completed chunks'; end if;
 if (select count(*) from public.security_events where id=event)<>1 then raise exception 'Integrity retry duplicated audit'; end if;
 perform set_config('request.jwt.claims',json_build_object('sub',student,'role','authenticated')::text,true);
 set local role authenticated;
 if exists(select 1 from public.document_chunks where document_id=doc) then raise exception 'Student retrieved invalid index'; end if;
 reset role;
 perform set_config('request.jwt.claims',json_build_object('sub',actor,'role','authenticated')::text,true);
 set local role authenticated;
 if exists(select 1 from public.document_chunks where document_id=doc) then raise exception 'Admin retrieved invalid index'; end if;
 reset role;
 perform public.shield_begin_index(actor,doc,later,repeat('a',64),'gemini-embedding-001',repeat('b',64),true);
 perform public.shield_publish_index(actor,doc,later,repeat('a',64),good);
 select to_jsonb(x) into snapshot from public.documents x where id=doc;
 perform public.shield_fail_index(actor,doc,job);
 -- Lost/stale cached audit acknowledgements must not revoke a repaired revision.
 perform public.shield_invalidate_index(actor,doc,job,event,'sha256_mismatch',repeat('a',64),
  (select storage_path from public.documents where id=doc),repeat('c',64));
 if (select to_jsonb(x) from public.documents x where id=doc) is distinct from snapshot then raise exception 'Stale invalidation changed newer publication'; end if;
 begin
  perform public.shield_invalidate_index(student,doc,later,gen_random_uuid(),'stored_object_missing',repeat('a',64),
   (select storage_path from public.documents where id=doc),null);
  raise exception 'Student actor invalidated index';
 exception when sqlstate 'PT403' then null; end;
 -- Explicit replacement failure retains old chunks, but keeps them hidden.
 select array_agg(id order by id) into chunks_before from public.document_chunks where document_id=doc;
 perform public.shield_begin_index(actor,doc,stale,repeat('a',64),'gemini-embedding-001',repeat('d',64),true);
 perform public.shield_fail_index(actor,doc,stale);
 if (select array_agg(id order by id) from public.document_chunks where document_id=doc) is distinct from chunks_before then raise exception 'Failure deleted prior revision chunks'; end if;
 perform public.shield_begin_index(actor,doc,job,repeat('a',64),'gemini-embedding-001',repeat('d',64),true);
 perform public.shield_publish_index(actor,doc,job,repeat('a',64),good);
 -- Legacy completed revisions (new column NULL) are supported without backfill.
 update public.documents set index_revision_id=null where id=doc;
 perform public.shield_invalidate_index(actor,doc,null,gen_random_uuid(),'stored_object_missing',repeat('a',64),
  (select storage_path from public.documents where id=doc),null);
 if (select index_status from public.documents where id=doc)<>'failed' then raise exception 'Legacy revision remained visible'; end if;
end;$test$;
rollback;
