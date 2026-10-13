# Read-only exchange connection: verified contract and remaining gate

Sourced: 2026-10-12T23:20:26-04:00 Eastern. Research only: no private exchange request, credential import, funding action or order was executed. Provider choice remains with the owner. This document is a concrete next implementation slice, not a claim that an exchange account is connected.

## Existing implementation, verified locally

`app/src/lib/exchange/kraken.ts:26` accepts credentials but only marks its paper adapter connected. Its balance and order functions call `/intel/kraken/paper/*`. `intel/wolfpack/exchanges/kraken.py` invokes the installed Kraken CLI for public USD candles and perpetual market/depth data. Those are reusable transport concepts, not an authenticated CAD spot ledger or live execution implementation. Existing code remains untouched.

Credential-name inventory of `~/.env.keys`, `app/.env.local`, `intel/.env`, and process environment found no `NDAX`/`KRAKEN` names. The installed CLI's local `kraken auth show -o json` reports its API-key value as a not-set placeholder; the first naive nonempty-string check was corrected before reaching a conclusion. `~/.config/kraken` contains `instance_id` and `paper`. This proves only the inspected configuration paths; it does not assert credentials cannot exist elsewhere. The CLI's private `auth test`/balance commands were not run.

## Ndax

The exchange documents API-key creation with selectable permissions and a separately revealed secret. Its authenticated WebSocket endpoint is `wss://api.ndax.io/WSGateway/`; `AuthenticateUser` takes APIKey, Signature, UserId and Nonce, with UserId/Nonce strings. The official reference explicitly says that this authentication call is not an HTTP login. [Ndax key setup](https://ndax.io/en/support/api_access_and_developer_tools/find-credentials-ndax-trading-api), [authentication reference](https://apidoc.ndax.io/#authenticateuser).

Read-only account discovery/balances use `GetUserAccountInfos` and `GetAccountPositions`; both permit `AccountReadOnly`. Positions distinguish amount, hold and pending deposits/withdrawals. Account/OMS identity must come from the authenticated account response. The official repository authentication example supplies a literal Signature but does not show its derivation. The API reference describes a signature with APIKey and Nonce; the reviewed reference and repository do not establish the exact signing algorithm, input concatenation and encoding. Signature derivation and a definitive key-permission introspection method remain unverified before a connection can be called ready. [Account API](https://apidoc.ndax.io/#getaccountpositions), [official WebSocket message examples](https://github.com/NDAXlO/ndax-api-documentation).

### Signature evidence follow-up

The live GitHub API lists 43 public repositories under `NDAXlO`: 42 forks and one original documentation repository. That original repository contains only `README.md` at commit `234d7aa7dd23ea0f8369d8a71ee1053c5f90a8c0`; the authentication example supplies APIKey, Signature, UserId and Nonce but no reproducible secret/signing fixture. The separate `API` repository is a static documentation fork; its text repeats the parameter descriptions. Searches of those source texts found no HMAC/SHA256 derivation. This is a scoped evidence result, not a claim that Ndax has no other documentation. [Official repository inventory](https://api.github.com/users/NDAXlO/repos?per_page=100), [pinned authentication example](https://github.com/NDAXlO/ndax-api-documentation/blob/234d7aa7dd23ea0f8369d8a71ee1053c5f90a8c0/README.md#authentication), [documentation fork](https://github.com/NDAXlO/API/tree/0688861a62d995a40c1472214b3e611c04fbf8e6).

No exact algorithm, concatenation order, secret decoding or signature encoding is promoted to a verified Ndax contract. A complete exchange-published signing example/fixture or a read-only acceptance check with an owner-authorized key is needed to close that gap. Provider selection and authorization are still pending; no key or private request was used. Third-party adapters returned by search were excluded from this official-source conclusion. [Captured evidence](security-evidence/ndax-signature-research.json).

## Kraken

Spot private REST uses API-Key/API-Sign headers and an increasing nonce. Signing combines the URI path, SHA256 of nonce plus encoded POSTdata, and HMAC-SHA512 using the decoded API secret. Server instances need a shared per-key nonce allocator to prevent concurrent requests reusing or decreasing a nonce. API-key 2FA can additionally require an OTP. [Kraken authentication](https://docs.kraken.com/exchange/guides/rest/authentication).

`GetApiKeyInfo` authenticates without an additional permission requirement and returns granted permissions/restrictions. The proposed connection refuses trading, cancellation, funding, withdrawal and unknown scopes. Begin with `query-funds`; add order/history/ledger read scopes only when those features are implemented. [Key introspection](https://docs.kraken.com/api-reference/account-data/get-api-key-info), [permission definitions](https://support.kraken.com/articles/how-to-create-an-api-key-on-kraken-pro).

`BalanceEx` returns balances and held/credit amounts. The spot-only adapter must keep borrowed credit out of owned inventory and expose reserved balances rather than declaring all total units spendable. Extended staking/earn assets require explicit treatment; do not merge them into immediately available CAD/BTC/ETH/LINK. [Extended balances](https://docs.kraken.com/api-reference/account-data/get-extended-balance).

Kraken also documents OAuth-based Kraken Connect. A confidential client needs a provisioned client ID and encrypted client secret, so a working consumer-style connection button requires that provider setup; it is not created merely by adding a callback route. [Kraken Connect](https://docs-legacy.kraken.com/api/docs/oauth/kraken-connect/).

## Next implementation slice, after provider decision

1. Provide a separate **Connect account — read only** surface requiring an owner identity, never a public demo membership. Show exact read permissions and reject broader keys. Do not silently repurpose the paper login as exchange authorization.
2. Keep the owner's initial secret in deployment-scoped server secret storage; do not put it in browser storage, URLs, the paper JSON ledger, trial exports or the shared workshop database. A multi-user key store requires separately reviewed envelope encryption/key management and customer-data isolation before collecting keys.
3. Implement only an explicit provider-method allowlist: authenticated account identity, key permissions where supported, balances, and subsequently open orders/fees. No generic proxy, order endpoint, transfer, withdrawal or funding-address call.
4. On successful authentication read identity and CAD/BTC/ETH/LINK totals, reserved amounts, available owned units, and timestamp. Persist only the connection's nonsecret status/identity reference and an audit event. Keep live balances visually separate from paper opening units; importing a paper copy requires an explicit user action.
5. Revoke/disconnect removes local credential access and cached account data; it must not claim to revoke the exchange key unless the exchange confirmed that action. Invalid permission, expiry, 2FA and provider errors remain distinct.

Acceptance: owner verifies account identity and displayed live balances against the exchange; another app/demo owner cannot use the connection; private logs/client bundles/exports contain no key; every forbidden method is structurally unreachable. This is the read-only readiness gate. Funded execution still needs custody selection, approved risk limits, trade-only permissions, fill reconciliation and a separately authorized real order.
