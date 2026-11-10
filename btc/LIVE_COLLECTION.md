# BTC-perp data collection

**November 10 CRC deployment:** [job setup and commands](CRC_COLLECTION.md) ·
[Grid Engine job](../jobs/kalshi_btc_crc.job). Prepared for a new capture on CRC;
no new local collector or remote job was launched. The completed run below is preserved.

## Finalized continuous capture

**Stopped at the user's request on November 5, 2026 at 11:15:26 p.m. Indianapolis (November 6, 04:15:26 UTC).** Both feeds report stopped, the recorder PID no longer exists, the final run manifest is saved, all 52 gzip files are closed, and no `.partial` files remain. The STOP marker is retained. All 52 closed files passed hash, gzip and row-count validation; all 11,467 checkpoints and 25 carried hour-boundary books matched exact-decimal replay. The archive contains 21,694,928 book updates, 165,084 trade messages and 130,962 regular Coinbase samples, totaling 725.14 MiB compressed. Interruptions are retained. [Final completion report](experiments/btc_archive_final_2026_11_05/README.md). The recording spans approximately 24 hours 39 minutes in calendar time, with interruptions; it is not continuous gap-free market coverage. No restart is authorized.

The user subsequently authorized ongoing capture of **both Kalshi BTC perps and a lightweight Coinbase BTC reference**, with compression and hourly files. Started **November 4, 2026 at 10:36:50 p.m. Indianapolis (November 5, 03:36:50 UTC)**, using the existing `tda` environment and existing signing keys read in place.

- Completed run pointer: [ACTIVE_CAPTURE.json](ACTIVE_CAPTURE.json).
- Final stopped status: [status.json](../market_data/recordings/2026-11-05T03-36-49Z/status.json); its timestamp is the completion time and will no longer advance.
- Final run manifest: [manifest.json](../market_data/recordings/2026-11-05T03-36-49Z/manifest.json).
- Data directory: `market_data/recordings/2026-11-05T03-36-49Z/` (ignored by Git).
- Runtime: local detached process with temporary idle-sleep prevention; no login/boot service.
- Configured to stop on request, at **20 GiB of compressed archive**, or when free disk falls below **10 GiB**. This run stopped by request; no recorded history was deleted.

The [new recorder](../market_data/record_btc_archive.py) maintains two independent authenticated public market-data connections. Kalshi uses the same existing HFT RSA credentials as the sample. Coinbase uses the existing supported ECDSA CDP key in the HFT collector's `misc` directory, generating a fresh JWT per subscription/reconnect. No key, JWT, authorization header, order client, private account channel, paid source, or credential copy is stored in the archive.

**Kalshi:** all delivered `KXBTCPERP` public `orderbook_delta`/`trade`/`ticker` messages at `update_interval_ms=0`, with full parsed payloads, server/source timestamps, nanosecond receipt clocks, connection epochs, sequence validation and exact-decimal reconstruction. Full-book convenience checkpoints are saved about every five seconds. A discontinuity triggers a marked gap and fresh connection/snapshot.

**Coinbase:** normal BTC-USD ticker, market trades, and heartbeats are received; the saved reference targets **two rows per second**, including bid/ask, sizes, midpoint, ticker/last-trade prices, source and receipt clocks, quote age, and received trade count/BTC/USD aggregates since the preceding sample. Historical trade snapshots are not counted as new volume, and recent trade IDs are deduplicated. The full Coinbase L2 book and individual raw trade messages are intentionally not recorded for this reference. Missing sample intervals and connection/sequence gaps are explicit; samples represent information received locally, not exact exchange-time half-second bins or a complete quote-change feed.

**Hourly files:** each source has its own `YYYY-MM-DDTHH-00-00Z.jsonl.gz` files. The first hour is partial because capture starts mid-hour. Rotation is by UTC hour and **does not reconnect the network feeds**. A new perp segment includes a clearly labeled carried book anchor preceding its first event, enabling replay without reading the previous hour. An anchor is a saved local reconstruction, not a newly fetched exchange snapshot. Source/connection metadata and gap markers remain in the file.

Open files end in `.jsonl.gz.partial`; they are flushed/fsynced approximately every five seconds. On rotation or graceful stop they close, gain the final `.jsonl.gz` name and a per-file SHA-256/count/size manifest. A live prefix can be inspected before the gzip trailer exists; complete gzip CRC/hash validation waits for close. The source snapshots and runtime configuration are retained inside the ignored run directory.

```sh
conda activate tda
python market_data/btc_archive_control.py status
python market_data/btc_archive_control.py inspect
# When you want to end collection:
python market_data/btc_archive_control.py stop
```

