# Provider and wallet evidence

Checked 2026-10-12, approximately 21:48–21:54 Eastern. Public documentation and unauthenticated market API reads only. No account creation, private trading API verification, transfer or order. Fees and access require rechecking before a funded launch.

## Decision

Recommend evaluating **one new exchange account holding CAD, BTC, ETH and LINK**, with Ndax first for its direct CAD markets and Kraken as the alternative with direct crypto cross pairs. This is an engineering/product recommendation for the requested workflow, not a finding that a strategy makes money. Final choice remains with the owner; capital, account fee tier, actual size-dependent execution cost and custody preference are unresolved.

An asset balance is not a separate strategy wallet. Four balances can sit inside one account; multiple experiments can have paper ledgers. Separate funded strategy accounts require an explicit owner decision and provider subaccount support verification.

## Ontario and CAD

The [OSC's current registered-platform list](https://www.osc.ca/en/industry/registration-and-compliance/registered-crypto-asset-trading-platforms) lists Ndax Canada Inc. as an investment dealer and Payward Canada Inc./Payward Inc. as a restricted dealer. Both rows link August 18, 2026 amendments. Direct HTTPS retrieval succeeded even though the research browser returned 403; regulatory findings come from the retrieved OSC HTML, not the failed browser result.

Both current amendments expressly include Ontario: [Ndax decision](https://www.osc.ca/en/securities-law/orders-rulings-decisions/ndax-canada-inc), [Kraken decision](https://www.osc.ca/en/securities-law/orders-rulings-decisions/payward-canada-inc-and-payward-inc-0). Their specified-asset lists include BTC and ETH; LINK remains subject to applicable account investment limits. The amendments add SOL to exempt assets; SOL is not part of this project's universe. Older help-page exemption lists are therefore incomplete. The provider must establish the owner's classification and actual remaining limit during onboarding; the design must not assume an unlimited LINK allocation.

| Capability | Ndax | Kraken Pro spot |
|---|---|---|
| CAD in | Free Interac or wire deposits according to current fee page; bank charges/limits remain separate | Interac deposits listed as free; bank account name must match Kraken identity |
| CAD out | Interac CAD 1.50; EFT CAD 4.99 | Interac CAD 10; other bank methods require checking the selected method's quote |
| Public spot markets verified | BTC/CAD, ETH/CAD, LINK/CAD, all Running and enabled | BTC/CAD, ETH/CAD, ETH/BTC, LINK/BTC, LINK/ETH, all online |
| Route within requested universe | Crypto → CAD → other crypto; charge both legs | BTC↔ETH↔LINK can use cross markets; CAD↔LINK can route through BTC or ETH |
| Posted base trading commission | 0.20% each buy/sell | Canadian page returned 0.40% maker / 0.80% taker at lowest tier; tiers improve with volume/assets |
| Automation interface | Retail trading API; documented orders, balances, fills, fee estimates and WebSocket authentication | REST/WebSocket spot APIs; order IDs, client order IDs, validation and execution reports |
| Untested | Owner's private API permission scope, effective fees/limits, fills, bank funding | Same; public global market availability is not account-specific trading eligibility |

Sources: [Ndax fees](https://ndax.io/en/fees), [Kraken Interac](https://support.kraken.com/gb/articles/4412259063444-how-do-i-fund-my-account-with-an-interac-e-transfer-), [Kraken Canadian fees](https://www.kraken.com/ca/features/fee-schedule), [Ndax retail API](https://apidoc.ndax.io/index.html), [Kraken Add Order](https://docs.kraken.com/api-reference/trading/add-order). Kraken's page warns that displayed fees can depend on location/VPN; obtain the authenticated account's pair-specific fees before choosing or simulating a live tier. Do not reuse remembered historical fees or equate a limit order with a guaranteed maker fill.

Public API provenance: [Ndax GetInstruments](https://api.ndax.io:8443/AP/GetInstruments?OMSId=1) returned instrument IDs 1/3/81 for BTC/ETH/LINK versus CAD. [Kraken AssetPairs](https://api.kraken.com/0/public/AssetPairs) returned the five routes above. A separate [Kraken market table](https://support.kraken.com/au/articles/kraken-markets) marks LINK/CAD unavailable. Two methods agree on the absence of a direct LINK/CAD order-book market in the inspected sources; instant conversion is a different product and fee schedule.

## Total cost, not commission alone

For each proposed shift, compute cost from executable bid/ask depth and account fees: spread crossing + market impact + commission on every leg + explicitly applicable funding/withdrawal/FX/network charges. Cash already inside the account does not incur a bank withdrawal on every rebalance. Avoid double-counting spread already embedded in the fill. Compare expected destination units and their CAD value, not headline fees.

Two 0.20% legs retain 0.998² = 99.6004% before spreads: a 0.3996% commission drag on value moved. Two 0.80% legs retain 0.992² = 98.4064%: 1.5936% drag at that quoted tier. These are illustrative calculations, not the owner's assigned tier or an all-in cost quote.

At 21:51:23 Eastern, public responses produced these full bid/ask spreads:

| Pair | Ndax Level 1 | Kraken ticker |
|---|---:|---:|
| BTC/CAD | 43.86 basis points | 2.76 basis points |
| ETH/CAD | 56.70 basis points | 0.51 basis points |
| LINK/CAD | 88.59 basis points | Route through BTC/ETH |
| LINK/BTC | Not sampled | 5.84 basis points |
| LINK/ETH | Not sampled | 4.46 basis points |

One basis point is 0.01%. These are **diagnostic snapshots, not a venue ranking or simulated fills**. Ndax response timestamps corresponded to 21:51:19 for BTC, 21:47:41 for ETH and 21:40:45 for LINK; quote freshness differed. Kraken ticker retrieval time is not proof of a synchronized exchange quote timestamp. Before a decision: fresh subscriptions/order books, executable quantity, actual fee tier and identical size/time comparison. Selected raw responses are retained in `public-market-evidence.json`.

## Account requirements and permissions

Ndax requires personal information, valid government photo ID and selfie verification; see [verification requirements](https://ndax.io/en/support/getting_started_and_verification/information-needed-verification). Kraken requires Canadian account verification and an investor questionnaire/risk acknowledgments; see [regulatory overview](https://support.kraken.com/ca/articles/canada-regulatory-requirements-overview). Age/residency and bank ownership must meet the chosen provider's onboarding terms. No assumption about the owner's investor classification.

Connect read-only first. Later execution needs a server-held key restricted to balance/order/history reads and spot trading/cancellation, with withdrawals disabled and IP restrictions where supported. Verify those exact restrictions on the new account; generic API documentation is insufficient. Scope keys and account IDs to the new system. The old futures credentials and routes are unsuitable defaults.

## Self-custody alternative

[MetaMask's current Bitcoin guide](https://support.metamask.io/configure/networks/bitcoin/) documents native BTC accounts and swaps from EVM/Solana assets into native BTC. It is incorrect to say MetaMask is necessarily EVM-only today. WolfPack's current wagmi configuration, however, enables Ethereum/Arbitrum EVM connections; it does not establish a native-Bitcoin application integration.

An explicit self-custody design is: native BTC on Bitcoin; ETH and LINK on Ethereum; actual CAD in a bank or chosen exchange account. ETH↔LINK can use an EVM swap. Native BTC↔ETH/LINK requires a verified cross-chain route or exchange deposit/trade/withdrawal. A wrapped-BTC token, stablecoin, bridge receipt or chain-native imitation is never silently treated as BTC or CAD. ETH is needed for gas and token approvals; BTC spends need network fees. Exact transaction simulation, minimum received, route, chains and asset contracts must be visible before signing.

[MetaMask Swaps](https://support.metamask.io/token-swaps/user-guide-swaps) quotes a 0.875% service fee; network and route costs must also be priced. Direct DEX integration has different costs and would need separate verification. [MetaMask Sell](https://support.metamask.io/manage-crypto/move-crypto/sell/how-to-sell-your-crypto-assets-for-fiat-currency-in-metamask) describes locale-specific providers, KYC and bank payouts; its regional FAQ lists US/UK/parts of Europe. That page does **not establish Ontario CAD off-ramp eligibility**. Do not claim a complete Ontario CAD round trip through the wallet based on generic buy support.

Concrete supported fallback: self-custody with the verified Canadian exchange providing CAD rails, subject to account-specific deposit networks/withdrawal checks. This retains key ownership for crypto but adds transfers, network fees, settlement delays and potentially several signatures to each CAD rotation. The exchange-held approach has custody exposure but fits the requested simple owner-click flow more directly. Custody choice remains open.

The remembered “better mask” identity remains unresolved. Verified repo names are injected wallet, WalletConnect and Coinbase Wallet. A generic injected connector can support a browser wallet without naming it in source; the search cannot identify which wallet the owner used.
