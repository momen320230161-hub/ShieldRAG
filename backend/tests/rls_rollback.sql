-- Run only with an authorized SQL connection to the inspected ShieldRAG schema.
-- All synthetic fixtures are rolled back. No existing rows are changed.
begin;
do $test$
declare
    student_id uuid := gen_random_uuid();
    admin_id uuid := gen_random_uuid();
    doc_id uuid;
    fixture_documents uuid[] := '{}';
    fixture_events uuid[] := '{}';
    event_id uuid;
    visibility_value public.shield_visibility;
    status_value public.shield_review_status;
    actual integer;
begin
    insert into auth.users(id, email) values
        (student_id, student_id::text || '@example.invalid'),
        (admin_id, admin_id::text || '@example.invalid');
    update public.profiles set role = 'admin' where id = admin_id;
    foreach visibility_value in array array['public', 'restricted']::public.shield_visibility[] loop
        foreach status_value in array array['approved', 'pending', 'rejected']::public.shield_review_status[] loop
            insert into public.documents(uploaded_by, original_name, storage_path, sha256, visibility, review_status)
            values(student_id, 'synthetic.txt', gen_random_uuid()::text, repeat('a', 64), visibility_value, status_value)
            returning id into doc_id;
            update public.documents set index_status='indexed',indexed_sha256=sha256,
                embedding_model='synthetic-fixture-model',external_processing_authorized=true where id=doc_id;
            fixture_documents := array_append(fixture_documents, doc_id);
            insert into public.document_chunks(document_id, chunk_index, content, embedding)
            values(doc_id, 0, 'synthetic', array_fill(1.0, array[768])::extensions.vector);
        end loop;
    end loop;
    insert into public.security_events(user_id, event_type, decision)
    values(student_id, 'synthetic', 'deny') returning id into event_id;
    fixture_events := array_append(fixture_events, event_id);
    insert into public.security_events(user_id, event_type, decision)
    values(admin_id, 'synthetic', 'deny') returning id into event_id;
    fixture_events := array_append(fixture_events, event_id);
    insert into public.security_events(event_type, decision)
    values('synthetic', 'deny') returning id into event_id;
    fixture_events := array_append(fixture_events, event_id);

    perform set_config('request.jwt.claims', json_build_object('sub', student_id, 'role', 'authenticated',
        'user_metadata', json_build_object('role', 'admin'))::text, true);
    set local role authenticated;
    select count(*) into actual from public.document_chunks where document_id = any(fixture_documents);
    if actual <> 1 then raise exception 'Student chunk isolation failed: %', actual; end if;
    select count(*) into actual from public.match_shield_chunks(array_fill(1.0, array[768])::extensions.vector, 20)
        where document_id = any(fixture_documents);
    -- Existing approved chunks may occupy the top 20; never allow forbidden fixture results.
    if exists(select 1 from public.match_shield_chunks(array_fill(1.0, array[768])::extensions.vector, 20) m
        join public.documents d on d.id = m.document_id
        where d.review_status <> 'approved' or d.visibility <> 'public')
        then raise exception 'Student RPC authorization failed'; end if;
    select count(*) into actual from public.security_events where id = any(fixture_events);
    if actual <> 1 then raise exception 'Student event ownership failed'; end if;
    update public.profiles set role = 'admin' where id = student_id;
    if (select role from public.profiles where id = student_id) <> 'student'
        then raise exception 'Role escalation succeeded'; end if;
    update public.documents set review_status = 'approved' where id = any(fixture_documents);
    reset role;
    select count(*) into actual from public.documents where id = any(fixture_documents) and review_status = 'approved';
    if actual <> 2 then raise exception 'Student review mutation succeeded'; end if;

    perform set_config('request.jwt.claims', json_build_object('sub', admin_id, 'role', 'authenticated')::text, true);
    set local role authenticated;
    select count(*) into actual from public.document_chunks where document_id = any(fixture_documents);
    if actual <> 2 then raise exception 'Admin approved-only chunks failed: %', actual; end if;
    if exists(select 1 from public.match_shield_chunks(array_fill(1.0, array[768])::extensions.vector, 20) m
        join public.documents d on d.id = m.document_id where d.review_status <> 'approved')
        then raise exception 'Admin RPC approval isolation failed'; end if;
    select count(*) into actual from public.security_events where id = any(fixture_events);
    if actual <> 3 then raise exception 'Admin event visibility failed'; end if;
    reset role;
end;
$test$;
rollback;
