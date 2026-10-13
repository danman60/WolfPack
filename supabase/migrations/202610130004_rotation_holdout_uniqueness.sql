begin;
create unique index wpr_holdout_once_per_protocol on public.wpr_trials(owner_id,(data->>'protocolId')) where kind='holdout';
insert into public.wpr_schema_migrations(version) values('202610130004_rotation_holdout_uniqueness');
notify pgrst,'reload schema';
commit;