The control tool uses `ACTIVE_CAPTURE.json` by default; `--out` can select another run. `stop` writes a stop marker so both feeds finalize gracefully without risking an unrelated reused PID. Inspect validates the latest file/prefix for each source, replays perp deltas independently against persisted checkpoints, and checks sampled reference midpoints. Offline tests cover a UTC-hour handoff with exact book state and Coinbase interval-volume accounting.

Keep the Mac awake and network-connected. Idle sleep is inhibited while this process runs; lid closure, forced sleep, shutdown, or network failure can still interrupt it. Reconnects are journaled and never presented as gap-free history. A single-feed failure marks the run degraded while the other feed may continue. The recorder is local and will not restart itself after shutdown.

## Earlier ten-minute example

User request, November 4, 2026: collect new BTC-perp data for feature engineering and liquidity, consulting the existing HFT C++ system. The clarified duration is **ten minutes only**. Use the existing **`tda` Conda environment**. No paid service or permanent process is installed.

**Latest storage preference:** keep this ten-minute sample **uncompressed** for direct inspection; use **lossless gzip for future recordings**. Future commands should include `--gzip`. Compression preserves every recorded event and does not imply downsampling the book. A [formatted preview](../market_data/samples/kalshi_btc_stream_2026-11-04_10min/data_preview.json) contains the first full snapshot, delta, trade, and ticker record. `market.json` is instrument metadata, not the event stream.

The [measured storage/depth/liquidity assessment](../liquidity/experiments/perp_capture_assessment_2026_11_04/README.md) compares this sample with the older HFT Coinbase and binary-event recordings. The subsequent continuous capture is documented above; the example itself remains unchanged.

## November 4 run

Dataset: [kalshi_btc_stream_2026-11-04_10min](../market_data/samples/kalshi_btc_stream_2026-11-04_10min/README.md).

**Completed and stopped:** November 4, 7:22:29–7:32:29 p.m. Indianapolis. The finalized manifest reports 600.15 seconds including startup/close. Captured **one full initial snapshot, 114,753 book deltas, 1,327 public trades, and 599 ticker messages**. Independent replay matched **all 119 full-book checkpoints**; all recorded counts and both completed-file hashes matched. There were **zero detected book/trade sequence gaps, reconstruction errors, connection failures, and duplicate trade IDs**. No recorder remains running from this request. The current uncompressed files total **39,770,212 bytes (37.93 MiB)**. Original gzip files totaled 3.86 MiB and are now retained only in the ignored provenance backup. Maximum observed ladders contained 160 bid levels and 110 ask levels. [Final replay report](../market_data/samples/kalshi_btc_stream_2026-11-04_10min/replay_validation.json).

- Instrument: Kalshi **`KXBTCPERP`**, a BTC perpetual, using the production perp WebSocket.
- Start: **November 4, 7:22:29 p.m. Indianapolis (EST)**, November 5 at 00:22:29 UTC. Planned end: ten minutes later. The process stops at its duration limit or earlier if its cap/access/disk checks require it.
- Read-only channels: `orderbook_delta`, `trade`, and `ticker`; books request real-time updates with `update_interval_ms=0`.
- Storage: **uncompressed JSONL**, a **512 MiB journal cap**, and a free-disk floor of 1 GiB. Checkpoints and small metadata are additional to the journal cap. Files are intentionally kept local under `.gitignore`. The run originally used lossless gzip; the original compressed files/manifests are preserved locally under `raw/original_gzip/` for provenance. Current manifests and replay hashes refer to the plain files.
- Runtime: `/Users/derickshi/anaconda3/envs/tda/bin/python`; temporary `caffeinate -i` prevents idle sleep only while the bounded process is running. Closing the lid, shutdown, forced sleep, or losing network can still interrupt capture.

The [status file](../market_data/samples/kalshi_btc_stream_2026-11-04_10min/status.json) records PID, fresh timestamp, received counts, errors, gaps, and deadline. A completed run writes a [manifest](../market_data/samples/kalshi_btc_stream_2026-11-04_10min/manifest.json); the independent [replay report](../market_data/samples/kalshi_btc_stream_2026-11-04_10min/replay_validation.json) is generated afterward. File freshness matters: an abruptly killed process can leave an old `collecting` status.

## What the files preserve

`messages.jsonl` contains every received application message before book processing, including initial/replacement snapshots, additive price-level deltas, public executions, ticker messages, subscription responses, and explicit connection/error controls. Each envelope preserves the full parsed server message, UTC receipt time, nanosecond Unix receipt time, monotonic receipt time, and connection epoch. Native exchange timestamps and sequence numbers remain in the original payload; no price bucketing or sampling is applied to the book feed. It is 39,105,403 bytes (37.29 MiB), with one JSON record per line.

