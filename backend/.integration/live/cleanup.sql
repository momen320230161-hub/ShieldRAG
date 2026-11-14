begin;
do $cleanup$
begin
    if exists(select 1 from auth.users where id in ('1a752df6-41fb-490d-a5b6-04a14f62694a','b33bdefd-160c-47dd-9384-e04bef4cd421')
        and (raw_app_meta_data->>'shieldrag_test_run' is distinct from '14659f42-bab9-4f07-91d5-26f35c9c417e'
             or email not like 'shieldrag-' || '14659f42-bab9-4f07-91d5-26f35c9c417e' || '-%@example.invalid'))
        then raise exception 'Cleanup refused: account marker mismatch'; end if;
    if exists(select 1 from public.documents where id in ('6f50e702-af07-4565-8ed9-1a072c6e45f9','df27664b-67af-45c7-a30b-33074206fed2','34f691a9-a786-4687-a5ff-eecfd2bce526','df3e1c9f-5659-45ae-8889-a33e0fab169d','0da7f040-cbda-4c69-94ca-d1c5d03684ab','e9caab62-97a7-4edd-8818-d35585390e24')
        and (uploaded_by not in ('1a752df6-41fb-490d-a5b6-04a14f62694a','b33bdefd-160c-47dd-9384-e04bef4cd421') or not starts_with(storage_path, '__shieldrag_test__/14659f42-bab9-4f07-91d5-26f35c9c417e/')))
        then raise exception 'Cleanup refused: document marker mismatch'; end if;
    if exists(select 1 from public.documents where uploaded_by in ('1a752df6-41fb-490d-a5b6-04a14f62694a','b33bdefd-160c-47dd-9384-e04bef4cd421') and id not in ('6f50e702-af07-4565-8ed9-1a072c6e45f9','df27664b-67af-45c7-a30b-33074206fed2','34f691a9-a786-4687-a5ff-eecfd2bce526','df3e1c9f-5659-45ae-8889-a33e0fab169d','0da7f040-cbda-4c69-94ca-d1c5d03684ab','e9caab62-97a7-4edd-8818-d35585390e24'))
        or exists(select 1 from public.document_chunks where document_id in ('6f50e702-af07-4565-8ed9-1a072c6e45f9','df27664b-67af-45c7-a30b-33074206fed2','34f691a9-a786-4687-a5ff-eecfd2bce526','df3e1c9f-5659-45ae-8889-a33e0fab169d','0da7f040-cbda-4c69-94ca-d1c5d03684ab','e9caab62-97a7-4edd-8818-d35585390e24') and id not in ('02a5fe06-48f4-42ea-8e79-fccd04745fda','6de1df1d-3412-49db-8a9f-9f0723bb1953','794e4a87-5d57-4f73-8df3-78341d78d227','0b37fa52-4700-4f29-b9ae-adc58a7b4062','f627d80c-3346-4bbb-9f22-ef0430c7028b','615a28a4-ebb1-4460-bedd-cf91563f7179'))
        or exists(select 1 from public.documents where reviewed_by in ('1a752df6-41fb-490d-a5b6-04a14f62694a','b33bdefd-160c-47dd-9384-e04bef4cd421'))
        or exists(select 1 from public.security_events where user_id in ('1a752df6-41fb-490d-a5b6-04a14f62694a','b33bdefd-160c-47dd-9384-e04bef4cd421') or document_id in ('6f50e702-af07-4565-8ed9-1a072c6e45f9','df27664b-67af-45c7-a30b-33074206fed2','34f691a9-a786-4687-a5ff-eecfd2bce526','df3e1c9f-5659-45ae-8889-a33e0fab169d','0da7f040-cbda-4c69-94ca-d1c5d03684ab','e9caab62-97a7-4edd-8818-d35585390e24'))
        or exists(select 1 from public.chat_sessions where user_id in ('1a752df6-41fb-490d-a5b6-04a14f62694a','b33bdefd-160c-47dd-9384-e04bef4cd421'))
        or exists(select 1 from public.evaluation_runs where started_by in ('1a752df6-41fb-490d-a5b6-04a14f62694a','b33bdefd-160c-47dd-9384-e04bef4cd421'))
        then raise exception 'Cleanup refused: unexpected referencing data'; end if;
    delete from public.document_chunks where id in ('02a5fe06-48f4-42ea-8e79-fccd04745fda','6de1df1d-3412-49db-8a9f-9f0723bb1953','794e4a87-5d57-4f73-8df3-78341d78d227','0b37fa52-4700-4f29-b9ae-adc58a7b4062','f627d80c-3346-4bbb-9f22-ef0430c7028b','615a28a4-ebb1-4460-bedd-cf91563f7179') and document_id in ('6f50e702-af07-4565-8ed9-1a072c6e45f9','df27664b-67af-45c7-a30b-33074206fed2','34f691a9-a786-4687-a5ff-eecfd2bce526','df3e1c9f-5659-45ae-8889-a33e0fab169d','0da7f040-cbda-4c69-94ca-d1c5d03684ab','e9caab62-97a7-4edd-8818-d35585390e24');
    delete from public.documents where id in ('6f50e702-af07-4565-8ed9-1a072c6e45f9','df27664b-67af-45c7-a30b-33074206fed2','34f691a9-a786-4687-a5ff-eecfd2bce526','df3e1c9f-5659-45ae-8889-a33e0fab169d','0da7f040-cbda-4c69-94ca-d1c5d03684ab','e9caab62-97a7-4edd-8818-d35585390e24');
    -- Auth-owned session/identity rows and the fixture profiles cascade normally.
    delete from auth.users where id in ('1a752df6-41fb-490d-a5b6-04a14f62694a','b33bdefd-160c-47dd-9384-e04bef4cd421')
        and raw_app_meta_data->>'shieldrag_test_run' = '14659f42-bab9-4f07-91d5-26f35c9c417e';
    if exists(select 1 from auth.users where id in ('1a752df6-41fb-490d-a5b6-04a14f62694a','b33bdefd-160c-47dd-9384-e04bef4cd421'))
        or exists(select 1 from public.profiles where id in ('1a752df6-41fb-490d-a5b6-04a14f62694a','b33bdefd-160c-47dd-9384-e04bef4cd421'))
        or exists(select 1 from public.documents where id in ('6f50e702-af07-4565-8ed9-1a072c6e45f9','df27664b-67af-45c7-a30b-33074206fed2','34f691a9-a786-4687-a5ff-eecfd2bce526','df3e1c9f-5659-45ae-8889-a33e0fab169d','0da7f040-cbda-4c69-94ca-d1c5d03684ab','e9caab62-97a7-4edd-8818-d35585390e24'))
        or exists(select 1 from public.document_chunks where id in ('02a5fe06-48f4-42ea-8e79-fccd04745fda','6de1df1d-3412-49db-8a9f-9f0723bb1953','794e4a87-5d57-4f73-8df3-78341d78d227','0b37fa52-4700-4f29-b9ae-adc58a7b4062','f627d80c-3346-4bbb-9f22-ef0430c7028b','615a28a4-ebb1-4460-bedd-cf91563f7179'))
        then raise exception 'Cleanup incomplete: fixture rows remain'; end if;
