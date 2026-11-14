create extension if not exists vector with schema extensions;
create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to authenticated;
create type public.shield_role as enum ('student','admin');
create type public.shield_visibility as enum ('public','restricted');
create type public.shield_review_status as enum ('pending','approved','rejected');
create type public.shield_index_status as enum ('not_indexed','processing','indexed','failed');
create table public.profiles(id uuid primary key references auth.users(id) on delete cascade,role public.shield_role not null default 'student',display_name text,created_at timestamptz not null default now());
create table public.documents(id uuid primary key default gen_random_uuid(),uploaded_by uuid not null references public.profiles(id),original_name text not null,storage_path text not null unique,sha256 text check(sha256 is null or sha256 ~ '^[0-9a-f]{64}$'),visibility public.shield_visibility not null default 'public',review_status public.shield_review_status not null default 'pending',index_status public.shield_index_status not null default 'not_indexed',reviewed_by uuid references public.profiles(id),reviewed_at timestamptz,created_at timestamptz not null default now(),constraint approved_requires_hash check(review_status <> 'approved' or sha256 is not null));
create table public.document_chunks(id uuid primary key default gen_random_uuid(),document_id uuid not null references public.documents(id) on delete cascade,chunk_index integer not null check(chunk_index>=0),page_number integer check(page_number is null or page_number>=1),content text not null,embedding extensions.vector(768) not null,created_at timestamptz not null default now(),unique(document_id,chunk_index));
create index documents_review_idx on public.documents(review_status,visibility);
create index documents_uploader_idx on public.documents(uploaded_by);
create index chunks_document_idx on public.document_chunks(document_id);
create table public.chat_sessions(id uuid primary key default gen_random_uuid(),user_id uuid not null references public.profiles(id),created_at timestamptz not null default now());
create table public.chat_messages(id uuid primary key default gen_random_uuid(),session_id uuid not null references public.chat_sessions(id) on delete cascade,role text not null check(role in ('user','assistant')),content text not null,created_at timestamptz not null default now());
create table public.security_events(id uuid primary key default gen_random_uuid(),user_id uuid references public.profiles(id),document_id uuid references public.documents(id) on delete set null,event_type text not null,decision text not null check(decision in ('allow','warn','review','deny')),reason text,created_at timestamptz not null default now());
create table public.evaluation_runs(id uuid primary key default gen_random_uuid(),started_by uuid references public.profiles(id),configuration text not null check(configuration in ('baseline','secure')),metrics jsonb not null default '{}'::jsonb,created_at timestamptz not null default now());
create function private.create_shield_profile() returns trigger language plpgsql security definer set search_path = '' as $$
begin
 insert into public.profiles(id,role) values(new.id,'student') on conflict(id) do nothing;
 return new;
end;$$;
revoke all on function private.create_shield_profile() from public,anon,authenticated;
create trigger shield_profile_on_signup after insert on auth.users for each row execute function private.create_shield_profile();
create function private.is_shield_admin() returns boolean language sql stable security definer set search_path = '' as $$
select exists(select 1 from public.profiles where id=(select auth.uid()) and role='admin');
$$;
revoke all on function private.is_shield_admin() from public,anon;
grant execute on function private.is_shield_admin() to authenticated;
alter table public.profiles enable row level security;
alter table public.documents enable row level security;
alter table public.document_chunks enable row level security;
alter table public.chat_sessions enable row level security;
alter table public.chat_messages enable row level security;
alter table public.security_events enable row level security;
alter table public.evaluation_runs enable row level security;
create policy "profile_self_or_admin_read" on public.profiles for select to authenticated using(id=(select auth.uid()) or (select private.is_shield_admin()));
create policy "documents_authorized_read" on public.documents for select to authenticated using(uploaded_by=(select auth.uid()) or (select private.is_shield_admin()) or (review_status='approved' and visibility='public'));
create policy "chunks_approved_authorized_read" on public.document_chunks for select to authenticated using(exists(select 1 from public.documents d where d.id=document_id and d.review_status='approved' and (d.visibility='public' or (select private.is_shield_admin()))));
create policy "sessions_owner_read" on public.chat_sessions for select to authenticated using(user_id=(select auth.uid()));
create policy "messages_owner_read" on public.chat_messages for select to authenticated using(exists(select 1 from public.chat_sessions s where s.id=session_id and s.user_id=(select auth.uid())));
create policy "events_owner_or_admin_read" on public.security_events for select to authenticated using(user_id=(select auth.uid()) or (select private.is_shield_admin()));
create policy "evaluations_admin_read" on public.evaluation_runs for select to authenticated using((select private.is_shield_admin()));
revoke all on public.profiles,public.documents,public.document_chunks,public.chat_sessions,public.chat_messages,public.security_events,public.evaluation_runs from anon;
grant select on public.profiles,public.documents,public.document_chunks,public.chat_sessions,public.chat_messages,public.security_events,public.evaluation_runs to authenticated;
create function public.match_shield_chunks(query_embedding extensions.vector(768),match_count integer default 5)
returns table(chunk_id uuid,document_id uuid,chunk_text text,page_number integer,similarity double precision)
language sql stable security invoker set search_path = 'extensions'
as $$
 select c.id,c.document_id,c.content,c.page_number,
 (1 - (c.embedding <=> query_embedding))::double precision
 from public.document_chunks c
 join public.documents d on d.id=c.document_id
 where d.review_status='approved' and (d.visibility='public' or (select private.is_shield_admin()))
 order by c.embedding <=> query_embedding
 limit least(greatest(match_count,1),20);
$$;
revoke all on function public.match_shield_chunks(extensions.vector,integer) from public,anon;
grant execute on function public.match_shield_chunks(extensions.vector,integer) to authenticated;
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('shieldrag-documents','shieldrag-documents',false,10485760,array['application/pdf','text/plain']) on conflict(id) do nothing;
