# Active bounded BTC-perp data capture

Started October 29, 2026 using [record_kalshi_btc_stream.py](../../record_kalshi_btc_stream.py). Check [status.json](status.json) for the latest state and OS process ID. Planned duration: **3,600 seconds**; raw-journal cap: **512 MiB**. Either limit stops the recorder. No permanent service or automatic restart is installed.

Only two market-data channels are subscribed: `orderbook_delta` in real-time mode and `trade`, for `KXBTCPERP`. The process contains no order API/client or trading strategy, and sends no order submissions, amendments or cancellations. Existing HFT credentials are read in place, excluded from command arguments/logs/outputs, and not copied.

`messages.jsonl` retains raw server messages inside receipt-time/connection-epoch envelopes. `checkpoints.jsonl` stores exact-decimal reconstructed books every approximately five seconds and at snapshots. Trade events are retained separately from book updates; they are not subtracted from depth a second time. A gap or invalid quantity ends that reconstruction epoch and triggers reconnect/resnapshot.

The running `status.json` is updated periodically; `manifest.json` is written when the bounded process ends. Check file freshness as well as its state. The host must remain awake and network-connected. To stop earlier, send `SIGTERM` to the PID in status; the recorder writes a final status/manifest. Raw messages already captured remain on disk.

The [completed 90-second probe](../kalshi_btc_stream_2026-10-29_probe/manifest.json) recorded 26,250 deltas and 203 trades with no sequence errors. Its [18 checkpoints passed exact replay](../kalshi_btc_stream_2026-10-29_probe/replay_validation.json). These probe checks do not guarantee future uptime or prove exchange-wide completeness.
