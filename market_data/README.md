# Alpaca market-data feasibility test

**November 4 equity context:** separate [QQQ daily and Cboe VIX history](datasets/mean_reversion_context_2026-11-04/README.md) support the [index sell-off reversal check](../equity/experiments/index_selloff_reversal/README.md). Alpaca's current official documentation excludes index values from Market Data despite VIX-option trading support; free Cboe VIX is saved with provenance and lagged research features. Original equity panels are unchanged.

**October 29 BTC collection:** see the [BTC source assessment](../btc/DATA_SOURCES.md) and [running log](../btc/BTC_RESEARCH_LOG.md) for the independently active BTC track. New [Binance prices/depth bands](datasets/btc_binance_2024_2026-10-27/README.md), [Kalshi perp minute history](datasets/btc_kalshi_2026-06_2026-10-27/README.md), and a [bounded Kalshi depth sample](samples/kalshi_btc_depth_2026-10-29/manifest.json) are saved separately. [Offline audit](datasets/btc_independent_audit.json). The remainder of this page documents the earlier Alpaca probes.

Read-only test completed October 12, 2026, using the supplied paper-account credentials. Credentials were entered through hidden prompts and were not saved. No orders were submitted and no balances or positions were requested.

In the later October 12 follow-up, the user requested retaining the paper credentials. They are now stored separately in `.alpaca-paper.local.json`, with owner-only mode `0600` and a `.gitignore` rule. The probe automatically loads this local file; credentials remain excluded from source, sample data, and research notes.

**Finding: Alpaca stocks provide trades and top-of-book quotes; Alpaca crypto also provides live multilevel order books. Liquidity-depth TDA is therefore not restricted to Kalshi.**

For the proposed small TDA studies, see the [current plan and data assessment](../START_HERE.md). Alpaca is a useful starting source for equity/BTC histories. The samples do not establish an authentic historical option-chain/IV panel, and Alpaca spot depth is distinct from Kalshi's newly documented perpetual-futures API. These are different feasibility questions.

## Files and reproduction

**October 28 expanded collection:** the [200-stock-plus-SPY daily panel](datasets/equity_daily_expanded_2016_2026-10-27/README.md) is now saved separately. It retains all original 30 names, uses a frozen top-200 eligible IVV-holdings size rule, and spans January 2016–October 27, 2026. Raw/all-adjusted histories each contain 526,828 bars, with 182 complete-history equities, 18 shorter leading histories, and no internal missing sessions. A SPY-only pre-2016 probe returned no bars. [Downloader](download_equity_expanded.py), [independent audit source](audit_equity_expanded.py), and frozen selection/provenance live with the new panel. This is current-survivor breadth, not historical point-in-time eligibility; no expanded-universe backtest has been run. Original prices match exactly and original files remain unchanged.

**October 28 equity download:** a complete [30-stock daily panel plus SPY](datasets/equity_daily_30_2016_2026-10-27/README.md) now covers January 4, 2016–October 27, 2026 (2,720 sessions; no missing bars). Raw and all-adjusted SIP OHLCV, close matrices, simple/log daily returns, original responses, and coverage checks are retained. [download_equity_daily.py](download_equity_daily.py) reproduces the pull. The 30-symbol Basic-plan limit concerns live streaming, not historical REST downloads. This fixed learning basket has survivorship/selection bias; it is not a point-in-time universe.

- [alpaca_probe.py](alpaca_probe.py): reusable probe with fixed paper/market-data hosts and GET-only HTTP requests.
- [samples/alpaca_2026-10-12/summary.json](samples/alpaca_2026-10-12/summary.json): endpoint results, status codes, counts, time windows, and pagination flags.
- [Stock quote example](samples/alpaca_2026-10-12/stock_sip_aapl_quotes.csv): historical consolidated bid/ask observations.
- [Crypto depth snapshot](samples/alpaca_2026-10-12/crypto_us_latest_orderbooks.csv): returned prices and quantities by side and rank.
- [Raw crypto stream](samples/alpaca_2026-10-12/crypto_us_stream.jsonl): received reset snapshots, book updates, quotes, and control messages.
- [Reconstructed crypto depth summaries](samples/alpaca_2026-10-12/crypto_us_stream_depth.csv): spread, level counts, and displayed quantity after each book message. The raw stream retains the actual depth needed for a price-by-time grid; these summary columns alone do not retain the shape.

From `Senior-Fall/TDA_Research`, activate `tda` and run:

```sh
conda activate tda
python market_data/alpaca_probe.py --out market_data/samples/alpaca_new_probe --seconds 15
```