end;
$cleanup$;
commit;
select (select count(*) from auth.users where id in ('1a752df6-41fb-490d-a5b6-04a14f62694a','b33bdefd-160c-47dd-9384-e04bef4cd421'))
     + (select count(*) from public.profiles where id in ('1a752df6-41fb-490d-a5b6-04a14f62694a','b33bdefd-160c-47dd-9384-e04bef4cd421'))
     + (select count(*) from public.documents where id in ('6f50e702-af07-4565-8ed9-1a072c6e45f9','df27664b-67af-45c7-a30b-33074206fed2','34f691a9-a786-4687-a5ff-eecfd2bce526','df3e1c9f-5659-45ae-8889-a33e0fab169d','0da7f040-cbda-4c69-94ca-d1c5d03684ab','e9caab62-97a7-4edd-8818-d35585390e24'))
     + (select count(*) from public.document_chunks where id in ('02a5fe06-48f4-42ea-8e79-fccd04745fda','6de1df1d-3412-49db-8a9f-9f0723bb1953','794e4a87-5d57-4f73-8df3-78341d78d227','0b37fa52-4700-4f29-b9ae-adc58a7b4062','f627d80c-3346-4bbb-9f22-ef0430c7028b','615a28a4-ebb1-4460-bedd-cf91563f7179')) as remaining_fixture_rows;
