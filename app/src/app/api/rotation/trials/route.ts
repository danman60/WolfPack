import { createHash } from "node:crypto";
import { GET as getHistory } from "@/app/api/rotation/history/route";
import { CRYPTO_ASSETS, type HistoryDataset, type ResearchConfig } from "@/lib/rotation/contract";
import { RESEARCH_VERSION, type ResearchProtocol, type ResearchScenario, type ResearchTrial, type ResearchTrialSummary } from "@/lib/rotation/research-contract";
import { ApiError, apiError, dbRequest, freshMarket, getPortfolio, protectedRoute, rateLimit, readBody, requireSameOrigin, response } from "@/lib/rotation/server";
import { calendarDay, evaluateHoldout, evaluatorFingerprintSource, runValidation, shiftDay, shiftMonth } from "@/lib/rotation/validation";
import { createStrategyTrial, loadStrategyTrial } from '@/lib/rotation/strategy-server';

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function uuid(value: unknown): string {
  if (typeof value !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)) throw new ApiError("A valid trial identifier is required.");
  return value;
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new ApiError("Trial data must be an object.");
  return value as Record<string, unknown>;
}

function researchConfig(raw: unknown): ResearchConfig {
  const input = record(raw);
  for (const field of ["capitalCad", "lookbackDays", "riskPercent", "feeBps", "slippageBps"]) {
    if (typeof input[field] !== "number" || !Number.isFinite(input[field])) throw new ApiError(`${field} must be a finite number.`);
  }
  const config: ResearchConfig = { capitalCad: input.capitalCad as number, cadence: input.cadence as ResearchConfig["cadence"], lookbackDays: input.lookbackDays as number, riskPercent: input.riskPercent as number, feeBps: input.feeBps as number, slippageBps: input.slippageBps as number };
  if (config.capitalCad <= 0 || config.capitalCad > 1e12) throw new ApiError("Scenario capital must be positive and at most CAD 1 trillion.");
  if (config.cadence !== "weekly" && config.cadence !== "monthly") throw new ApiError("Choose weekly or monthly reviews.");
  if (!Number.isInteger(config.lookbackDays) || config.lookbackDays < 14 || config.lookbackDays > 180) throw new ApiError("Lookback must be 14–180 whole calendar days.");
  if (config.riskPercent < 0 || config.riskPercent > 100 || config.feeBps < 0 || config.feeBps > 1000 || config.slippageBps < 0 || config.slippageBps > 1000) throw new ApiError("Allocation or cost assumptions are outside the allowed range.");
  return config;
}

async function history(): Promise<HistoryDataset> {
  const result = await getHistory();
  const body = await result.json();
  if (!result.ok) throw new ApiError(body.error || "Historical prices could not be loaded.", 502);
  return body as HistoryDataset;
}

export const GET = protectedRoute(async (request, user) => {
  try {
    const id = new URL(request.url).searchParams.get("id");
    const strategy = new URL(request.url).searchParams.get('strategy') === '1';
    if (strategy) {
      if (id) return response({trial: await loadStrategyTrial(user, id)});
      const trials = await dbRequest(`wpr_trials?owner_id=eq.${user.id}&data->>namespace=eq.strategy&select=id,created_at,kind,purpose:data->>purpose,protocolId:data->>protocolId&order=created_at.desc&limit=50`, {}, user.accessToken);
      return response({trials});
    }
    if (id) {
      const rows = await dbRequest<ResearchTrial[]>(`wpr_trials?owner_id=eq.${user.id}&id=eq.${uuid(id)}&data->>namespace=is.null&select=id,created_at,kind,data`, {}, user.accessToken);
      if (rows.length !== 1) throw new ApiError("Trial not found in this workspace.", 404);
      return response({ trial: rows[0] });
    }
    const trials = await dbRequest<ResearchTrialSummary[]>(`wpr_trials?owner_id=eq.${user.id}&data->>namespace=is.null&select=id,created_at,kind,protocolId:data->>protocolId,forwardHoldoutStart:data->>forwardHoldoutStart,forwardHoldoutEnd:data->>forwardHoldoutEnd&order=created_at.desc&limit=50`, {}, user.accessToken);
    return response({ trials });
  } catch (error) { return apiError(error); }
});