The probe uses existing `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` environment variables, then the retained local credential file, then hidden prompts for any missing value. Use `--credentials-file` to select another local file. Keep credentials out of notebooks, source files, shell command arguments, and sample data. The script uses Python's standard library plus `websocket-client`, which was already installed in `tda`.

To repeat the small options-only probe:

```sh
python market_data/alpaca_probe.py --out market_data/samples/alpaca_options_new_probe --options-only
```

The paper trading base is `https://paper-api.alpaca.markets`. Actual market-data requests go to `https://data.alpaca.markets`; WebSocket data comes from `wss://stream.data.alpaca.markets`. Paper credentials can authenticate those data requests. This does not make the returned market observations simulated.

## What this account actually returned

The authenticated clock reported October 12 at 16:02:29 Eastern, just after the regular stock session closed. The script selected that day's completed session from Alpaca's calendar. Historical stock requests covered **09:30:00 through 09:35:00 Eastern**, with an inclusive end. Minute bars consequently include the 09:35 bar, yielding six rows per symbol rather than five.

Each historical tick request downloaded only its first page, with a 1,000-record limit. This is an access/schema probe, not a complete five-minute dataset. Use `next_page_token` to paginate before any research that needs all observations. Counts from truncated pages cannot be compared as trading intensities over the same interval.

| Test | AAPL | SPY | Interpretation |
|---|---:|---:|---|
| Historical IEX trades | 980 | 455 | Complete returned pages; no additional page token |
| Historical IEX quotes | 1,000 | 1,000 | Both truncated; additional pages exist |
| Historical SIP trades | 1,000 | 1,000 | Both truncated; additional pages exist |
| Historical SIP quotes | 1,000 | 1,000 | Both truncated; additional pages exist |
| IEX 1-minute bars | 6 | 6 | Inclusive endpoint includes 09:35 bar |
| SIP 1-minute bars | 6 | 6 | Same inclusive endpoint behavior |
| Latest IEX trades and quotes | HTTP 200 | HTTP 200 | Available with these credentials |
| Latest SIP trades and quotes | HTTP 403 | HTTP 403 | Subscription does not permit recent SIP data |

Historical consolidated access worked despite the restriction on current consolidated data. The [Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) explains that historical SIP requests ending at least 15 minutes ago can be queried without the live SIP subscription. The paper-account documentation has more general IEX-only entitlement language; the saved HTTP responses establish what worked for this particular account and interval.

Stock trade fields include price `p`, size `s`, exchange `x`, conditions `c`, trade ID `i`, and timestamp `t`. Quote fields include bid/ask prices `bp`/`ap`, sizes `bs`/`as`, exchange codes `bx`/`ax`, conditions, and timestamp. They contain **one bid and one ask per observation, not arrays of deeper price levels**. Preserve conditions, source exchanges, and original timestamp strings when analyzing them. Timestamp precision is not a guarantee about network latency or event completeness. Stock quote-size units should follow the applicable feed schema; do not assume they are interchangeable with crypto quantities.

The IEX quote sample had exchange code `V`; the SIP sample had multiple exchange codes. A single-exchange quote can be much wider than the consolidated market. Do not use an IEX bid/ask as a substitute for the national best prices when modeling broker execution. The [stock stream documentation](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data) describes these fields and channels.

## The crypto order-book result

The latest REST order-book endpoint returned:

| Symbol | Returned bid levels | Returned ask levels |
|---|---:|---:|
| BTC/USD | 91 | 100 |
| ETH/USD | 50 | 100 |

The **15-second live crypto stream** successfully authenticated and subscribed to trades, quotes, and `orderbooks` for both symbols. It delivered **58 book messages and 28 quotes**, with no trade messages during that short sample. Its initial reset snapshots contained:

| Symbol | Reset bid levels | Reset ask levels |
|---|---:|---:|
| BTC/USD | 91 | 129 |
| ETH/USD | 50 | 140 |

The REST and WebSocket snapshots were taken at different times. These observations establish multilevel depth access; they do not establish a fixed maximum depth or prove that REST and stream snapshots have identical coverage. In particular, do not assume the REST response is equivalent to the stream's complete server-side reset.

