# Liquidity: the Kalshi BTC perp order book

The third of the project's three studies. It asks how displayed liquidity in an order book is organized, whether topology (mainly Reeb graphs, plus point clouds) describes it better than plain measures, and whether anything in it can be traded. Everything is before fees.

## Read in this order

1. **[BOOK_SHAPE.md](BOOK_SHAPE.md):** what the book looks like. Depth ridges, how they move, refill after large trades, the band graph, Reeb splits. Descriptive.
2. **[WHO_WINS.md](WHO_WINS.md):** who makes money trading against the book, and why. Kalshi follows Binance with a 100–200 ms delay, plus every trading test.
3. **[BOOK_CLOUD.md](BOOK_CLOUD.md):** each second of the book as a point in a point cloud. Its shape, and whether that shape forecasts anything.

## Main results

- **The book is a ladder that moves with the price.** Depth sits in narrow ridges at fixed distances from the midpoint (about 6–7, 20–21 and 24–25 bp). The whole ladder re-prices when Binance moves; Binance explains 75% of Kalshi's one-second price changes.
- **Resting orders lose almost immediately.** A filled resting order is worth −0.42 bp per contract 0.1 s later, mostly because the trade followed a Binance move from the last 300 ms.
- **No slow strategy found an edge.** We tried taking after Binance moves with a 100 ms delay, resting orders at any distance, pulling quotes after Binance moves, and a hedged Kalshi–Binance gap trade. All lose before fees, or break even only with an unrealistically instant reaction.
- **Topology finds real structure but adds no forecasting power.** The band graph's events are mostly the midpoint moving. Its features, and the point cloud's persistence, are explained 72–97% by plain counts and add nothing once those are known. This matches the equity and BTC studies.
- **A plain by-product:** average displayed depth plus how much the book's shape moved improves a 5-minute volatility forecast by 15%.

## What changes the book, from biggest effect to smallest

1. **Binance moves.** Market makers re-post their whole ladder at the new price within about 100–200 ms. Binance explains 75% of Kalshi's one-second price changes.
2. **Fast traders trade in that window.** 44% of volume follows Binance's last 300 ms move, hitting quotes that haven't been updated yet. They ride the move rather than cause it.
3. **Large trades.** Nearby depth dips, but about 90% of the disappearing depth is cancelled and re-posted rather than traded. The price steps about 2 bp and does not bounce back, because Binance moved too.
4. **Flicker at the best quotes.** Small adds and cancels, about 575 updates per second, move the midpoint by fractions of a tick. That reshuffles bins and produces most Reeb-graph splits.
5. **A standing pattern.** Ridges at about 6–7 and 20–25 bp are there day after day, almost never traded against. They look like market makers quoting fixed sizes at fixed distances from a Binance-based price. That reading is inferred from timing and shape; the feed shows no order identities.

## Words used throughout

| Term | Meaning |
|---|---|
| **bp** (basis point) | 0.01% of price. One tick ($1/BTC) is about 0.14 bp. The median spread is 0.46 bp. |
| **Bid, ask, spread** | Best price someone will buy at, best price someone will sell at, and the gap between them. |
| **Midpoint** | Plain (best bid + best ask) / 2, with no weighting by size, used everywhere. A size-weighted version, the *microprice*, was checked in BOOK_SHAPE §5 and changes nothing. |
| **Depth** | Dollar value of resting orders displayed at a price, or summed over a range of prices. |
| **Moving frame / fixed frame** | Measuring depth by distance from the current midpoint, or at fixed prices. |
| **Ridge** | A distance from the midpoint where depth is consistently piled up. |
| **High bin, band** | A 1-bp bin above the frozen depth cutoff (the November 11 90th percentile, about $1.51m); a band is a run of neighbouring high bins. |
| **Band graph / time-Reeb graph** | Bands at each second joined across time, recording births, deaths, splits and merges. Astra's discrete version links bands that share a bin; the continuous TTK version interpolates between snapshots. |
| **Maker / resting order, taker** | An order waiting in the book, and the order that trades against it. |
| **Markout** | What a filled resting order is worth later: fill price against the later midpoint, positive when the resting order gained. |
| **Plain twin** | A simple, non-topological measure built from the same inputs as a TDA feature. Every TDA result is shown against one. |
| **Out-of-sample** | Fit on November 12–14, scored on November 15–17. |
| **95% interval** | Resampling whole hours (moves cluster in time) and taking the middle 95% of results. |
| **Receipt time** | When the recorder received a message. Every analysis uses it, so only information available at the time is used. |

