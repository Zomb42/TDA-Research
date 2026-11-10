# Perp capture: levels, storage, liquidity, and research scope

Measured November 4, 2026 in the existing `tda` Conda environment with [assess_perp_capture.py](../../../market_data/assess_perp_capture.py). Inputs: the [ten-minute Kalshi perp capture](../../../market_data/samples/kalshi_btc_stream_2026-11-04_10min/README.md), all 176 HFT Coinbase BTC files, and all 176 HFT Kalshi binary-event files. The older files are in `Junior-Spring/HFT/Kalshi-Orderbook-Predictor/{data,collector/rawdata}`. No source file was modified, private fill payload exported, or new live capture started.

Machine-readable results: [assessment.json](assessment.json). The CSVs retain checkpoint statistics and sampled public historical quote/book summaries, not private account data.

## Price levels

The initial perp snapshot had **158 bid + 91 ask = 249 occupied price levels**. Exact-decimal replay of every snapshot/delta gives:

| Occupied levels after each book event | Minimum | Median | Maximum |
|---|---:|---:|---:|
| Bids | 117 | 149 | 160 |
| Asks | 70 | 95 | 110 |
| Combined | 190 | 245 | 260 |

Column-wise extrema/medians need not occur at the same instant; do not add the separate bid/ask extrema to infer the combined maximum. These counts weight each book event equally. The five-second checkpoints have a slightly different median (249 combined), reflecting a different observation schedule.

Across the entire ten minutes, **716 distinct occupied prices** appeared: 473 on the bid side and 405 on the ask side, with some prices appearing on both sides at different times. This is not 716 simultaneous levels. With the saved contract metadata, the API tick corresponds to **$1/BTC**. Occupied quotes ranged from $56,000 to $91,000/BTC across the sample, with most economic depth much closer to the approximately $80,600 market. Empty price ticks are not stored as resting levels. There is no configured top-100 truncation in the recorder; it retains all book levels delivered by the feed.

## Measured storage

Includes both raw-message envelopes and convenience checkpoints. Decimal MB/GB, not binary MiB/GiB:

| Duration | Uncompressed | Gzip |
|---|---:|---:|
| Measured ten minutes | 39.77 MB | 4.04 MB |
| Projected hour | 238.62 MB | 24.26 MB |
| Projected day | 5.73 GB | 0.582 GB |
| Projected 30 days | 171.81 GB | 17.47 GB |

Gzip was actually measured on these exact bytes with the recorder's original compression settings: about **9.83× smaller**, or 89.8% saved. Hour/day/month values extrapolate this short sample; busy periods, payload changes, flush/rotation settings, and additional channels can change them. Compression is lossless and does not discard book updates. Stream decompression permits replay without loading a whole day into RAM; it still processes the recorded events.

**User's latest storage preference:** leave the ten-minute sample uncompressed for inspection, and use gzip for future captures. The future command in [LIVE_COLLECTION.md](../../../btc/LIVE_COLLECTION.md) includes `--gzip`. No new process was launched by this assessment.

## Displayed liquidity in the perp sample

The following are **medians of 119 saved full-book checkpoints**, approximately five seconds apart. They are displayed resting quantities, not balances, margin deposits, open interest, guaranteed executable capacity, or cumulative trade volume.

| Measure | Median |
|---|---:|
| Total bid quantity | 178.23 BTC |
| Total ask quantity | 171.76 BTC |
| Combined quantity | 350.32 BTC |
| Combined displayed limit-price notional | $28.22 million |
| Combined notional within 10 bps of midpoint (0.10%) | $6.82 million |
| Combined notional within 25 bps (0.25%) | $25.77 million |
| Combined notional within 50 bps (0.50%) | $27.54 million |
| Combined notional within 100 bps (1%) | $27.55 million |
| Best bid + best ask notional only | $2,628.97 |
| Quoted spread | 0.372 bps, approximately $3/BTC |

Combined full-book notional ranged from **$12.32m to $28.37m** across checkpoints. Medians of separately measured bid and ask fields need not add to the median of their combined field. A large total can coexist with a small best quote because most depth rests farther from the touch. Summing both sides describes the book's two-sided displayed size; a single buy or sell can only consume the opposite side.

Units: BTC quantity = contract count × 0.0001; notional at a level = API dollar price × contract count. All-depth totals sum each level's own quote, rather than repricing everything at the midpoint. Near-mid bands use the contemporaneous bid/ask midpoint. The nesting of depth bands and quantity totals was checked.

Separately, this ten-minute stream records **43.7142 BTC / $3.5254m of public executed notional**. That is turnover over time, not the amount simultaneously resting in the book.

## Historical HFT comparison

**April 20–23 histories versus a November 4 ten-minute perp sample: these are not contemporaneous observations or a controlled venue ranking.** Sampling also differs: the Coinbase comparison retains the latest recorded ticker in each global UTC five-second bucket; binary books retain the first nonempty reconstructed state per contract/file per five-second bucket. The historical cash/quantity units are source-specific.

