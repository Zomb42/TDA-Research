# Historical full-depth BTC perpetual pilot — Deribit, January 1, 2025

Collected October 29, 2026. **Exchange: Deribit. Archive provider: Tardis.** This is external historical BTC perpetual data; it uses neither Kalshi event contracts nor a newly started live recorder. Kalshi remains preferred if comparable historical perp depth becomes accessible; the user explicitly permits alternatives with historical full depth.

## What is actually saved

The complete daily normalized L2 and matching trade archives were downloaded publicly without credentials, using the provider's free first-of-month access. Both files match advertised byte counts and MD5 checksums; local SHA256 values and exact URLs are retained in [downloads.json](downloads.json). Both gzip streams passed CRC checks on complete reading.

| Data | Verified result |
|---|---:|
| Total price-level records | 15,452,352 |
| Initial/resnapshot rows | 5,837 across 2 contiguous snapshot blocks |
| Incremental replacement-size rows | 15,446,515 |
| Zero-size removal rows | 4,571,417 |
| Public executions | 50,816 |
| Saved reconstructed book checkpoints | 1,440 |
| Maximum bid/ask levels at checkpoints | 1,958 / 1,354, respective maxima |
| Crossed/locked sampled books | 0 |
| Decreasing local/exchange timestamps | 0 / 0 in this day |

The book file covers **00:00:00.225572–23:59:59.955258 UTC**. The longest observed interval between price-level records is **9.182477 seconds**. That is an observation gap, not an established outage or proof of inactivity. Two snapshot blocks mean that a resnapshot occurred; normalized CSV alone does not show explicit disconnect events or native sequence IDs. Do not claim proven uninterrupted whole-day capture.

## Fields and reconstruction

Book columns: `exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount`. Timestamps are UTC epoch microseconds. `amount` **replaces** quantity at `(side,price)`; zero removes that level. Consecutive snapshot rows initialize/reset the book. Updates before the first snapshot must be excluded. Rows preserve provider capture order; multiple level rows can come from one message.

`raw/incremental_book_L2.csv.gz` retains all daily rows; `raw/trades.csv.gz` retains trade ID, side, price, amount and both clocks. `book_checkpoints.jsonl.gz` stores full native-precision price/quantity ladders at approximately one-minute observation intervals; `book_summary_1m.csv` stores actual observation timestamps, best prices, spread and level counts. These checkpoints do not replace the retained update history.

Deribit's official API defines inverse perpetual amount in USD units, not BTC quantity. The native trade records also expose separate `contracts`; the checked minute has amount/contracts = 10 throughout. Preserve this distinction. Any BTC-equivalent calculation must explicitly use the inverse contract convention and observed price. No automatic conversion was applied to the saved raw/checkpoint quantities. [Official API specification](https://docs.deribit.com/specifications/deribit_openapi.json).

## Original-message access also tested

A separate historical API GET retrieved **one native minute**, including:

- **1 full snapshot and 8,652 change messages**, with `new`, `change`, and `delete` price-level actions.
- `change_id` and `prev_change_id`; no broken links were found within that minute.
- **16 native trade messages**, containing **28 individual executions**.

Independent native-message replay matches the first normalized full-day book checkpoint exactly, and all 28 native executions match the daily trade CSV by ID, price, amount and direction. [Native access evidence and example messages](../../samples/external_historical_books_2026-10-29/deribit_native_minute/access_test.json), [cross-validation](native_cross_validation.json).

The native test covers **one minute only**. Full-day sequence continuity and explicit outage mapping would require the corresponding native-day replay. The normalized full day was completely downloaded and processed, but it cannot independently supply those missing native fields. [Daily audit](audit.json).

## Suitability and access limits

This is a concrete full-depth L2 pilot for spread/depth/imbalance, liquidity concentrations, replenishment and price-by-time topology, with matched executed-flow data. It is aggregate displayed liquidity, not every original order identity, queue position, or hidden quantity. One day is a plumbing/interpretation pilot, not an adequate statistical sample for a general predictive claim.

Tardis documents full-depth Deribit snapshots/updates, historical coverage since March 2019, and first-of-month free samples. Exact instrument/date eligibility still needs metadata checks before broader collection; non-sample dates require the appropriate access. No subscription was purchased. [Depth coverage](https://docs.tardis.dev/faq/order-books), [Deribit archive](https://docs.tardis.dev/historical-data-details/deribit), [dataset access](https://docs.tardis.dev/downloadable-csv-files/api), [native historical API](https://docs.tardis.dev/api/http-api-reference).

Reproduce the normalized full-day collection and checks from the project root:

```sh
python market_data/collect_deribit_historical_day.py
python market_data/probe_deribit_native_history.py
```

No credentials, accounts, trading endpoints, live subscriptions or order actions are used.
