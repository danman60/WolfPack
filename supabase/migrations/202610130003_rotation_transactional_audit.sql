begin;
create function public.wpr_audit_portfolio_write() returns trigger
language plpgsql security invoker set search_path=public,pg_temp as $$
declare event jsonb; event_kind text;
begin
 event := new.data->'events'->-1;
 event_kind := case when tg_op='INSERT' then 'create' when event->>'kind'='shift' then 'approve' else event->>'kind' end;
 insert into public.wpr_audit(owner_id,kind,detail) values(new.owner_id,event_kind,jsonb_build_object('portfolioId',new.id,'revision',new.revision,'eventId',event->>'id'));
 return new;
end $$;
revoke all on function public.wpr_audit_portfolio_write() from public,anon,authenticated;
grant execute on function public.wpr_audit_portfolio_write() to service_role;
create trigger wpr_portfolio_write_audit after insert or update on public.wpr_portfolios for each row execute function public.wpr_audit_portfolio_write();
insert into public.wpr_schema_migrations(version) values('202610130003_rotation_transactional_audit');
notify pgrst,'reload schema';
commit;
