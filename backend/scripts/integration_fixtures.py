"""Prepare opt-in SQL fixtures for an authorized operator, never for FastAPI.

No SQL is executed here. Passwords remain in an ignored local manifest; generated
SQL contains bcrypt hashes. Auth schema layout was inspected for this project.
"""
import argparse
import json
import secrets
from pathlib import Path
from uuid import UUID, uuid4

from app.core.config import Settings


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_fixture(settings: Settings) -> dict:
    run_id = str(uuid4())
    accounts = {}
    for role in ('student', 'admin'):
        accounts[role] = {
            'id': str(uuid4()), 'role': role,
            'email': f'shieldrag-{run_id}-{role}@example.invalid',
            'password': secrets.token_urlsafe(32),
        }
    documents = []
    # Orthogonal embeddings prevent unrelated project chunks from displacing all
    # fixture positives from the RPC top 20. Tests also explicitly require them.
    axis = secrets.randbelow(768)
    embedding = [0] * 768
    embedding[axis] = 1
    for visibility in ('public', 'restricted'):
        for status in ('approved', 'pending', 'rejected'):
            documents.append({'id': str(uuid4()), 'chunk_id': str(uuid4()),
                              'visibility': visibility, 'review_status': status,
                              'storage_path': f'__shieldrag_test__/{run_id}/{uuid4()}.txt'})
    return {'version': 1, 'run_id': run_id, 'supabase_url': settings.supabase_url,
            'accounts': accounts, 'documents': documents, 'embedding': embedding}


def setup_sql(manifest: dict) -> str:
    import bcrypt  # Optional test dependency; never imported by app startup.

    statements = ['begin;']
    for account in manifest['accounts'].values():
        user_id, email = literal(account['id']), literal(account['email'])
        hashed = literal(bcrypt.hashpw(account['password'].encode(), bcrypt.gensalt()).decode())
        metadata = literal(json.dumps({'provider': 'email', 'providers': ['email'],
                                       'shieldrag_test_run': manifest['run_id']}))
        statements.append(f"""
insert into auth.users(instance_id,id,aud,role,email,encrypted_password,email_confirmed_at,
    raw_app_meta_data,raw_user_meta_data,created_at,updated_at,confirmation_token,
    recovery_token,email_change_token_new,email_change,email_change_token_current)
values('00000000-0000-0000-0000-000000000000',{user_id},'authenticated','authenticated',
    {email},{hashed},now(),{metadata}::jsonb,'{{"role":"admin"}}'::jsonb,now(),now(),'','','','','');
insert into auth.identities(id,provider_id,user_id,identity_data,provider,created_at,updated_at)
values(gen_random_uuid(),{user_id},{user_id},
    jsonb_build_object('sub',{user_id},'email',{email},'email_verified',true),'email',now(),now());
update public.profiles set role={literal(account['role'])} where id={user_id};""")
    admin_id = literal(manifest['accounts']['admin']['id'])
    vector = literal(json.dumps(manifest['embedding']))
    for document in manifest['documents']:
        statements.append(f"""
insert into public.documents(id,uploaded_by,original_name,storage_path,sha256,visibility,review_status)
values({literal(document['id'])},{admin_id},'synthetic integration fixture',
    {literal(document['storage_path'])},repeat('a',64),{literal(document['visibility'])},
    {literal(document['review_status'])});
insert into public.document_chunks(id,document_id,chunk_index,content,embedding)
values({literal(document['chunk_id'])},{literal(document['id'])},0,'synthetic fixture',
    {vector}::extensions.vector);""")
    statements.append('commit;')
    return '\n'.join(statements) + '\n'


def cleanup_sql(manifest: dict) -> str:
    # Only generated fixture IDs are eligible. Guard all relationships before any
    # deletion; unexpected data referencing an account causes the transaction to fail.
    user_ids = ','.join(literal(str(UUID(a['id']))) for a in manifest['accounts'].values())
    doc_ids = ','.join(literal(str(UUID(d['id']))) for d in manifest['documents'])
    chunk_ids = ','.join(literal(str(UUID(d['chunk_id']))) for d in manifest['documents'])
    run_id = literal(str(UUID(manifest['run_id'])))
    prefix = literal(f'__shieldrag_test__/{manifest["run_id"]}/')
    return f"""begin;
do $cleanup$
begin
    if exists(select 1 from auth.users where id in ({user_ids})
        and (raw_app_meta_data->>'shieldrag_test_run' is distinct from {run_id}
             or email not like 'shieldrag-' || {run_id} || '-%@example.invalid'))
        then raise exception 'Cleanup refused: account marker mismatch'; end if;
    if exists(select 1 from public.documents where id in ({doc_ids})
        and (uploaded_by not in ({user_ids}) or not starts_with(storage_path, {prefix})))
        then raise exception 'Cleanup refused: document marker mismatch'; end if;
    if exists(select 1 from public.documents where uploaded_by in ({user_ids}) and id not in ({doc_ids}))
        or exists(select 1 from public.document_chunks where document_id in ({doc_ids}) and id not in ({chunk_ids}))
        or exists(select 1 from public.documents where reviewed_by in ({user_ids}))
        or exists(select 1 from public.security_events where user_id in ({user_ids}) or document_id in ({doc_ids}))
        or exists(select 1 from public.chat_sessions where user_id in ({user_ids}))
        or exists(select 1 from public.evaluation_runs where started_by in ({user_ids}))
        then raise exception 'Cleanup refused: unexpected referencing data'; end if;
    delete from public.document_chunks where id in ({chunk_ids}) and document_id in ({doc_ids});
    delete from public.documents where id in ({doc_ids});
    -- Auth-owned session/identity rows and the fixture profiles cascade normally.
    delete from auth.users where id in ({user_ids})
        and raw_app_meta_data->>'shieldrag_test_run' = {run_id};
    if exists(select 1 from auth.users where id in ({user_ids}))
        or exists(select 1 from public.profiles where id in ({user_ids}))
        or exists(select 1 from public.documents where id in ({doc_ids}))
        or exists(select 1 from public.document_chunks where id in ({chunk_ids}))
        then raise exception 'Cleanup incomplete: fixture rows remain'; end if;
end;
$cleanup$;
commit;
select (select count(*) from auth.users where id in ({user_ids}))
     + (select count(*) from public.profiles where id in ({user_ids}))
     + (select count(*) from public.documents where id in ({doc_ids}))
     + (select count(*) from public.document_chunks where id in ({chunk_ids})) as remaining_fixture_rows;
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path('.integration/live'))
    args = parser.parse_args()
    directory = args.directory.resolve()
    root = (Path.cwd() / '.integration').resolve()
    if not directory.is_relative_to(root):
        raise SystemExit('Fixture output must stay under backend/.integration/')
    directory.mkdir(parents=True, exist_ok=False)
    manifest = build_fixture(Settings())
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (directory / 'setup.sql').write_text(setup_sql(manifest), encoding='utf-8')
    (directory / 'cleanup.sql').write_text(cleanup_sql(manifest), encoding='utf-8')
    print('Prepared fixture files under .integration/; no database writes performed.')
    print('Apply setup.sql with an authorized SQL connection; always apply cleanup.sql afterward.')
    return directory


if __name__ == '__main__':
    main()
