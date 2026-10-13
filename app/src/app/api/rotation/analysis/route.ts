import { apiError, protectedRoute, response } from '@/lib/rotation/server';
import { getCurrentAnalysis } from '@/lib/rotation/analysis-server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export const GET = protectedRoute(async () => {
  try { return response({analysis: await getCurrentAnalysis()}); }
  catch (error) { return apiError(error); }
});