`checkpoints.jsonl` contains reconstructed full bid/ask ladders at snapshots and approximately every five seconds. It is 664,809 bytes (0.63 MiB). These are convenience states: all intervening updates remain in the journal. Prices and quantities are replayed with exact decimals. A book gap invalidates a reconstruction epoch and triggers reconnect/fresh snapshot; reconnect intervals are missing data, never silently filled. Trades are retained separately as message events, not subtracted from the book a second time.

`market.json` preserves public instrument metadata. This run reports a **0.0001 BTC contract size**, underlying multiplier 1, and API price tick 0.0001. Given that metadata, contract counts × 0.0001 give BTC quantity, and API prices ÷ 0.0001 give the corresponding USD/BTC quote. Preserve original values and metadata instead of importing binary-contract cent or complementary Yes/No rules.

`ticker` adds delivered public price/top-of-book/volume/open-interest and optional reference/mark/funding context. Kalshi coalesces ticker updates to at most one per second; they are auxiliary context, not a replacement for the real-time book journal.

The first saved snapshot in this run contains **158 bid levels and 91 ask levels**. Received ticker payloads include reference price, settlement and liquidation mark prices, funding rate, open interest, and volume. These are access-tested fields in this capture; no forecast benefit is inferred.

**Depth boundary:** this is **aggregated public L2**—displayed quantity at each price and its changes. It cannot reveal hidden liquidity, the identities/queue positions of every resting order, or reliably classify every decrease as a cancellation versus execution. Public trades complement the book but do not turn it into individual-order L3. A successful replay establishes recorded-stream consistency, not independent exchange-wide completeness.

Official references checked November 4: [book snapshots/deltas and sequence recovery](https://docs.kalshi.com/margin-ws/websockets/orderbook-updates), [public trades](https://docs.kalshi.com/margin-ws/websockets/public-trades), [ticker fields/coalescing](https://docs.kalshi.com/margin-ws/websockets/market-ticker), and [perp connection/clock conventions](https://docs.kalshi.com/margin).

## Connection to the existing C++ system

Reviewed `Junior-Spring/HFT/Kalshi-Orderbook-Predictor/collector/`, particularly `kalshi_worker.hpp`, `csv_writer.hpp`, `orderbook.hpp`, `session.hpp`, and `src/main.cpp`. The corresponding `ND-HFTT/2026_spring/hft` worker is identical. The existing design already preserves raw messages before downstream processing and reconnects with refreshed signatures.

The original executable uses the event-contract host/path and a 15-minute contract scheduler, subscribes to private fills, and attaches market-maker logic. Its downstream `KalshiBook` is a 99-slot Yes/No array, unsuitable for decimal-priced perp bid/ask ladders. The raw writer preserves more precision than that downstream representation. We therefore reused the recording/signing approach through the existing isolated [perp recorder](../market_data/record_kalshi_btc_stream.py), without modifying/running the HFT executable or importing its trading components.

## Validate or repeat a bounded run

After this run finishes:

```sh
conda activate tda
python market_data/audit_kalshi_btc_stream.py \
  --out market_data/samples/kalshi_btc_stream_2026-11-04_10min
```

The validator independently reconstructs decimal price-level states, compares every saved checkpoint, checks sequence/error counts, verifies requested channel acknowledgments, and hashes both completed files. It supports plain JSONL and historical gzip recordings. It was checked against the earlier real 90-second probe and rejects a negative control with a deliberately removed delta. It requires a completed manifest and closed files.

Offline recovery regression check (no network or credentials):

```sh
python -B -m unittest discover -s tests -v
```

It simulates six recovered disconnects followed by a signal stop, verifies that seven fresh-snapshot epochs and all closed gap windows survive gzip/replay, and confirms that deleting a book update fails validation.

A future run requires a fresh output directory. The following is a manual recipe, not an automatically recurring job:

```sh
conda activate tda
python market_data/record_kalshi_btc_stream.py \
  --seconds 600 --max-mb 512 --gzip --include-ticker \
  --max-consecutive-errors 0 --out market_data/samples/NEW_UNIQUE_RUN
```

Credentials are read in place from the preexisting HFT secret files, never passed as values in command arguments or copied into outputs. The script signs a WebSocket GET and uses one public metadata GET; it has no order client or account/private subscriptions. Stop an active run with SIGTERM to the PID in its status file; the process finalizes its journals and manifest. Do not silently extend the current ten-minute authorization. Before longer unattended collection, add compressed segment rotation and test reconnect recovery under sustained outages.
