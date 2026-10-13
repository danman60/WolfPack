import { apiError, config, dbRequest, demoEnabled, protectedRoute, response } from '@/lib/rotation/server';
export const dynamic = 'force-dynamic';
export const GET = protectedRoute(async () => {
  try {
    const cfg = config();
    const [database, auth] = await Promise.all([
      dbRequest<{version:string}[]>('wpr_schema_migrations?select=version&version=eq.202610130001_rotation_workshop'),
      fetch(`${cfg.url}/auth/v1/health`, {headers:{apikey:cfg.anon},cache:'no-store',signal:AbortSignal.timeout(10000)}),
    ]);
    return response({ mode: 'paper-workshop', database: database.length === 1 ? 'operational' : 'migration-unverified', auth: auth.ok ? 'operational' : 'unavailable', demo: demoEnabled() ? 'enabled-isolated-synthetic-accounts' : 'disabled', persistence: 'server-ledger-with-atomic-revision-check', liveTrading: 'disabled', passwordRecovery: 'not-enabled-seeded-workshop-accounts-only', backups: 'platform-managed; rotation-specific restore not rehearsed', ownerDecisions: ['actual funding', 'custody/provider', 'risk and concentration limits'] });
  } catch (error) { return apiError(error); }
});