export const POST = protectedRoute(async (request, user) => {
  try {
    requireSameOrigin(request);
    await rateLimit(request, `research:${user.id}`, 12);
    const body = await readBody(request, 256_000);
    const id = uuid(body.id);
    const input = record(body.data);
    if (input.namespace === 'strategy') return response({trial: await createStrategyTrial(user, body)}, 201);
    const kind = body.kind;
    let data: ResearchTrial["data"];
    if (kind === "protocol") {
      if (input.protocolVersion !== RESEARCH_VERSION) throw new ApiError("Unknown research protocol version.");
      const config = researchConfig(input.config);
      // Source data and current marks come from public server adapters, never
      // from a browser-supplied result, source hash or synthetic dataset.
      const dataset = await history();
      if (dataset.points.length < 575) throw new ApiError("Insufficient real history for the registered chronological protocol.");
      const portfolio = await getPortfolio(user);
      let scenario: ResearchScenario | undefined;
      if (portfolio) {
        const market = await freshMarket();
        const marks = { ...dataset.points.at(-1)!.prices };
        for (const asset of CRYPTO_ASSETS) marks[asset] = (Number(market.books[asset].bid) + Number(market.books[asset].ask)) / 2;
        scenario = { balances: { ...portfolio.balances }, marks, asOf: market.fetchedAt, basis: "entered-portfolio" };
      }
      const forwardHoldoutStart = shiftDay(calendarDay(new Date().toISOString()), 1);
      data = { protocolVersion: RESEARCH_VERSION, config, dataset, scenario,
        sourceHash: createHash("sha256").update(JSON.stringify({ source: dataset.source, points: dataset.points })).digest("hex"),
        evaluatorHash: createHash("sha256").update(evaluatorFingerprintSource()).digest("hex"),
        buildCommit: process.env.VERCEL_GIT_COMMIT_SHA ?? process.env.GITHUB_SHA ?? null,
        historicalExposure: "already-exposed", forwardHoldoutStart,
        forwardHoldoutEnd: shiftDay(shiftMonth(forwardHoldoutStart, 12), -1),
      } satisfies ResearchProtocol;
    } else if (kind === "development" || kind === "holdout") {
      const protocolId = uuid(input.protocolId);
      const rows = await dbRequest<ResearchTrial[]>(`wpr_trials?owner_id=eq.${user.id}&id=eq.${protocolId}&kind=eq.protocol&data->>namespace=is.null&select=id,created_at,kind,data`, {}, user.accessToken);
      if (rows.length !== 1 || !("protocolVersion" in rows[0].data)) throw new ApiError("Registered protocol not found in this workspace.", 404);
      const protocol = rows[0].data as ResearchProtocol;
      if (protocol.protocolVersion !== RESEARCH_VERSION) throw new ApiError("This protocol requires its original evaluator version.", 409);
      if (protocol.evaluatorHash !== createHash("sha256").update(evaluatorFingerprintSource()).digest("hex")) throw new ApiError("The compiled research evaluator differs from the registered version. View its saved results or register a new future protocol; old holdouts cannot use changed logic.", 409);
      const expectedHash = createHash("sha256").update(JSON.stringify({ source: protocol.dataset.source, points: protocol.dataset.points })).digest("hex");
      if (expectedHash !== protocol.sourceHash) throw new ApiError("Registered historical source integrity check failed.", 409);
      if (kind === "development") {
        data = { protocolId, report: runValidation(protocol.dataset, protocol.config, protocol.scenario) };
      } else {
        const existing = await dbRequest<ResearchTrial[]>(`wpr_trials?owner_id=eq.${user.id}&kind=eq.holdout&data->>protocolId=eq.${protocolId}&select=id,created_at,kind,data`, {}, user.accessToken);
        if (existing.length) return response({ trial: existing[0] });
        if (calendarDay(new Date().toISOString()) <= protocol.forwardHoldoutEnd) throw new ApiError(`Forward holdout remains sealed through ${protocol.forwardHoldoutEnd}. No future-period performance has been calculated.`, 409);
        const latest = await history();
        const merged = new Map(protocol.dataset.points.map((point) => [point.date, point]));
        for (const point of latest.points) {
          const archived = merged.get(point.date);
          if (archived && CRYPTO_ASSETS.some((asset) => archived.prices[asset] !== point.prices[asset])) throw new ApiError("Historical source revisions differ from the frozen archive. Holdout evaluation is suspended for provenance review.", 409);
          merged.set(point.date, point);
        }
        const points = [...merged.values()].sort((a, b) => a.date.localeCompare(b.date));
        const combined: HistoryDataset = { ...latest, points, coverageStart: points[0].date, coverageEnd: points.at(-1)!.date };
        data = { protocolId, ...evaluateHoldout(combined, protocol) };
      }
    } else throw new ApiError("Choose protocol, development or holdout trial type.");
    const saved = await dbRequest<ResearchTrial[]>("wpr_trials", { method: "POST", body: JSON.stringify({ id, owner_id: user.id, kind, data }) });
    if (saved.length !== 1) throw new ApiError("Trial was not confirmed saved.", 503);
    return response({ trial: saved[0] }, 201);
  } catch (error) { return apiError(error); }
});