| Dataset | What the saved files actually contain | Measured result |
|---|---|---|
| November Kalshi perp | Full reported price-level bid/ask snapshots/deltas, trades, ticker | Median best-bid-plus-best-ask notional **$2.63k**; full-book two-sided notional **$28.22m** |
| April Coinbase BTC-USD | Ticker and public trades; best quotes and their quantities, **no full L2 book** | Median best-bid-plus-best-ask notional **$25.85k**, best bid 0.106 BTC and best ask 0.151 BTC separately; median spread approximately **$0.01/BTC** |
| April Kalshi 15-minute binary events | YES/NO bid ladders, book deltas, trades; some private message types ignored | Median **$12.37k** of displayed bid cash across both outcomes, 152 combined bid levels; median top-of-book bid cash across the two outcomes **$357.86**; median implied YES spread **1 cent** |

The Coinbase historical quote size was larger at the touch in these samples; its deeper liquidity is **unknown from these files**, not zero. The original HFT Coinbase capture was already lightweight: **570.76 MB over 47.52 summed file-stream hours**, approximately **12.01 MB/hour** uncompressed. It contains 773,460 ticker messages, 453,331 market-trade messages, and 364 subscription messages. Overlapping file time is counted in that rate denominator; it is not unique wall-clock coverage. No full-depth channel appeared in any of the 176 Coinbase files.

Binary totals are the sum of `YES bid price × YES quantity` and `NO bid price × NO quantity`. They describe displayed purchase commitments for $1-payout event contracts. They are **not BTC units or a comparable perp notional/collateral measure**. Treating a NO bid as a YES ask is useful for a one-outcome book, but its complementary ask value is not additional independently funded liquidity to add again. Current code avoids that double count.

The 176 binary files total 3.515 GB and contain 13,534,604 deltas and 822,336 public trade messages, matching the previous independent inventory exactly. The displayed samples above are descriptive summaries of those existing records, not new historical-data availability claims.

## Recommended narrower study

The suggested center is **Kalshi BTC-perp full displayed L2 + public trades**, with **one lightweight BTC-USD spot reference**. There is no need to collect an additional full Coinbase book to answer the initial questions. Keep the 15-minute events as a separate historical method comparison if useful; their probability/expiry geometry is a different main problem.

For the spot reference, save the latest available **best bid, best ask, midpoint, last trade, source/receipt clocks, and quote age**, about **twice per second**. Best sizes and trade-volume/count aggregates per half-second are inexpensive optional context. Midpoint avoids some last-trade bid/ask bounce; quote age distinguishes repeated stale values from fresh observations. Subscribe to the regular ticker and save locally on a 0.5-second clock. Coinbase's `ticker_batch` is a different channel with five-second updates and no best bid/ask. Its ordinary ticker is trade-driven, so sampled ticker quotes do not establish complete quote-change coverage. This supports seconds-to-minutes market context, not millisecond lead/lag claims. One venue is a BTC reference, not the entire global market.

The two subtopics remain distinct despite sharing data:

| Study | Mathematical object | Bounded research question | Ordinary controls |
|---|---|---|---|
| 2: BTC feature engineering | Delay clouds of temporal states, initially midpoint returns with a small declared set of spread/imbalance/flow channels | Do persistence features distinguish oscillatory/choppy paths, directional moves, and changing activity after accounting for scale? | Volatility, autocorrelation, trend, spectrum, trade rate, spread/imbalance |
| 3: Liquidity organization | Displayed depth as a price-or-distance-by-time field; superlevel branches and, if justified, cubical features | How do concentrations, depleted regions, and replenishment reorganize during BTC moves? Do geometric summaries capture distinctions beyond ordinary depth/imbalance? | Depth bands, spread, gaps, imbalance, turnover and replenishment |

Preserve original quote coordinates and clocks so fixed-price versus midpoint-relative grids can be compared; a moving coordinate frame can itself change apparent shape. Match lookback information when comparing features. Share a dataset and comparison periods without claiming that the two feature families are independent or inevitably complementary. For prediction, choose a concrete target/horizon before tuning, and use genuinely later data.

This is a sufficient **scope and data representation** for the two mini-studies. Ten minutes is sufficient for plumbing and examples, not empirical conclusions about general market behavior or predictive usefulness. Obtain longer, varied episodes before evaluation; 100,000 correlated book messages are not 100,000 independent trials. No longer run or target selection has been inferred from this discussion.

Official references checked: [Kalshi snapshot/delta semantics](https://docs.kalshi.com/margin-ws/websockets/orderbook-updates), [Coinbase public feed channels](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-endpoints), and [Coinbase five-second ticker batch](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/websocket/ticker-batch).
