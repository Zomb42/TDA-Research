# TDA project instructions

Read `START_HERE.md` for project context. User instructions in the conversation take precedence.

## BTC/liquidity scope correction — user, October 29, 2026

- **Coinbase follow-up:** the user also requested Coinbase historical-depth documentation, their existing key context and data-volume assessment. This is exploration within the no-fee constraint, not a commitment to switch venues or start indefinite collection. See `btc/COINBASE_HISTORICAL_API.md` for the checked distinction between free live depth and unestablished free historical replay. Preserve the user's historical-data question.

- **Latest budget/preference instruction:** the user does not want to pay any fee and is leaning toward collecting Kalshi data themselves. Treat paid data/API subscriptions, purchases, and paid cloud hosting as out of scope. Use public/free access and existing resources only; do not initiate trials requiring payment or buy a subscription. The Deribit/Tardis pilot was obtained from free samples and is not a reason to recommend paid access. Recommend improving data-only Kalshi BTC-perp recording for new history under this constraint, while preserving the distinction from historical backfill. A stated preference is not authorization to start an indefinite process or install a persistent service.

- **Platform preference, latest October 29 clarification:** Kalshi is preferred, but the user explicitly accepts other venues if historical full-depth data is available. Investigate and validate practical alternatives rather than blocking on Kalshi. Prefer a simple data-access platform; a Tardis archive is third-party data access, not an exchange's own API. A third-party Kalshi archive must explicitly support the requested perps; prediction-event coverage is insufficient. Free public sample collection is within scope; paid subscriptions/purchases are not automatically authorized.

- The user is asking whether **external historical data contains the snapshots, incremental order-book messages, and trades needed to reconstruct books for markets beyond their existing recordings**. Investigate archived data access, actual schemas, market/date coverage, completeness, granularity and cost.
- Keep the BTC project focused on relevant BTC markets, including actual spot/perpetual instruments and Kalshi perps. **Do not substitute Kalshi BTC 15-minute binary event contracts for this work.** Only work on those event contracts again if the user explicitly requests them.
- The user already knows their HFT folder contains complete previously collected order-book streams. Do not present finding, recounting, plotting or replaying those files as a discovery or as an answer to external historical-data availability. The folder was supplied for implementation techniques and access context.
- Distinguish historical message-level L2/L3 data, periodic depth snapshots, trade-only tapes, candles and coarse depth bands. Candles/trades/band totals do not satisfy a request for archived book updates. L2 also does not automatically reveal every original order or exact queue position.
- Treat live recording as a separate activity. It does not answer whether historical data can be obtained. Do not redirect a historical-data request into more live collection.
- Verify external availability with provider/exchange documentation and, where possible, a real sample from a market/date not in the user's existing archive. Clearly separate documented, access-tested, downloaded and replay-validated claims. Do not infer global unavailability from one exchange's API or a failed URL.
- **Do not submit, amend or cancel orders.** Do not launch the original HFT collector/strategy executable. Use isolated market-data-only tools. Read existing credentials in place only when needed for authorized data access; do not expose or copy secrets.
- Record conclusions candidly. The prior focus on the user's old 15-minute files was an assistant scope mistake, not newly requested research progress.

## Research reporting

Keep equity, BTC temporal features, and liquidity geometry distinct. Preserve gross/pre-fee reporting, causal preprocessing, source attribution, and the separation between descriptive findings and predictive claims. Do not alter equity work merely to update BTC context.
