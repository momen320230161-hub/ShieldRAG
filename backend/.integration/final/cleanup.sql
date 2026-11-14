begin;
do $cleanup$
begin
    if exists(select 1 from auth.users where id in ('a5654568-c643-47c3-a322-53d332fc565a','bf0b6f91-ba8a-4aeb-b5cc-264300f47add')
        and (raw_app_meta_data->>'shieldrag_test_run' is distinct from '55b0584a-aa5f-46b0-9d1d-af5ea1dbb3c8'
             or email not like 'shieldrag-' || '55b0584a-aa5f-46b0-9d1d-af5ea1dbb3c8' || '-%@example.invalid'))
        then raise exception 'Cleanup refused: account marker mismatch'; end if;
    if exists(select 1 from public.documents where id in ('9d93deb2-81eb-4fbf-b102-fbbeffd246c8','6e869290-97ad-425b-b3cd-f52048a79ef8','6ec13330-87a2-4c55-ad55-d56c72a2a80b','cbcc64fd-d280-450a-8c3f-10608977dbc4','12196da3-adbd-498c-8039-055a3d427968','277a4b62-b796-40d9-a0de-e5c38b6e4717')
        and (uploaded_by not in ('a5654568-c643-47c3-a322-53d332fc565a','bf0b6f91-ba8a-4aeb-b5cc-264300f47add') or not starts_with(storage_path, '__shieldrag_test__/55b0584a-aa5f-46b0-9d1d-af5ea1dbb3c8/')))
        then raise exception 'Cleanup refused: document marker mismatch'; end if;
    if exists(select 1 from public.documents where uploaded_by in ('a5654568-c643-47c3-a322-53d332fc565a','bf0b6f91-ba8a-4aeb-b5cc-264300f47add') and id not in ('9d93deb2-81eb-4fbf-b102-fbbeffd246c8','6e869290-97ad-425b-b3cd-f52048a79ef8','6ec13330-87a2-4c55-ad55-d56c72a2a80b','cbcc64fd-d280-450a-8c3f-10608977dbc4','12196da3-adbd-498c-8039-055a3d427968','277a4b62-b796-40d9-a0de-e5c38b6e4717'))
        or exists(select 1 from public.document_chunks where document_id in ('9d93deb2-81eb-4fbf-b102-fbbeffd246c8','6e869290-97ad-425b-b3cd-f52048a79ef8','6ec13330-87a2-4c55-ad55-d56c72a2a80b','cbcc64fd-d280-450a-8c3f-10608977dbc4','12196da3-adbd-498c-8039-055a3d427968','277a4b62-b796-40d9-a0de-e5c38b6e4717') and id not in ('79ac525e-e994-4cb0-94c6-0052120a91ee','1a1aa4df-31c9-4cac-ae22-b77244b153bc','2c2c79ab-7b7c-46e4-bc99-bee14c2dd6ee','02768f36-d691-4690-abcb-742683a7d313','89025905-1db1-4259-80a4-25ad8aff8c1a','602db1cf-489c-44e3-91ad-6edcbd3f0b22'))
        or exists(select 1 from public.documents where reviewed_by in ('a5654568-c643-47c3-a322-53d332fc565a','bf0b6f91-ba8a-4aeb-b5cc-264300f47add'))
        or exists(select 1 from public.security_events where user_id in ('a5654568-c643-47c3-a322-53d332fc565a','bf0b6f91-ba8a-4aeb-b5cc-264300f47add') or document_id in ('9d93deb2-81eb-4fbf-b102-fbbeffd246c8','6e869290-97ad-425b-b3cd-f52048a79ef8','6ec13330-87a2-4c55-ad55-d56c72a2a80b','cbcc64fd-d280-450a-8c3f-10608977dbc4','12196da3-adbd-498c-8039-055a3d427968','277a4b62-b796-40d9-a0de-e5c38b6e4717'))
        or exists(select 1 from public.chat_sessions where user_id in ('a5654568-c643-47c3-a322-53d332fc565a','bf0b6f91-ba8a-4aeb-b5cc-264300f47add'))
        or exists(select 1 from public.evaluation_runs where started_by in ('a5654568-c643-47c3-a322-53d332fc565a','bf0b6f91-ba8a-4aeb-b5cc-264300f47add'))
        then raise exception 'Cleanup refused: unexpected referencing data'; end if;
    delete from public.document_chunks where id in ('79ac525e-e994-4cb0-94c6-0052120a91ee','1a1aa4df-31c9-4cac-ae22-b77244b153bc','2c2c79ab-7b7c-46e4-bc99-bee14c2dd6ee','02768f36-d691-4690-abcb-742683a7d313','89025905-1db1-4259-80a4-25ad8aff8c1a','602db1cf-489c-44e3-91ad-6edcbd3f0b22') and document_id in ('9d93deb2-81eb-4fbf-b102-fbbeffd246c8','6e869290-97ad-425b-b3cd-f52048a79ef8','6ec13330-87a2-4c55-ad55-d56c72a2a80b','cbcc64fd-d280-450a-8c3f-10608977dbc4','12196da3-adbd-498c-8039-055a3d427968','277a4b62-b796-40d9-a0de-e5c38b6e4717');
    delete from public.documents where id in ('9d93deb2-81eb-4fbf-b102-fbbeffd246c8','6e869290-97ad-425b-b3cd-f52048a79ef8','6ec13330-87a2-4c55-ad55-d56c72a2a80b','cbcc64fd-d280-450a-8c3f-10608977dbc4','12196da3-adbd-498c-8039-055a3d427968','277a4b62-b796-40d9-a0de-e5c38b6e4717');
    -- Auth-owned session/identity rows and the fixture profiles cascade normally.
    delete from auth.users where id in ('a5654568-c643-47c3-a322-53d332fc565a','bf0b6f91-ba8a-4aeb-b5cc-264300f47add')
        and raw_app_meta_data->>'shieldrag_test_run' = '55b0584a-aa5f-46b0-9d1d-af5ea1dbb3c8';
    if exists(select 1 from auth.users where id in ('a5654568-c643-47c3-a322-53d332fc565a','bf0b6f91-ba8a-4aeb-b5cc-264300f47add'))
        or exists(select 1 from public.profiles where id in ('a5654568-c643-47c3-a322-53d332fc565a','bf0b6f91-ba8a-4aeb-b5cc-264300f47add'))
        or exists(select 1 from public.documents where id in ('9d93deb2-81eb-4fbf-b102-fbbeffd246c8','6e869290-97ad-425b-b3cd-f52048a79ef8','6ec13330-87a2-4c55-ad55-d56c72a2a80b','cbcc64fd-d280-450a-8c3f-10608977dbc4','12196da3-adbd-498c-8039-055a3d427968','277a4b62-b796-40d9-a0de-e5c38b6e4717'))
        or exists(select 1 from public.document_chunks where id in ('79ac525e-e994-4cb0-94c6-0052120a91ee','1a1aa4df-31c9-4cac-ae22-b77244b153bc','2c2c79ab-7b7c-46e4-bc99-bee14c2dd6ee','02768f36-d691-4690-abcb-742683a7d313','89025905-1db1-4259-80a4-25ad8aff8c1a','602db1cf-489c-44e3-91ad-6edcbd3f0b22'))
        then raise exception 'Cleanup incomplete: fixture rows remain'; end if;
