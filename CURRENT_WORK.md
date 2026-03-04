# Current Work - WolfPack

## Active Task
New session — resuming from Supabase fix. `4a53990` should be deployed on Vercel by now.

## Previous Session (2026-03-03)
1. **Intelligence quality fixes** (`2808fbe`) — R1 for Quant, Brief data gaps, JSON fence stripping, conviction filter 55
2. **Paper trading** (`cb854c9`) — `/paper/order` endpoint, frontend wired
3. **Mobile nav + live prices** (`33ba477`) — hamburger menu, portfolio fetches live prices
4. **Comprehensive quality pass** (`1afa67a`) — 19 issues across 10 files
5. **Supabase fix** (`8a9fac2`, `4a53990`) — REST-only client (no auth session, no Realtime)

## Supabase Status
- "Connection interrupted while trying to subscribe" — Realtime WebSocket was failing
- REST API works fine (verified via curl + MCP)
- RLS is OFF on all wp_ tables
- Fix: `supabase.ts` REST-only client — `4a53990` pushed, should be deployed

## VPS Details
- Host: `root@ubuntu-s-1vcpu-1gb-tor1-01` (159.89.115.95)
- Repo: `/root/WolfPack`
- Uvicorn: `.venv/bin/uvicorn wolfpack.api:app --host 127.0.0.1 --port 8000 --workers 2`
- Has auto-restart — uvicorn respawns after kill
- `fuser -k 8000/tcp` to kill, then restart

## Next Steps
1. Verify Supabase fix — user needs to hard refresh Vercel deployment
2. Test all pages (dash, intelligence, trading, portfolio)
3. Register for WalletConnect project ID + subgraph API key
4. HTTPS on VPS (Caddy/nginx + Let's Encrypt)
