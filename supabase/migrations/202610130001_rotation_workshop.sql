-- WolfPack isolated spot PAPER workspace. Apply only to existing NETCUP workshop.
-- No old wp_* tables, existing auth behavior, tenant services or routers are changed.
begin;
create table public.wpr_schema_migrations (version text primary key, applied_at timestamptz not null default now());
create table public.wpr_members (
  user_id uuid primary key, -- GoTrue ID verified server-side; workshop_owner cannot access auth schema.
  is_demo boolean not null default false,
  created_at timestamptz not null default now()
);
create table public.wpr_portfolios (
  id uuid primary key,
  owner_id uuid not null unique references public.wpr_members(user_id),
  revision integer not null check(revision >= 0),
  data jsonb not null check(jsonb_typeof(data) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((data->>'id')::uuid = id),
  check ((data->>'revision')::integer = revision)
);
create table public.wpr_previews (
  id uuid primary key,
  owner_id uuid not null references public.wpr_members(user_id),
  portfolio_id uuid not null references public.wpr_portfolios(id),
  revision integer not null check(revision >= 0),
  data jsonb not null check(jsonb_typeof(data) = 'object'),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  consumed_at timestamptz
);
create index wpr_previews_owner_created on public.wpr_previews(owner_id,created_at desc);
create table public.wpr_trials (
  id uuid primary key,
  owner_id uuid not null references public.wpr_members(user_id),
  kind text not null check(kind in ('development','holdout','protocol')),
  data jsonb not null check(jsonb_typeof(data) = 'object'),
  created_at timestamptz not null default now()
);
create index wpr_trials_owner_created on public.wpr_trials(owner_id,created_at desc);
create table public.wpr_rate_limits (
  key text primary key,
  window_start timestamptz not null,
  hits integer not null check(hits > 0)
);
alter table public.wpr_schema_migrations enable row level security;
alter table public.wpr_members enable row level security;
alter table public.wpr_portfolios enable row level security;
alter table public.wpr_previews enable row level security;
alter table public.wpr_trials enable row level security;
alter table public.wpr_rate_limits enable row level security;
-- Reads may use an authenticated JWT; writes are server only. Workshop's other apps
-- cannot create memberships, submit arbitrary financial JSON or consume previews.
revoke all on public.wpr_schema_migrations,public.wpr_members,public.wpr_portfolios,public.wpr_previews,public.wpr_trials,public.wpr_rate_limits from anon,authenticated;
grant select on public.wpr_members,public.wpr_portfolios,public.wpr_trials to authenticated;
grant all on public.wpr_schema_migrations,public.wpr_members,public.wpr_portfolios,public.wpr_previews,public.wpr_trials,public.wpr_rate_limits to service_role;
create policy wpr_member_self on public.wpr_members for select to authenticated using(user_id = ((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'sub')::uuid));
create policy wpr_portfolio_owner on public.wpr_portfolios for select to authenticated using(owner_id = ((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'sub')::uuid));
create policy wpr_trial_owner on public.wpr_trials for select to authenticated using(owner_id = ((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'sub')::uuid));

-- Invoker runs as service_role only (BYPASSRLS); no elevated function privileges.
-- Row lock + revision check + preview consumption commit in one transaction.
create function public.wpr_commit_portfolio(p_owner uuid,p_next jsonb,p_expected integer,p_preview uuid default null)
returns jsonb language plpgsql security invoker set search_path = public, pg_temp as $$
declare oldrow public.wpr_portfolios; quote public.wpr_previews; next_revision integer;
begin
  if not exists(select 1 from public.wpr_members where user_id=p_owner) then raise exception 'Rotation membership required' using errcode='42501'; end if;
  next_revision := (p_next->>'revision')::integer;
  if p_expected is null then
    if next_revision <> 0 or p_preview is not null or jsonb_array_length(p_next->'events') <> 1 then raise exception 'Invalid opening revision' using errcode='22023'; end if;
    insert into public.wpr_portfolios(id,owner_id,revision,data) values((p_next->>'id')::uuid,p_owner,0,p_next);
    return p_next;
  end if;
  select * into oldrow from public.wpr_portfolios where owner_id=p_owner for update;
  if not found or oldrow.revision <> p_expected or oldrow.id <> (p_next->>'id')::uuid or next_revision <> p_expected+1 then raise exception 'Portfolio changed; reload before continuing' using errcode='40001'; end if;
  if jsonb_array_length(p_next->'events') <> jsonb_array_length(oldrow.data->'events')+1
    or (p_next->'events') - (jsonb_array_length(p_next->'events')-1) <> oldrow.data->'events'
    or p_next->'opening' <> oldrow.data->'opening'
    or p_next->'createdAt' <> oldrow.data->'createdAt'
    or p_next->'initialValueCad' <> oldrow.data->'initialValueCad'
    or p_next->'name' <> oldrow.data->'name'
    or p_next->'cadence' <> oldrow.data->'cadence'
    or p_next->'feeBps' <> oldrow.data->'feeBps'
    then raise exception 'Immutable ledger or settings changed' using errcode='22023'; end if;
  if p_preview is not null then
    select * into quote from public.wpr_previews where id=p_preview and owner_id=p_owner for update;
    if not found or quote.portfolio_id<>oldrow.id or quote.revision<>p_expected or quote.consumed_at is not null or quote.expires_at<=clock_timestamp() then raise exception 'Preview stale, expired or already approved' using errcode='40001'; end if;
    update public.wpr_previews set consumed_at=clock_timestamp() where id=p_preview;
  end if;
  update public.wpr_portfolios set data=p_next,revision=next_revision,updated_at=clock_timestamp() where id=oldrow.id;
  return p_next;
end $$;
revoke all on function public.wpr_commit_portfolio(uuid,jsonb,integer,uuid) from public,anon,authenticated;
grant execute on function public.wpr_commit_portfolio(uuid,jsonb,integer,uuid) to service_role;

create function public.wpr_take_rate_limit(p_key text,p_limit integer,p_seconds integer)
returns boolean language plpgsql security invoker set search_path = public, pg_temp as $$
declare count_now integer;
begin
 if length(p_key)>200 or p_limit<1 or p_limit>1000 or p_seconds<1 or p_seconds>86400 then raise exception 'Invalid rate limit'; end if;
 insert into public.wpr_rate_limits(key,window_start,hits) values(p_key,clock_timestamp(),1)
 on conflict(key) do update set
 hits=case when wpr_rate_limits.window_start < clock_timestamp()-make_interval(secs=>p_seconds) then 1 else wpr_rate_limits.hits+1 end,
 window_start=case when wpr_rate_limits.window_start < clock_timestamp()-make_interval(secs=>p_seconds) then clock_timestamp() else wpr_rate_limits.window_start end
 returning hits into count_now;
 return count_now<=p_limit;
end $$;
revoke all on function public.wpr_take_rate_limit(text,integer,integer) from public,anon,authenticated;
grant execute on function public.wpr_take_rate_limit(text,integer,integer) to service_role;
insert into public.wpr_schema_migrations(version) values('202610130001_rotation_workshop');
notify pgrst,'reload schema';
commit;