The [crypto stream schema](https://docs.alpaca.markets/us/docs/real-time-crypto-pricing-data) specifies:

- `T="o"`: order-book message.
- `b` and `a`: lists of price `p` and quantity `s` pairs.
- `r=true`: replace the local book with the supplied server-side snapshot.
- Later nonzero quantities replace the quantity at a price; they are not additive deltas. Zero quantities remove that price.

The probe applied those rules and retained all raw messages. Replaying them reproduced its final level counts. Its 58 recorded reconstructed states had no crossed best bid/ask. These checks do not establish reliability over long sessions, reconnects, or outages.

The stock IEX stream also authenticated and delivered **34 quote messages** in 15 seconds. It delivered no trade messages in that after-close sample, so this does not measure regular-session trade activity.

For historical crypto, a separate five-minute recent window returned **4 BTC trades, 3 ETH trades, 380 BTC quotes, and 286 ETH quotes**, without additional page tokens. Sparse trades on this venue are an important feasibility observation; they are not estimates of the activity of the whole crypto market. The sample tested the `us` feed, not the other documented crypto locations.

For future BTC bar-based experiments, note that the [crypto documentation](https://docs.alpaca.markets/us/docs/real-time-crypto-pricing-data) allows bars to include quote midpoints, including zero-volume bars. Audit the chosen series' construction before interpreting its prices as executions or its changes as trading intensity.

## Options follow-up: measured access

The [options sample](samples/alpaca_options_2026-10-12/summary.json) was collected October 12 at approximately 16:12 Eastern. Twelve read-only HTTP requests produced nine successes and three expected OPRA-access failures. No options order or account-approval change was attempted.

| Data | Measured result | Important limitation |
|---|---|---|
| Contract metadata | Four AAPL calls and four SPY calls | Small filtered sample, not an entire chain; more contract pages exist |
| Latest indicative trades | One record for each of eight contracts | Indicative trades are derived and delayed |
| Latest indicative quotes | One bid/ask observation for each of eight contracts | Quotes are modified derivatives of OPRA rather than actual exchange quotes |
| Indicative snapshots | Eight, all with Greeks and implied volatility | Presence does not independently validate the model values or market-price accuracy |
| Historical option trades | 1,000 records over the requested 09:30-09:35 interval | First page only, all AAPL in this page; additional pages exist |
| Historical 1-minute bars | 46 records across the eight contracts | Inclusive end includes 09:35; a contract need not have a bar for every minute |
| Latest official OPRA trades, quotes, and snapshots | All HTTP 403: `OPRA agreement is not signed` | Official current-feed access was not established; no agreement was accepted |

The four AAPL contracts expire October 14 with strikes 337.5, 340, 342.5, and 345. The four SPY contracts expire October 13 with strikes 774, 775, 776, and 777. Contract metadata also includes multiplier, style, tradability, open interest with its observation date, and prior close with its date. Those dates matter: open interest is not an instantaneous book-depth observation.

Useful files:

- [AAPL contracts](samples/alpaca_options_2026-10-12/options_contracts_aapl.csv) and [SPY contracts](samples/alpaca_options_2026-10-12/options_contracts_spy.csv).
- [Indicative quotes](samples/alpaca_options_2026-10-12/options_latest_indicative_quotes.csv).
- [Snapshots with Greeks and implied volatility](samples/alpaca_options_2026-10-12/options_indicative_snapshots.json).
- [Historical trades](samples/alpaca_options_2026-10-12/options_historical_trades.csv) and [minute bars](samples/alpaca_options_2026-10-12/options_historical_bars.csv).

The historical trades and bars endpoints do not expose a documented `feed` selector in the references reviewed; the probe did not supply one. Their successful responses should be reported separately from access to latest indicative or latest OPRA data. Historical access did not establish current OPRA access, and this short test did not independently audit historical-feed provenance.

Options prices across strikes and expirations could support a different TDA question about the shape of an options surface. They do **not** reveal deeper resting quantities for an individual contract. An options chain is a collection of different contracts, not an order-book depth ladder. For research on actual option liquidity or executable pricing consistency, modified indicative quotes are an unsuitable substitute for authentic quotes; the free sample is useful for testing data plumbing and representations.

Sources: [Historical options and indicative-feed definition](https://docs.alpaca.markets/us/docs/historical-option-data), [contract metadata](https://docs.alpaca.markets/us/reference/get-options-contracts), [latest option quotes](https://docs.alpaca.markets/us/reference/optionlatestquotes), [snapshots](https://docs.alpaca.markets/us/reference/optionsnapshots), [historical trades](https://docs.alpaca.markets/us/reference/optiontrades), [historical bars](https://docs.alpaca.markets/us/reference/optionbars). The original quote/trade stream test covered stocks and crypto; an options WebSocket stream was not tested.

## What this means for the TDA project

| Research question | Is stock L1 enough? | Suitable data |
|---|---|---|
| Does spread or displayed best-quote size deteriorate and recover? | Yes, for a top-of-book target | Alpaca stock quotes, trades, and appropriately defined baselines |
| Does the arrangement of gaps across price levels predict depth recovery? | No | A multilevel book stream, such as Alpaca crypto, Coinbase/Kraken, or Kalshi |
| What would a specified-size order cost when walking displayed depth? | No | Sufficient book coverage to cover that quantity; not necessarily every distant level |
| What is our exact passive-order queue position or fill probability? | L1 is insufficient; aggregate L2 is also insufficient for exact queue position | Requires order-level information and explicit matching/execution assumptions |

For the proposed **price-by-past-time liquidity image**, we need multiple price levels and reliable temporal reconstruction. Top-of-book quote history cannot recover orders at unobserved deeper prices. However, it is not automatically necessary to include every remote resting order: a predeclared near-market price band or top-N levels can support a local liquidity-recovery question. Measure boundary coverage and test sensitivity rather than interpreting missing observations as zero liquidity.

Alpaca crypto supplies aggregated displayed quantity at price levels on its specified venue/feed. It does not provide the entire cross-exchange crypto market, individual identities for orders at each level, hidden orders, or proof of execution at every observed price. The documented APIs reviewed here offer latest books and live book streams, rather than a historical depth replay endpoint. A depth-history study would therefore need ongoing recording or another archival dataset.

Kalshi event contracts remain attractive because their bounded binary price range and our existing book collector simplify some representations. These arguments concern event contracts, not the separate perpetual-futures product discussed in the current research notes. Kalshi is **one good option**, rather than a technical requirement for liquidity TDA. Coinbase/Kraken remain useful candidates if their trade/depth activity better supports repeated depletion and recovery episodes. Free stock-depth research is also possible with [IEX HIST](https://www.iex.io/products/market-data-connectivity); the historical files require decoding and concern IEX's displayed book. [DEEP+ inclusion in HIST](https://www.sec.gov/file/34-101782) documents order-by-order historical coverage.

For a pilot, choose a local liquidity region, define a depletion/recovery target, record resets and updates, retain exchange and receipt timestamps, resnapshot after reconnects, and compare topology against ordinary spread, depth, imbalance, gap, and duration predictors. Do not infer cancellation versus execution from a net book-size decrease alone.

## Order submission and paper simulation

Alpaca documents paper order submission at `POST https://paper-api.alpaca.markets/v2/orders`. This probe intentionally performed only data reads; it **did not test order submission or fills**. The AAPL and SPY asset endpoints returned `tradable=true`, which is instrument metadata rather than an account-level execution test. See [Working with orders](https://docs.alpaca.markets/us/docs/working-with-orders).

Paper simulation is useful for API plumbing. It is not a validation of liquidity-based execution: Alpaca's [paper documentation](https://docs.alpaca.markets/us/docs/paper-trading) says queue position, market impact, and latency slippage are not modeled, and submitted quantity is not checked against available NBBO quantity. A paper fill should not be used as evidence that the displayed book could execute that size in production.

## Validation and limits

- Authenticated paper clock and asset reads succeeded; 19 of 21 HTTP requests succeeded. The two expected failures were current SIP trades and quotes.
- Both WebSocket feeds authenticated; their raw received messages and subscriptions are saved without outgoing authentication payloads.
- Verified all 14 REST trade/quote/bar CSV counts against the summary.
- Replayed raw crypto reset/update messages and checked final counts, positive prices, nonnegative quantities, and uncrossed observed best prices.
- Approximately 2.53 MB of stock/crypto samples were saved in the original run. No credentials, account balances, positions, or account identifiers are included in the sample data. The later options samples and explicitly authorized private credential file are separate.
- This was a short access test, not a production collector, exhaustive entitlement audit, full historical download, or predictive experiment.

Subscription descriptions and schema references: [Market Data API plans](https://docs.alpaca.markets/us/docs/about-market-data-api), [crypto latest books](https://docs.alpaca.markets/us/reference/cryptolatestorderbooks-1), [stock trades](https://docs.alpaca.markets/us/reference/stocktrades-1), [stock quotes](https://docs.alpaca.markets/us/reference/stockquotes-1), [crypto trades](https://docs.alpaca.markets/us/reference/cryptotrades-1), [crypto quotes](https://docs.alpaca.markets/us/reference/cryptoquotes-1). Checked October 12, 2026.
