# Repository and local data

Cleanup performed November 4, 2026. Research conclusions, frozen experiment source, notebooks, and original data bytes were preserved.

## November 10 equity documentation cleanup

At the user's request, removed **15 ignored Python bytecode cache files**
(425,216 bytes) from the equity code/review folders and the equity downloader's
cache. These are generated `.pyc` files; the source scripts remain available.
No research dataset, result, notebook, experiment source or compatibility link
was removed.

Prepended **OUTDATED** notices to six documents, identifying the particular
status or proposal that has been superseded and linking to completed work:

| Document | What is outdated |
|---|---|
| [Earlier progress report](equity/EQUITY_PROGRESS_REPORT.md) | October 29 project summary omits research steps 16–23 |
| [Original PCA walkthrough](equity/EQUITY_INTUITION.md) | Initial next-step/holdout status; the original mathematical explanations remain useful |
| [Persistence/regime ideas](equity/PERSISTENCE_REGIME_IDEAS.md) | Proposal-stage status for experiments now completed |
| [Coordinate-design review](equity/literature/tda_regimes_and_coordinate_design_2026-10-29.md) | Earlier proposed next design and comparison status |
| [Regime/VIX review](equity/literature/tda_regimes_vix_2026-11-04/README.md) | Matched VIX/TDA comparison described as unexecuted; completed November 5 |
| [Alternative TDA uses](equity/literature/tda_alternative_uses_2026-11-05.md) | First two proposals now executed; remaining ideas are still unrun |

The [consolidated equity document](equity/EQUITY_RESEARCH_LOG.md) is the current
reading entry point. Navigation now identifies the archived notes and separates
the November 9 data vintage from October 27 experiment inputs. Review-provenance
metadata retains earlier hashes and records the documentation annotations.

Historical result reports and older dataset vintages were retained because they
are still the evidence for their stated periods. Their age alone does not make
their calculations outdated. Before/after SHA256 checks verified **all 768
snapshotted experiment/data/notebook files** were unchanged by this cleanup;
local links in the edited documents were checked.

## The three studies

| Study | Object and current evidence | Current boundary |
|---|---|---|
| [Equity](equity/README.md) | Stock relationships from correlation/PCA, H0 peer structures, residual-reversal tests, and regime comparisons. Broadest completed study; see the [running log](equity/EQUITY_RESEARCH_LOG.md). | Repeatable peer structure does not establish predictable reversal. No reliable incremental TDA trading gate is established; preserve gross/pre-fee reporting. |
| [BTC](btc/README.md) | Delay embeddings and H0/H1 features on controlled signals and 1,030 daily real-data windows. Standardization materially changes the relationship to volatility. | Descriptive feature interpretation, without a validated prediction target or held-out performance claim. |
| [Liquidity](liquidity/README.md) | Price-by-time depth grids, source-attributed superlevel H0 branches, and a historical-book replay preview. | Branch persistence measures depth contrast, not elapsed time. The bounded pilot does not demonstrate forecasting value. |

[START_HERE.md](START_HERE.md) remains the project context; this page records repository maintenance only. BTC historical full-depth access and new live capture are distinct activities. Existing free samples do not authorize paid access or continuous recording.

## Why the original push failed

The original sole commit, `43d0e7dfd1609f47a39b790dd743d93fdc4fdb66`, contained about 1,006 MiB of regular-file content. Two files exceed GitHub's [100 MiB file limit](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github):

- `market_data/samples/kalshi_btc_stream_2026-10-29_session01/messages.jsonl`: 143.63 MiB.
- `market_data/datasets/btc_deribit_2025-01-01/raw/incremental_book_L2.csv.gz`: 118.44 MiB.

Ignoring or deleting these in a second commit would leave them in the history sent to GitHub. The remote returned no branch or tag references before cleanup. A verified backup bundle was created outside the repository, then the unpublished initial commit was replaced with the cleaned tree. The backup is in `../TDA-Research-local-backup-2026-11-04/`; its inventory records original checksums and link targets. Keep that backup outside Git. No remote push was performed.

## What is local versus versioned

- Versioned: Python source, notebooks with existing outputs, figures, literature, specifications, dataset documentation, small samples/results, manifests, and audit reports.
- Local: raw download directories, source response pages, full equity price/return tables, Parquet histories, recording journals, and explicitly listed generated artifacts over 5 MiB. They remain at their original paths on this machine.
- Ignored: credentials, private key files, environments, Python caches, and notebook/OS caches.

[LOCAL_DATA_MANIFEST.json](LOCAL_DATA_MANIFEST.json) records the paths, byte counts, and SHA-256 hashes of the 832 research payloads removed from Git tracking, totaling 901.54 MiB. Nine Python cache files were also untracked. The original cache files remain local and can be regenerated.

The remaining original regular-file content is approximately 103.82 MiB, plus the small maintenance files added during cleanup. Git's compressed transfer size differs from these content totals. The old objects can still occupy local `.git` storage through the reflog; they are outside the new branch history and are not sent by a normal push. No aggressive garbage collection was performed.

The 279 stale absolute audit links now use relative paths. The fourteen existing compatibility links were retained. A fresh clone will need the omitted payloads restored before data-dependent links and archived audits can work.

## Working from a fresh clone

1. Use the existing **`tda` Conda environment** (user instruction, November 4): `conda activate tda`, then read [the tutorial/setup guide](TUTORIAL_GUIDE.md). The ParaView launcher uses separately installed packages under `~/ttk-binary`; those packages are not bundled here. Recorded BTC package versions are in [btc/environment_versions.json](btc/environment_versions.json); these are provenance, not a complete project lockfile.
2. Restore the omitted files at the paths in `LOCAL_DATA_MANIFEST.json` from a private copy when exact historical reproduction is required. Match their SHA-256 hashes. The external backup bundle also contains the original tracked payloads.
3. For newly obtained data, follow the corresponding dataset README and existing collectors in `market_data/`. Do not assume a new download reproduces frozen inputs: provider revisions, access, and market coverage can change. Restore credentials privately; never commit them.
4. Restore large generated artifacts from the private copy or follow their experiment's documented procedure. Reruns should use a new output location and preserve frozen reports and their provenance.

## Before future pushes

Stage the intended files, then run:

```sh
python3 scripts/check_git_size.py
git status --short
git push -u origin main
```

The size check examines the staged index and all blobs reachable from `HEAD`, using a conservative 5 MiB limit. It catches historical payloads even when a later commit deletes them. It does not inspect other branches or authenticate to GitHub. `.gitignore` handles known data patterns; any new large artifact needs its own exclusion before committing. The script is an explicit check, not an installed Git hook.

## Further useful cleanup

Use the existing `tda` environment rather than creating a replacement. A useful future improvement is exporting and checking a reproducible dependency manifest for that environment; the current package-version records do not provide a complete installable lockfile. Notebook builders also retain the old folder name in some workspace-root discovery candidates, and the audit mirror builder creates absolute symlinks on rerun. Those source changes should be made with an explicit provenance update; frozen research scripts were preserved during this cleanup.
