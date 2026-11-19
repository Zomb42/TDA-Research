# Rules for AI assistants in this project

Read [README.md](README.md) first. The user's instructions in the conversation take precedence over this file. The full history behind these rules (October–November 2026) is in `_archive/root_docs/AGENTS_before_2026-11-18.md`.

## Environment

- Use the existing `tda` Conda environment (`/Users/derickshi/anaconda3/envs/tda/bin/python`). Do not use the base environment or create a new one. Installing extra packages into `tda` is allowed.
- Commit only when the user asks. Nothing has been pushed.

## Data and trading

- **Never submit, amend or cancel orders**, on any venue or paper account. Do not launch the user's old HFT trading executable. Use read-only, market-data-only tools.
- **No paid data, subscriptions, trials or paid hosting.** Free, public or already-entitled data only.
- **Credentials:** read them in place only when needed for authorized data access. Never print, copy or commit them.
- **No new data collection.** The user declared the November 10–17 Kalshi capture, plus the Binance files already downloaded, the final dataset (November 18, 2026). Do not start or restart any recorder without an explicit new request.
- **Keep the scope on BTC perpetuals and spot.** Do not substitute the Kalshi BTC 15-minute binary event contracts unless the user explicitly asks.
- Keep distinct: order-level (L3) against aggregated price-level (L2) data; live recording against historical backfill; documented access against tested, downloaded and replay-validated data.

## Research reporting

- Report performance **before fees** and say so. Spread crossing is a trading cost and is included where a strategy crosses it.
- Use only information available at the decision time: receipt times for order-book data.
- Show every TDA result next to a plain competitor built from the same inputs.
- Fix settings before seeing results; report every setting tried. Keep descriptive findings separate from predictive claims.
- Keep documentation short and plain, for a senior undergraduate in CS and applied math: define terms, avoid unexplained acronyms, give the reason for each statistical choice. Archive superseded notes rather than deleting them.
