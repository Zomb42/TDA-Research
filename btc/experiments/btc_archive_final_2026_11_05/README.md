# Finalized Kalshi BTC perpetual and Coinbase reference archive

**Stopped and finalized at the user's request.** Both feeds stopped gracefully on **November 05, 2026 at 11:15:26 PM Indianapolis time**. The recorder process exited, all **52 gzip files** are closed, and no `.partial` files remain. The STOP marker is retained; no restart is authorized.

## Recording and validation

| Item | Final result |
|---|---:|
| Started locally | November 04, 2026 at 10:36:50 PM |
| Stopped locally | November 05, 2026 at 11:15:26 PM |
| Calendar span | 24 hours 38 minutes |
| Final compressed journals | 725.14 MiB |
| Uncompressed journal bytes | 7,539,192,092 |
| Finalized files | 52 total, 26 per source |
| Kalshi book updates | 21,694,928 |
| Kalshi public trade messages | 165,084 |
| Independently replayed book checkpoints | 11,467 of 11,467 matched |
| Validated carried-book hour boundaries | 25 |
| Coinbase regular reference samples | 130,962 |
| Additional Coinbase disconnect snapshots | 36 |
| Additional Coinbase shutdown snapshot | 1 |
| Remaining open files | 0 |

The [full validation](final_validation.json) read every journal through its gzip trailer, checked SHA-256, total rows, per-message counts, file sizes and run counters, and independently replayed **every recorded Kalshi snapshot and delta with exact decimals**. All persisted book checkpoints and carried hour-boundary states matched. Public trade sequences were checked within connection epochs; 0 duplicate trade IDs were found. Reference quote midpoints and nonnegative recorded aggregate quantities were also checked.

The recorder's final `current_file` fields retain their last `.partial` names as historical status fields. The actual files have been renamed to completed `.jsonl.gz` files; directory checks confirmed none remain partial.

## Interruptions and coverage

This is a **calendar span**, not 24 hours of uninterrupted market coverage. The run's monotonic elapsed counter is 18.22 hours, which differs from wall-clock span. We do not assign a single cause to that difference from these counters alone.

- Kalshi recorded **51 connection errors**, 49 successful connections, and 48 explicit reconnect-gap windows. No recorded within-epoch book/trade sequence gap or reconstruction error was found.
- Coinbase recorded **36 connection errors**, 36 successful connections, and 35 explicit reconnect-gap windows. The 36 error-handling snapshots and 1 final shutdown snapshot are distinct from the 130,962 regular-sample counter.
- Across all reference snapshot rows, **155 observed intervals exceed two seconds**; the largest is **1068.68 seconds**. These capture pauses beyond explicit reconnect markers. Their total excess above nominal half-second spacing is 6.45 hours; this is a spacing diagnostic, not a certified usable-coverage estimate.
- **2532 quoted samples** have recorded quote age over two seconds. 128,441 rows are connected, uncrossed and within that quote-age bound, without establishing gap-free time coverage.

Gap windows and reference sample-spacing gaps remain in the validation JSON. A consistent replay verifies the captured stream; it cannot establish exchange-wide completeness during interruptions. Kalshi is aggregated displayed L2, while Coinbase is a sampled best-quote/trade-aggregate reference rather than a full book. No missing observations were filled and no raw history was deleted.

## Files and reuse

- [Completed-run pointer](../../ACTIVE_CAPTURE.json)
- [Collection guide](../../LIVE_COLLECTION.md)
- [Local archive directory](../../../market_data/recordings/2026-11-05T03-36-49Z/)
- [Final recorder manifest](../../../market_data/recordings/2026-11-05T03-36-49Z/manifest.json)
- [Full final validation and hashes](final_validation.json)
- [Offline validator source](../../../market_data/audit_btc_archive.py)

The raw archive remains losslessly compressed and ignored by Git. Keep the saved metadata and manifests with it. Existing feature-prediction and Reeb experiments retain their frozen input lists; finalization did not rerun them or promote the later recording into a holdout result. Use receipt-time availability, reconnect markers, quote ages and sampling gaps when selecting any future analysis interval. A new collection needs a new request.

Revalidate offline from the project root in the existing environment:

```sh
/Users/derickshi/anaconda3/envs/tda/bin/python market_data/audit_btc_archive.py
```

## Closed segment inventory