end;
$cleanup$;
commit;
select (select count(*) from auth.users where id in ('a5654568-c643-47c3-a322-53d332fc565a','bf0b6f91-ba8a-4aeb-b5cc-264300f47add'))
     + (select count(*) from public.profiles where id in ('a5654568-c643-47c3-a322-53d332fc565a','bf0b6f91-ba8a-4aeb-b5cc-264300f47add'))
     + (select count(*) from public.documents where id in ('9d93deb2-81eb-4fbf-b102-fbbeffd246c8','6e869290-97ad-425b-b3cd-f52048a79ef8','6ec13330-87a2-4c55-ad55-d56c72a2a80b','cbcc64fd-d280-450a-8c3f-10608977dbc4','12196da3-adbd-498c-8039-055a3d427968','277a4b62-b796-40d9-a0de-e5c38b6e4717'))
     + (select count(*) from public.document_chunks where id in ('79ac525e-e994-4cb0-94c6-0052120a91ee','1a1aa4df-31c9-4cac-ae22-b77244b153bc','2c2c79ab-7b7c-46e4-bc99-bee14c2dd6ee','02768f36-d691-4690-abcb-742683a7d313','89025905-1db1-4259-80a4-25ad8aff8c1a','602db1cf-489c-44e3-91ad-6edcbd3f0b22')) as remaining_fixture_rows;
