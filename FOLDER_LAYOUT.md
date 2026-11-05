# Research folder layout

Organized October 28, 2026 at the user's request. The three topic folders hold the individual studies:

```text
TDA-Research/
  equity/       notebooks, equity notes, source scripts, and result directories
  btc/          BTC delay-geometry features, source assessments, and experiments
  liquidity/    depth-grid topology, historical-book preview, and experiments
  START_HERE.md shared project checkpoint and user preferences
  literature/   reviews and examples relevant to more than one study
  market_data/  shared data access code, private credential location, and downloads
  ttk_assets/   shared installed TTK runtime assets
```

General tutorials, playground notebooks, ParaView launchers, and the app remain shared at project root. The actual installed runtime under `~/ttk-binary` is unchanged.

Old equity notebook paths and old `experiments/` paths are **symbolic-link aliases**, not duplicate copies. This keeps existing IDE tabs and archived relative paths functional. Equity scripts were moved without editing their bytes, preserving the original frozen-source hashes. `equity/market_data` points to the existing shared data directory so those source scripts still resolve the same dataset. Credentials were not copied or inspected during this reorganization.

Primary navigation now uses topic paths. [organization_manifest.json](organization_manifest.json) records the moves and preserved script hashes. The main [README](README.md) and [checkpoint](START_HERE.md) link to the new locations.

On November 4, 2026, 279 audit-mirror symlinks pointing to the old absolute `TDA_Research` path were converted to relative links. Historical provenance files keep their original recorded paths. Bulk data stays local under the same dataset paths; see [repository/data setup](REPOSITORY_CLEANUP.md).