| Journal relative to the archive directory | Rows | Compressed MiB |
|---|---:|---:|
| kalshi_perp/2026-11-05T03-00-00Z.jsonl.gz | 232,067 | 8.14 |
| kalshi_perp/2026-11-05T04-00-00Z.jsonl.gz | 623,808 | 21.79 |
| kalshi_perp/2026-11-05T05-00-00Z.jsonl.gz | 721,622 | 24.83 |
| kalshi_perp/2026-11-05T06-00-00Z.jsonl.gz | 511,180 | 17.82 |
| kalshi_perp/2026-11-05T07-00-00Z.jsonl.gz | 580,192 | 19.90 |
| kalshi_perp/2026-11-05T08-00-00Z.jsonl.gz | 33,535 | 1.28 |
| kalshi_perp/2026-11-05T09-00-00Z.jsonl.gz | 3,597 | 0.21 |
| kalshi_perp/2026-11-05T10-00-00Z.jsonl.gz | 377,035 | 13.67 |
| kalshi_perp/2026-11-05T11-00-00Z.jsonl.gz | 433,067 | 15.74 |
| kalshi_perp/2026-11-05T12-00-00Z.jsonl.gz | 1,081,687 | 36.15 |
| kalshi_perp/2026-11-05T13-00-00Z.jsonl.gz | 902,727 | 30.77 |
| kalshi_perp/2026-11-05T14-00-00Z.jsonl.gz | 2,131,422 | 67.28 |
| kalshi_perp/2026-11-05T15-00-00Z.jsonl.gz | 3,252,465 | 101.05 |
| kalshi_perp/2026-11-05T16-00-00Z.jsonl.gz | 2,787,428 | 85.84 |
| kalshi_perp/2026-11-05T17-00-00Z.jsonl.gz | 871,582 | 27.34 |
| kalshi_perp/2026-11-05T18-00-00Z.jsonl.gz | 355,202 | 11.41 |
| kalshi_perp/2026-11-05T19-00-00Z.jsonl.gz | 1,019,355 | 32.84 |
| kalshi_perp/2026-11-05T20-00-00Z.jsonl.gz | 1,044,455 | 33.52 |
| kalshi_perp/2026-11-05T21-00-00Z.jsonl.gz | 1,644,896 | 51.33 |
| kalshi_perp/2026-11-05T22-00-00Z.jsonl.gz | 383,420 | 12.34 |
| kalshi_perp/2026-11-05T23-00-00Z.jsonl.gz | 187,091 | 5.64 |
| kalshi_perp/2026-11-06T00-00-00Z.jsonl.gz | 47,889 | 1.58 |
| kalshi_perp/2026-11-06T01-00-00Z.jsonl.gz | 137,370 | 4.47 |
| kalshi_perp/2026-11-06T02-00-00Z.jsonl.gz | 1,238,279 | 41.04 |
| kalshi_perp/2026-11-06T03-00-00Z.jsonl.gz | 1,064,978 | 35.62 |
| kalshi_perp/2026-11-06T04-00-00Z.jsonl.gz | 270,890 | 9.03 |
| coinbase_reference/2026-11-05T03-00-00Z.jsonl.gz | 2,781 | 0.30 |
| coinbase_reference/2026-11-05T04-00-00Z.jsonl.gz | 7,200 | 0.75 |
| coinbase_reference/2026-11-05T05-00-00Z.jsonl.gz | 7,201 | 0.80 |
| coinbase_reference/2026-11-05T06-00-00Z.jsonl.gz | 7,201 | 0.77 |
| coinbase_reference/2026-11-05T07-00-00Z.jsonl.gz | 7,201 | 0.79 |
| coinbase_reference/2026-11-05T08-00-00Z.jsonl.gz | 7,201 | 0.76 |
| coinbase_reference/2026-11-05T09-00-00Z.jsonl.gz | 7,201 | 0.77 |
| coinbase_reference/2026-11-05T10-00-00Z.jsonl.gz | 7,200 | 0.75 |
| coinbase_reference/2026-11-05T11-00-00Z.jsonl.gz | 7,201 | 0.74 |
| coinbase_reference/2026-11-05T12-00-00Z.jsonl.gz | 7,201 | 0.79 |
| coinbase_reference/2026-11-05T13-00-00Z.jsonl.gz | 7,201 | 0.78 |
| coinbase_reference/2026-11-05T14-00-00Z.jsonl.gz | 6,201 | 0.72 |
| coinbase_reference/2026-11-05T15-00-00Z.jsonl.gz | 6,404 | 0.80 |
| coinbase_reference/2026-11-05T16-00-00Z.jsonl.gz | 5,282 | 0.66 |
| coinbase_reference/2026-11-05T17-00-00Z.jsonl.gz | 2,410 | 0.28 |
| coinbase_reference/2026-11-05T18-00-00Z.jsonl.gz | 1,490 | 0.16 |
| coinbase_reference/2026-11-05T19-00-00Z.jsonl.gz | 4,034 | 0.50 |
| coinbase_reference/2026-11-05T20-00-00Z.jsonl.gz | 3,999 | 0.48 |
| coinbase_reference/2026-11-05T21-00-00Z.jsonl.gz | 5,752 | 0.65 |
| coinbase_reference/2026-11-05T22-00-00Z.jsonl.gz | 2,978 | 0.29 |
| coinbase_reference/2026-11-05T23-00-00Z.jsonl.gz | 491 | 0.04 |
| coinbase_reference/2026-11-06T00-00-00Z.jsonl.gz | 297 | 0.02 |
| coinbase_reference/2026-11-06T01-00-00Z.jsonl.gz | 748 | 0.08 |
| coinbase_reference/2026-11-06T02-00-00Z.jsonl.gz | 7,200 | 0.85 |
| coinbase_reference/2026-11-06T03-00-00Z.jsonl.gz | 7,201 | 0.82 |
| coinbase_reference/2026-11-06T04-00-00Z.jsonl.gz | 1,856 | 0.21 |
