begin;
grant select on public.wpr_previews to authenticated;
create policy wpr_preview_owner on public.wpr_previews for select to authenticated using(owner_id=((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'sub')::uuid));
create table public.wpr_audit (
 id uuid primary key default gen_random_uuid(),
 owner_id uuid not null references public.wpr_members(user_id),
 kind text not null check(kind in ('signin','signout','export','create','preview','approve','hold','deposit','withdrawal','trial')),
 detail jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now()
);
alter table public.wpr_audit enable row level security;
revoke all on public.wpr_audit from anon,authenticated;
grant select on public.wpr_audit to authenticated;
grant select,insert on public.wpr_audit to service_role;
create policy wpr_audit_owner on public.wpr_audit for select to authenticated using(owner_id=((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'sub')::uuid));
insert into public.wpr_schema_migrations(version) values('202610130002_rotation_owner_reads_audit');
notify pgrst,'reload schema';
commit;
