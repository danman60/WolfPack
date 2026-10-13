-- Isolated CAD paper strategy adoption; no old wp_* tables or services touched.
begin;
alter table public.wpr_portfolios
 add column active_plan_id uuid references public.wpr_trials(id),
 add column plan_revision integer not null default 0 check(plan_revision >= 0);

create function public.wpr_adopt_plan(p_owner uuid,p_study uuid,p_expected integer,p_plan_expected integer)
returns jsonb language plpgsql security invoker set search_path=public,pg_temp as $$
declare portfolio public.wpr_portfolios; study public.wpr_trials;
begin
 select * into portfolio from public.wpr_portfolios where owner_id=p_owner for update;
 if not found or portfolio.revision<>p_expected or portfolio.plan_revision<>p_plan_expected or p_expected is null or p_plan_expected is null then
  raise exception 'Portfolio or plan changed' using errcode='40001';
 end if;
 select * into study from public.wpr_trials where id=p_study and owner_id=p_owner;
 if not found or study.kind<>'development' or study.data->>'namespace' is distinct from 'strategy'
  or study.data->>'purpose' is distinct from 'study' or study.data->>'protocolVersion' is distinct from 'cad-rotation-selector-v1'
  or (study.data->>'portfolioId') is distinct from portfolio.id::text
  or (study.data->>'portfolioRevision') is distinct from portfolio.revision::text then
  raise exception 'Study does not match current portfolio' using errcode='40001';
 end if;
 update public.wpr_portfolios set active_plan_id=p_study,plan_revision=plan_revision+1,updated_at=clock_timestamp() where id=portfolio.id;
 return jsonb_build_object('activePlanId',p_study,'planRevision',portfolio.plan_revision+1);
end $$;
revoke all on function public.wpr_adopt_plan(uuid,uuid,integer,integer) from public,anon,authenticated;
grant execute on function public.wpr_adopt_plan(uuid,uuid,integer,integer) to service_role;

-- Existing financial audit must not invent a second financial event on adoption.
create or replace function public.wpr_audit_portfolio_write() returns trigger
language plpgsql security invoker set search_path=public,pg_temp as $$
declare event jsonb; event_kind text;
begin
 if tg_op='UPDATE' and new.data=old.data and new.revision=old.revision then
  if new.active_plan_id is distinct from old.active_plan_id or new.plan_revision<>old.plan_revision then
   insert into public.wpr_audit(owner_id,kind,detail) values(new.owner_id,'trial',jsonb_build_object(
    'action','adoptPlan','portfolioId',new.id,'revision',new.revision,
    'previousPlanId',old.active_plan_id,'planId',new.active_plan_id,'planRevision',new.plan_revision));
  end if;
  return new;
 end if;
 event:=new.data->'events'->-1;
 event_kind:=case when tg_op='INSERT' then 'create' when event->>'kind'='shift' then 'approve' else event->>'kind' end;
 insert into public.wpr_audit(owner_id,kind,detail) values(new.owner_id,event_kind,jsonb_build_object('portfolioId',new.id,'revision',new.revision,'eventId',event->>'id'));
 return new;
end $$;

-- Lock the portfolio before both plan validation and the original financial CAS.
-- The existing RPC retains all immutable-ledger, preview-expiry and consume checks.
create function public.wpr_commit_decision(p_owner uuid,p_next jsonb,p_expected integer,p_preview uuid default null,p_recommendation uuid default null,p_plan_expected integer default null)
returns jsonb language plpgsql security invoker set search_path=public,pg_temp as $$
declare portfolio public.wpr_portfolios; quote public.wpr_previews; recommendation public.wpr_trials;
 bound_id uuid:=p_recommendation; bound_plan integer:=p_plan_expected; result jsonb;
begin
 if p_expected is null then
  if p_recommendation is not null or p_plan_expected is not null then raise exception 'Opening cannot consume a recommendation' using errcode='22023'; end if;
  return public.wpr_commit_portfolio(p_owner,p_next,p_expected,p_preview);
 end if;
 select * into portfolio from public.wpr_portfolios where owner_id=p_owner for update;
 if not found or portfolio.revision<>p_expected then raise exception 'Portfolio changed' using errcode='40001'; end if;
 if p_preview is not null then
  select * into quote from public.wpr_previews where id=p_preview and owner_id=p_owner;
  if found and quote.data ? 'recommendationId' then
   bound_id:=(quote.data->>'recommendationId')::uuid;
   bound_plan:=(quote.data->>'planRevision')::integer;
   if quote.data->>'planId' is distinct from portfolio.active_plan_id::text then raise exception 'Quote plan changed' using errcode='40001'; end if;
  end if;
 end if;
 if bound_id is not null then
  select * into recommendation from public.wpr_trials where id=bound_id and owner_id=p_owner;
  if not found or recommendation.kind<>'development' or recommendation.data->>'namespace' is distinct from 'strategy'
   or recommendation.data->>'purpose' is distinct from 'recommendation'
   or recommendation.data->>'protocolVersion' is distinct from 'cad-rotation-selector-v1'
   or recommendation.data->>'planId' is distinct from portfolio.active_plan_id::text
   or recommendation.data->>'planRevision' is distinct from portfolio.plan_revision::text
   or bound_plan is distinct from portfolio.plan_revision
   or recommendation.data->>'portfolioId' is distinct from portfolio.id::text
   or recommendation.data->>'portfolioRevision' is distinct from portfolio.revision::text
   or nullif(recommendation.data->>'expiresAt','') is null
   or (recommendation.data->>'expiresAt')::timestamptz<=clock_timestamp() then
    raise exception 'Recommendation or plan changed or expired' using errcode='40001';
  end if;
  if p_preview is null then
   if recommendation.data->>'decision' is distinct from 'hold' or p_next->'events'->-1->>'kind' is distinct from 'hold' then raise exception 'Recommended HOLD required' using errcode='22023'; end if;
  elsif recommendation.data->>'decision' is distinct from 'shift' then raise exception 'Recommended shift required' using errcode='22023';
  end if;
 end if;
 result:=public.wpr_commit_portfolio(p_owner,p_next,p_expected,p_preview);
 if bound_id is not null then
  insert into public.wpr_audit(owner_id,kind,detail) values(p_owner,'trial',jsonb_build_object('action','recommendationDecision',
   'recommendationId',bound_id,'planId',portfolio.active_plan_id,'planRevision',portfolio.plan_revision,
   'portfolioId',portfolio.id,'revision',p_expected+1,'eventId',p_next->'events'->-1->>'id','previewId',p_preview));
 end if;
 return result;
end $$;
revoke all on function public.wpr_commit_decision(uuid,jsonb,integer,uuid,uuid,integer) from public,anon,authenticated;
grant execute on function public.wpr_commit_decision(uuid,jsonb,integer,uuid,uuid,integer) to service_role;
insert into public.wpr_schema_migrations(version) values('202610130005_rotation_strategy_plan');
notify pgrst,'reload schema';
commit;
