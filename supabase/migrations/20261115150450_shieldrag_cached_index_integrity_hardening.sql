-- Completed revisions are stable; cache hits never acquire a job. No RLS changes.
alter table public.documents add column index_revision_id uuid;

create or replace function public.shield_begin_index(p_actor uuid,p_id uuid,p_job uuid,p_sha256 text,
 p_model text,p_config_hash text,p_external_authorized boolean)
returns setof public.documents language plpgsql security invoker set search_path='' as $$
declare d public.documents;
begin
 if not exists(select 1 from public.profiles where id=p_actor and role='admin') then
  raise sqlstate 'PT403' using message='Admin required'; end if;
 select * into d from public.documents where id=p_id for update;
 if not found then raise sqlstate 'PT404' using message='Missing document'; end if;
 if d.review_status<>'approved' or d.sha256 is distinct from p_sha256 then
  raise sqlstate 'PT409' using message='Invalid state'; end if;
 if p_job is null or p_external_authorized is distinct from true
  or p_model is null or p_model !~ '^[a-zA-Z0-9._-]{1,100}$'
  or p_config_hash is null or p_config_hash !~ '^[0-9a-f]{64}$' then
  raise sqlstate 'PT422' using message='Invalid operation'; end if;
 if d.index_status='indexed' and d.indexed_sha256=d.sha256 and d.embedding_model=p_model
  and d.index_config_hash=p_config_hash and d.external_processing_authorized then
  return next d; return; end if;
 if d.index_status='processing' and d.index_started_at>clock_timestamp()-interval '10 minutes' then
  raise sqlstate 'PT409' using message='Index already processing'; end if;
 update public.documents set index_status='processing',index_operation_id=p_job,
  index_started_at=clock_timestamp(),indexed_sha256=null,embedding_model=p_model,
  index_config_hash=p_config_hash,external_processing_authorized=true where id=p_id returning * into d;
 insert into public.security_events(user_id,document_id,event_type,decision,reason)
 values(p_actor,p_id,'document_index_started','allow','Explicit external model processing authorization');
 return next d;
end;$$;

create or replace function public.shield_publish_index(p_actor uuid,p_id uuid,p_job uuid,p_verified_sha256 text,p_chunks jsonb)
returns setof public.documents language plpgsql security invoker set search_path='' as $$
declare d public.documents; c jsonb; n integer:=0; v extensions.vector(768); page integer;
begin
 if not exists(select 1 from public.profiles where id=p_actor and role='admin') then
  raise sqlstate 'PT403' using message='Admin required'; end if;
 select * into d from public.documents where id=p_id for update;
 if not found then raise sqlstate 'PT404' using message='Missing document'; end if;
 if d.review_status<>'approved' or d.index_status<>'processing' or d.index_operation_id is distinct from p_job
  or p_job is null or d.sha256 is distinct from p_verified_sha256
  or not d.external_processing_authorized
  or d.index_started_at<clock_timestamp()-interval '10 minutes' then
  raise sqlstate 'PT409' using message='Index lease or integrity conflict'; end if;
 if jsonb_typeof(p_chunks) is distinct from 'array' then
  raise sqlstate 'PT422' using message='Invalid chunks'; end if;
 if jsonb_array_length(p_chunks) not between 1 and 256 then
  raise sqlstate 'PT422' using message='Invalid chunks'; end if;
 delete from public.document_chunks where document_id=p_id;
 for c in select value from jsonb_array_elements(p_chunks) loop
  if jsonb_typeof(c->'content') is distinct from 'string' or length(btrim(c->>'content'))=0
   or octet_length(c->>'content')>1800 or (c->>'chunk_index')::integer is distinct from n
   or jsonb_typeof(c->'embedding') is distinct from 'array' then
   raise sqlstate 'PT422' using message='Invalid chunk'; end if;
  if jsonb_array_length(c->'embedding')<>768 then
   raise sqlstate 'PT422' using message='Invalid vector'; end if;
  v:=(c->'embedding')::text::extensions.vector(768);
  if abs(extensions.vector_norm(v)-1)>0.0001 then
   raise sqlstate 'PT422' using message='Invalid vector norm'; end if;
  page:=(c->>'page_number')::integer;
  if (right(d.storage_path,4)='.pdf' and (page is null or page<1 or page>1000))
   or (right(d.storage_path,4)='.txt' and page is not null) then
   raise sqlstate 'PT422' using message='Invalid provenance'; end if;
  insert into public.document_chunks(document_id,chunk_index,page_number,content,embedding)
  values(p_id,n,page,c->>'content',v);
  n:=n+1;
 end loop;
 update public.documents set index_status='indexed',indexed_sha256=p_verified_sha256,index_revision_id=p_job,
  index_operation_id=null,index_started_at=null where id=p_id returning * into d;
 insert into public.security_events(user_id,document_id,event_type,decision,reason)
 values(p_actor,p_id,'document_indexed','allow','Complete index published atomically');
 return next d;
end;$$;

create or replace function public.shield_fail_index(p_actor uuid,p_id uuid,p_job uuid)
returns setof public.documents language plpgsql security invoker set search_path='' as $$
declare d public.documents;
begin
 if not exists(select 1 from public.profiles where id=p_actor and role='admin') then
  raise sqlstate 'PT403' using message='Admin required'; end if;
 select * into d from public.documents where id=p_id for update;
 if not found then raise sqlstate 'PT404' using message='Missing document'; end if;
 if d.index_status='processing' and p_job is not null and d.index_operation_id=p_job then
  update public.documents set index_status='failed',indexed_sha256=null,index_operation_id=null,
   index_started_at=null where id=p_id returning * into d;
  insert into public.security_events(user_id,document_id,event_type,decision,reason)
  values(p_actor,p_id,'document_index_failed','deny','Index processing or integrity check failed');
 end if;
 return next d;
end;$$;

-- Confirmed cached integrity denial: retain chunks, revoke only the observed revision.
-- Reuse the trusted audit function and UUID retry protocol in the same transaction.
create function public.shield_invalidate_index(p_actor uuid,p_document_id uuid,p_revision uuid,
 p_event_id uuid,p_failure text,p_expected_sha256 text,p_storage_path text,p_observed_sha256 text default null)
returns uuid language plpgsql security invoker set search_path='' as $$
declare d public.documents;
begin
 if not exists(select 1 from public.profiles where id=p_actor and role='admin') then
  raise sqlstate 'PT403' using message='Admin required'; end if;
 select * into d from public.documents where id=p_document_id for update;
 if not found then raise sqlstate 'PT404' using message='Document not found'; end if;
 -- This validates document association, failure kind/evidence and replay identity.
 perform public.shield_record_integrity_failure(p_actor,p_document_id,p_event_id,p_failure,
  p_expected_sha256,p_storage_path,p_observed_sha256);
 if d.index_status='indexed' and d.index_revision_id is not distinct from p_revision then
  update public.documents set index_status='failed',indexed_sha256=null,
   index_operation_id=null,index_started_at=null where id=p_document_id;
 end if;
 return p_event_id;
end;$$;
revoke all on function public.shield_invalidate_index(uuid,uuid,uuid,uuid,text,text,text,text)
 from public,anon,authenticated;
grant execute on function public.shield_invalidate_index(uuid,uuid,uuid,uuid,text,text,text,text) to service_role;