## Data

- **Kalshi KXBTCPERP**, November 10, 23:50 to November 17, 23:50 UTC: full order-book updates and trades, recorded on Notre Dame's CRC cluster. It is 7.6 GB compressed, in `market_data/recordings/crc/2026-11-10T23-50-19Z-job-1724180/` (not in git). Every saved book checkpoint matches the replay; there is one 2.6 s reconnect gap. November 11 is used only for calibration.
- **Binance BTCUSDT** futures and spot trades for the same days, from Binance's free public files, in `market_data/datasets/btc_binance_aggtrades_2026-11-11_17/`.
- **This is the final dataset** (user decision, November 18). No further collection.

More on data sources and validation: [btc/DATA.md](../btc/DATA.md).

## Scripts (`studies/`, run in order with the `tda` Python)

| Script | What it does | Used in |
|---|---|---|
| `l01_snapshots.py` (+ `replay_book.cpp`) | Rebuild the book at the end of every second; check against every saved book | all |
| `l02_describe.py` | Depth profile; fixed vs moving frame | BOOK_SHAPE §1–2 |
| `l03_band_age.py`, `check_book_shape.py` | Band graph, band paths, band-age forecasts, independent check | BOOK_SHAPE §3 |
| `l04_trade_tape.py` | Individual trades, reconciled with the books | |
| `l05_refill.py`, `l06_book_breaks.py`, `check_refill.py` | Large trades vs matched quiet seconds; ridges; band transitions | BOOK_SHAPE §4 |
| `l07_native_reeb.py`, `l08_split_replay.py`, `l09_audit_splits.py` | Continuous TTK Reeb graphs; message-level replay of splits | BOOK_SHAPE §5 |
| `l10_reference_tape.py` | Kalshi's published reference index | WHO_WINS §1 |
| `l11_bbo_tape.py` (+ `replay_bbo.cpp`) | Best quotes every 100 ms and just before every trade | WHO_WINS |
| `l12_binance_grid.py` | Binance prices every 100 ms | WHO_WINS |
| `l13_who_wins.py` | Lead-lag, markouts, slow taker, resting orders, predictability | WHO_WINS §1–5 |
| `l14_band_features.py` | Band graph vs plain twins for forecasting | WHO_WINS §6 |
| `l15_quote_filter.py` | Pulling quotes after Binance moves | WHO_WINS §7 |
| `l16_book_cloud.py` | Point clouds of book states | BOOK_CLOUD |
| `l17_gap_trade.py` | Hedged Kalshi–Binance gap trade | WHO_WINS §8 |
| `l18_followups.py` | Microprice check of splits; price path after large trades; trade distances; Kalshi–Binance price gap | BOOK_SHAPE §1, §4, §5; WHO_WINS §1 |

Large intermediate files (hourly books, quote grids, trade tapes) are written to `results/book_shape/snapshots/` and are not in git. Small results and figures are in `results/book_shape/`, `results/refill/` and `results/who_wins/`.

## Earlier work

- **November 5 pilot:** a 25-hour capture and the first continuous Reeb graphs with TTK, in `experiments/btc_archive_initial_2026_11_05/`. It showed that cycle counts depend heavily on settings, which shaped the later design (summarized in BOOK_SHAPE §6). It stays in place because `l07_native_reeb.py` reuses its TTK code.
- **October pilots** (synthetic demo, binary-contract preview, Binance coarse depth, capture assessment) and the superseded plans and design notes are in `_archive/liquidity_2026-11-18/` on this machine. Tracked files can also be restored from git commit `5f0579f`.

## Open questions, if time allows

Everything needed for the December 4 presentation is done. Optional extras:

- Exit the gap trade with a resting order instead of crossing the spread. I expect a loss, since resting orders are what gets picked off.
- Check whether the band-graph splits survive a half-bin shift of the grid, or a 2-bp grid.
