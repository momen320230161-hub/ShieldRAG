-- Authorized operator only. Exercise the actual server RPCs; preserve all rows.
begin;
do $test$
declare
    student_id uuid := gen_random_uuid();
    admin_id uuid := gen_random_uuid();
    first_id uuid := gen_random_uuid();
    second_id uuid := gen_random_uuid();
    actual integer;
    document public.documents%rowtype;
begin
    insert into auth.users(id,email) values(student_id,student_id::text || '@example.invalid'),
                                            (admin_id,admin_id::text || '@example.invalid');
    update public.profiles set role='admin' where id=admin_id;
    set local role authenticated;
    begin
        perform * from public.shield_register_document(student_id,first_id,'synthetic.txt',
            'ingestions/' || student_id::text || '/' || first_id::text || '.txt',repeat('a',64),'public');
        raise exception 'Authenticated caller unexpectedly registered a document directly';
    exception when insufficient_privilege then null;
    end;
    begin
        perform * from public.shield_review_document(admin_id,first_id,'approved',repeat('a',64),null);
        raise exception 'Authenticated caller unexpectedly reviewed a document directly';
    exception when insufficient_privilege then null;
    end;
    reset role;
    set local role service_role;
    select * into document from public.shield_register_document(student_id,first_id,'synthetic.txt',
        'ingestions/' || student_id::text || '/' || first_id::text || '.txt',repeat('a',64),'restricted');
    if document.review_status <> 'pending' or document.index_status <> 'not_indexed'
        or document.uploaded_by <> student_id then raise exception 'Registration state failed'; end if;
    begin
        perform * from public.shield_review_document(student_id,first_id,'approved',repeat('a',64),null);
        raise exception 'Student review unexpectedly succeeded';
    exception when sqlstate 'PT403' then null;
    end;
    begin
        perform * from public.shield_review_document(admin_id,first_id,'approved',repeat('b',64),null);
        raise exception 'Mismatched hash unexpectedly approved';
    exception when sqlstate 'PT409' then null;
    end;
    select count(*) into actual from public.security_events where document_id=first_id;
    if actual <> 1 then raise exception 'Failed review changed the audit history'; end if;
    select * into document from public.shield_review_document(admin_id,first_id,'approved',repeat('a',64),null);
    if document.review_status <> 'approved' or document.index_status <> 'not_indexed'
        or document.reviewed_by <> admin_id or document.reviewed_at is null then
        raise exception 'Approval state failed'; end if;
    begin
        perform * from public.shield_review_document(admin_id,first_id,'rejected',null,'synthetic');
        raise exception 'Duplicate review unexpectedly succeeded';
    exception when sqlstate 'PT409' then null;
    end;
    select count(*) into actual from public.security_events where document_id=first_id;
    if actual <> 2 then raise exception 'Approval audit count failed'; end if;
    perform * from public.shield_register_document(student_id,second_id,'synthetic.txt',
        'ingestions/' || student_id::text || '/' || second_id::text || '.txt',repeat('c',64),'public');
    select * into document from public.shield_review_document(admin_id,second_id,'rejected',null,'synthetic rejection');
    if document.review_status <> 'rejected' or document.index_status <> 'not_indexed' then
        raise exception 'Rejection state failed'; end if;
    select count(*) into actual from public.security_events where document_id=second_id and decision='deny';
    if actual <> 1 then raise exception 'Rejection audit count failed'; end if;
    reset role;
end;
$test$;
rollback;
