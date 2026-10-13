-- Isolated rotation allocation executor. No wp_* wallet tables changed.
begin;
create table public.wpr_batches (
 id uuid primary key, owner_id uuid not null references public.wpr_members(user_id),
 projection_id uuid not null references public.wpr_trials(id), portfolio_id uuid not null references public.wpr_portfolios(id),
 revision integer not null check(revision>=0), data jsonb not null,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(owner_id,projection_id), check((data->>'id')::uuid=id),check((data->>'revision')::integer=revision)
);
alter table public.wpr_batches enable row level security;
revoke all on public.wpr_batches from anon,authenticated;
grant select on public.wpr_batches to authenticated;
grant all on public.wpr_batches to service_role;
create policy wpr_batch_owner on public.wpr_batches for select to authenticated using(owner_id=((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'sub')::uuid));
create function public.wpr_write_batch(p_owner uuid,p_batch jsonb,p_expected integer,p_portfolio_expected integer,p_next jsonb default null)
returns jsonb language plpgsql security invoker set search_path=public,pg_temp as $$
declare portfolio public.wpr_portfolios; prior public.wpr_batches; projection public.wpr_trials; saved jsonb;
begin
 select * into portfolio from public.wpr_portfolios where owner_id=p_owner for update;
 if not found then raise exception 'Portfolio not found' using errcode='40001';end if;
 select * into prior from public.wpr_batches where owner_id=p_owner and projection_id=(p_batch->>'projectionId')::uuid for update;
 if p_expected is null and found then return prior.data;end if;
 if portfolio.id<>(p_batch->>'portfolioId')::uuid or portfolio.revision<>p_portfolio_expected then raise exception 'Portfolio changed' using errcode='40001';end if;
 select * into projection from public.wpr_trials where id=(p_batch->>'projectionId')::uuid and owner_id=p_owner;
 if not found or projection.data->>'namespace'<>'allocation-projection' then raise exception 'Projection not owned' using errcode='42501';end if;
 if p_expected is null then
  if (p_batch->>'revision')::integer<>0 or p_next is not null or projection.data->'projection'->>'startingRevision'<>portfolio.revision::text then raise exception 'Invalid opening batch' using errcode='40001';end if;
  if exists(select 1 from public.wpr_batches where owner_id=p_owner and data->>'status' in ('running','paused')) then raise exception 'Finish or pause and abandon existing allocation before applying another' using errcode='40001';end if;
  insert into public.wpr_batches(id,owner_id,projection_id,portfolio_id,revision,data) values((p_batch->>'id')::uuid,p_owner,projection.id,portfolio.id,0,p_batch);
 else
  if prior.id is null or prior.id<>(p_batch->>'id')::uuid or prior.revision<>p_expected or (p_batch->>'revision')::integer<>p_expected+1 then raise exception 'Batch changed' using errcode='40001';end if;
  if p_batch->'targetWeights'<>prior.data->'targetWeights' or p_batch->'maxCostCad'<>prior.data->'maxCostCad' or p_batch->'mode'<>prior.data->'mode' then raise exception 'Approved batch constraints changed' using errcode='22023';end if;
  if p_next is not null then saved:=public.wpr_commit_portfolio(p_owner,p_next,p_portfolio_expected,null);end if;
  update public.wpr_batches set data=p_batch,revision=(p_batch->>'revision')::integer,updated_at=clock_timestamp() where id=prior.id;
 end if;
 insert into public.wpr_audit(owner_id,kind,detail) values(p_owner,'trial',jsonb_build_object('action','allocationBatch','batchId',p_batch->>'id','status',p_batch->>'status','revision',p_batch->>'revision'));
 return p_batch;
end $$;
revoke all on function public.wpr_write_batch(uuid,jsonb,integer,integer,jsonb) from public,anon,authenticated;
grant execute on function public.wpr_write_batch(uuid,jsonb,integer,integer,jsonb) to service_role;
create unique index wpr_allocation_outcome_unique on public.wpr_trials(owner_id,(data->>'projectionId')) where data->>'namespace'='allocation-outcome';
insert into public.wpr_schema_migrations(version) values('202610130006_rotation_allocation_batches');
notify pgrst,'reload schema';
commit;
