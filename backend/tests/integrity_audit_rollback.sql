-- Operator-only database contract checks. All synthetic fixtures roll back.
begin;
do $test$
declare
    student_id uuid := gen_random_uuid();
    admin_id uuid := gen_random_uuid();
    first_id uuid := gen_random_uuid();
    second_id uuid := gen_random_uuid();
    event_id uuid := gen_random_uuid();
    actor_id uuid;
    result_id uuid;
    actual integer;
    first_path text;
    second_path text;
begin
    insert into auth.users(id,email) values(student_id,student_id::text || '@example.invalid'),
                                            (admin_id,admin_id::text || '@example.invalid');
    update public.profiles set role='admin' where id=admin_id;
    first_path := 'ingestions/' || student_id::text || '/' || first_id::text || '.txt';
    second_path := 'ingestions/' || student_id::text || '/' || second_id::text || '.txt';
    set local role service_role;
    perform * from public.shield_register_document(student_id,first_id,'synthetic.txt',first_path,repeat('a',64),'restricted');
    perform * from public.shield_register_document(student_id,second_id,'synthetic.txt',second_path,repeat('a',64),'public');
    begin
        perform public.shield_record_integrity_failure(student_id,first_id,event_id,'sha256_mismatch',
                                                       repeat('a',64),first_path,repeat('b',64));
        raise exception 'Non-Admin actor unexpectedly recorded integrity event';
    exception when sqlstate 'PT403' then null;
    end;
    begin
        perform public.shield_record_integrity_failure(admin_id,first_id,event_id,'sha256_mismatch',
                                                       repeat('c',64),first_path,repeat('b',64));
        raise exception 'Stale metadata association unexpectedly accepted';
    exception when sqlstate 'PT409' then null;
    end;
    begin
        perform public.shield_record_integrity_failure(admin_id,first_id,event_id,'arbitrary_client_reason',
                                                       repeat('a',64),first_path,repeat('b',64));
        raise exception 'Uncontrolled audit type unexpectedly accepted';
    exception when sqlstate 'PT422' then null;
    end;
    begin
        perform public.shield_record_integrity_failure(admin_id,first_id,event_id,'sha256_mismatch',
                                                       repeat('a',64),first_path,repeat('a',64));
        raise exception 'Equal hashes unexpectedly accepted as a mismatch';
    exception when sqlstate 'PT422' then null;
    end;
    result_id := public.shield_record_integrity_failure(admin_id,first_id,event_id,'sha256_mismatch',
                                                        repeat('a',64),first_path,repeat('b',64));
    if result_id <> event_id then raise exception 'Audit acknowledgement differs'; end if;
    perform public.shield_record_integrity_failure(admin_id,first_id,event_id,'sha256_mismatch',
                                                    repeat('a',64),first_path,repeat('b',64));
    select count(*) into actual from public.security_events where document_id=first_id
        and event_type='document_integrity_failure' and decision='deny'
        and reason='SHA-256 mismatch detected' and user_id=admin_id;
    if actual <> 1 then raise exception 'Persistent audit/retry count failed'; end if;
    if (select review_status from public.documents where id=first_id) <> 'pending' then
        raise exception 'Integrity audit changed document state'; end if;
    begin
        perform public.shield_record_integrity_failure(admin_id,second_id,event_id,'sha256_mismatch',
                                                       repeat('a',64),second_path,repeat('b',64));
        raise exception 'Audit ID was rebound to another document';
    exception when sqlstate 'PT409' then null;
    end;
    reset role;
    foreach actor_id in array array[student_id,admin_id] loop
        perform set_config('request.jwt.claims',json_build_object('sub',actor_id,'role','authenticated')::text,true);
        set local role authenticated;
        begin
            perform public.shield_record_integrity_failure(admin_id,first_id,event_id,'sha256_mismatch',
                                                           repeat('a',64),first_path,repeat('b',64));
            raise exception 'User JWT role unexpectedly invoked server audit operation';
        exception when insufficient_privilege then null;
        end;
        begin
            insert into public.security_events(user_id,document_id,event_type,decision,reason)
            values(actor_id,first_id,'document_integrity_failure','deny','unsafe client reason');
            raise exception 'User unexpectedly inserted audit event';
        exception when insufficient_privilege then null;
        end;
        update public.security_events set reason='unsafe client reason' where id=event_id;
        reset role;
    end loop;
    if (select reason from public.security_events where id=event_id) <> 'SHA-256 mismatch detected' then
        raise exception 'User modified persisted audit event'; end if;
end;
$test$;
rollback;
