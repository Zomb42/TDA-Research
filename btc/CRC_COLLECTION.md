# Collect Kalshi BTC perps on Notre Dame CRC

Prepared November 10, 2026. This setup records **KXBTCPERP** public L2 snapshots,
every delivered delta, public trades, and ticker context. No trading component
is used. The default collects Kalshi only; the previous lightweight Coinbase
reference is optional. Nothing was submitted to CRC or started on this Mac while
preparing these files. The completed November 5 archive and STOP marker are preserved.

## How the front end and compute nodes work

Log into a CRC front end, pull this repository, and submit
`qsub jobs/kalshi_btc_crc.job` **from the repository root**. Grid Engine queues the
job and runs it on a compute node when a slot is available. You can disconnect
SSH after submission. Running `bash jobs/kalshi_btc_crc.job` is not submission;
the script refuses to run without the scheduler environment.

Keep the first line exactly `#!/bin/bash`, with no `-l` argument. The CRC
`qsub` wrapper inspected on crcfe01 expands the complete shebang unquoted
after its `-S` option. A header of `#!/bin/bash -l` therefore adds a scheduler
`-l` option and causes the misleading submission error
`error opening BASH_ENV=/users/.../.bash_profile`. Conda initialization in
this job is explicit and does not require a login shell. For an older checkout
with that header, repair it on CRC before submitting:

```bash
sed -i '1c#!/bin/bash' jobs/kalshi_btc_crc.job
qsub jobs/kalshi_btc_crc.job
```

CRC documents a default single CPU for serial jobs and the `long` queue for
long-running jobs. The general-purpose `long` queue currently permits up to
14 days, with different limits possible on lab-owned equipment. This job uses
one CPU, collects for **seven days**, and requests a **168h10m hard limit** so
normal finalization happens before that deadline. It does not resubmit itself;
submit a new job for another run. Queue wait, reconnects, and resubmission can
leave gaps; there is no historical backfill here.

Sources checked November 10, 2026:
[batch submission, monitoring and cancellation](https://docs.crc.nd.edu/new_user/submitting_batch_jobs.html),
[front ends, storage, queues and modules](https://docs.crc.nd.edu/new_user/quick_start.html).

## One-time setup on CRC

1. Push the deployment files and their source dependencies from this checkout,
   then clone/pull on CRC. Include `jobs/`, this guide, the root `.gitignore`,
   `environment-crc.yml`, `market_data/requirements-capture.txt`, `record_btc_archive.py`,
   `record_kalshi_btc_stream.py`, `btc_archive_control.py`, `audit_btc_archive.py`,
   and the capture tests. Several recorder files are currently untracked locally;
   a plain `git commit -a` would omit them. Review `git status` before pushing;
   this checkout also contains unrelated research changes.
2. Recreate the portable **`tda` capture environment** on the CRC front end:

   ```bash
   bash jobs/setup_crc.sh
   ```

   The script finds an existing Conda installation, or loads CRC's `conda`
   module for this initial setup. It creates `tda` from `environment-crc.yml`
   (Python 3.13 and the collector dependencies), checks imports, runs the
   offline capture tests, and saves the actual activation path in the ignored
   `jobs/crc_conda.local.sh`. If `tda` already exists on CRC, it updates these
   dependencies without pruning unrelated research packages. It never edits
   your Mac environment, shell startup files, or the base environment, and it
   does not start collection. Run it again after dependency changes.

   The YAML is a portable capture recipe, not a copy of the full Mac research
   environment. It omits Mac build IDs and absolute paths; Conda installs Linux
   dependencies on CRC. Dependencies are pinned to the locally verified capture
   versions. See [Conda environment sharing](https://docs.conda.io/projects/conda/en/stable/commands/env/export.html).

   If your shell cannot find `module`, start a login Bash shell with `bash -l`,
   then run the setup command again. For a custom Conda installation, use
   `CONDA_SH=/actual/installation/etc/profile.d/conda.sh bash jobs/setup_crc.sh`.
   The setup must finish successfully before submission. There is no PyTorch/GPU
   dependency and no package installation inside the batch job.
   [CRC's Conda instructions](https://docs.crc.nd.edu/popular_modules/conda.html)
   describe initial module loading and activating saved environments in jobs.
3. Provision your existing Kalshi credential JSON (containing `key_id`) and
   matching RSA PEM through your usual secure transfer method, outside Git.
   By default the job reads `~/.config/kalshi/kalshi_credentials.json` and
   `~/.config/kalshi/private_key.pem`. Alternatively point it to existing files
   already on CRC. Git pull does not transfer these ignored secrets.
   Restrict their directory to your account and files to mode `600`.
4. Create your machine-specific configuration and edit the paths:

   ```bash
   cp jobs/crc_capture.example.sh jobs/crc_capture.local.sh
   chmod 600 jobs/crc_capture.local.sh
   # Edit jobs/crc_capture.local.sh with your editor.
   ```

   This local file is ignored by Git. It contains paths and settings; keys stay
   in their own files. Leave `CONDA_SH` commented out to use the path saved by
   setup. The job activates `tda` itself, including after a fresh SSH login.

## Storage limits

CRC's current guide specifies a **fixed 100 GB home-directory quota** under
`/users/netid`. It is an account/home allowance, not 100 GB reserved per compute
node. Other projects and environments share it. Check the actual allowance and
usage **on CRC before submission**:

```bash
quota
du -sh "$HOME"
```

Set `CAPTURE_TOTAL_GIB` below the remaining quota, leaving room for other work
and at least several GiB of headroom. For example, with 30 GB remaining, a
20 GiB budget consumes about 21.5 GB and leaves about 8.5 GB. **Do not use the
default 20 GiB budget if less than that plus headroom remains.** `du` measures
usage, not your quota; `quota` is the authoritative check. The program's free
space check sees the filesystem, which may report ample space even when your
personal quota is nearly exhausted. It does not automatically enforce your
account's remaining allowance or track unrelated jobs' writes.

| Setting | Default | Meaning |
| --- | --- | --- |
| `CAPTURE_SECONDS` | 604800 | Seven days; stop earlier at any other limit |
| `CAPTURE_MAX_GIB` | 20 | All files in the current run |
| `CAPTURE_TOTAL_GIB` | 20 | All runs under `CAPTURE_ROOT`, including earlier recordings |
| `CAPTURE_MIN_FREE_GIB` | 10 | Minimum free space on the underlying filesystem |
| `CAPTURE_ROOT` | `market_data/recordings/crc` | Persistent shared output folder |

Limits are checked before connecting and approximately every five seconds,
so output may exceed a cap slightly before shutdown. Compression is performed
as data arrives; no full uncompressed hour is staged. Nothing is automatically
deleted. A full archive stops later submissions before authentication until
you archive/move old data elsewhere or deliberately increase the budget.
Use the same `CAPTURE_ROOT` for all submissions so both the total cap and
duplicate-job lock cover them. Do not collect to node-local `$TMPDIR`, whose
contents may disappear after the job ends. If you change the output path,
keep it outside Git or add it to `.gitignore`.

The previous run used about 725 MiB compressed over roughly a day, including
interruptions. That is an observation, not a future storage guarantee.

## Submit and monitor

From the CRC checkout root, after the setup above:

```bash
git pull
qsub jobs/kalshi_btc_crc.job
qstat -u "$USER"
# Replace 12345 with the job ID printed by qsub:
qstat -j 12345
tail -f kalshi_btc.o12345
```

The combined scheduler log is unique per job and prints the hostname and
output path. Each job creates a fresh
`market_data/recordings/crc/<UTC-start>-job-<job-id>/` directory. Existing files
are never reused. An advisory `flock` on the shared archive folder prevents two
copies of this job from recording simultaneously; it releases on exit.

For an initial **two-minute compute-node smoke run**, submit with
`qsub -v CAPTURE_SECONDS=120 jobs/kalshi_btc_crc.job`. Leave `CAPTURE_SECONDS`
unset in the local config for this override, or temporarily change it there;
the local config takes precedence over inherited variables. Check for a fresh
`collecting` status and a received snapshot. On shutdown, check that
`manifest.json` reports `stopped` / `duration_completed` and there are no
`.partial` files. Then submit the normal seven-day job. A startup timeout or
feed failure produces a nonzero exit and a failed manifest; inspect its
per-feed state. Compute-node internet access, credentials, and the permitted
queue still need to be verified by this first CRC run.

Inspect or stop a specific run using its actual path:

```bash
source jobs/crc_conda.sh
initialize_crc_conda
conda activate tda
python market_data/btc_archive_control.py status --out market_data/recordings/crc/RUN_DIRECTORY
python market_data/btc_archive_control.py inspect --out market_data/recordings/crc/RUN_DIRECTORY
python market_data/btc_archive_control.py stop --out market_data/recordings/crc/RUN_DIRECTORY
```

Always pass `--out`: the default control pointer still refers to the old,
completed Mac archive. The stop command writes a STOP marker; allow a few
seconds for closure and check the manifest. `qdel 12345` cancels a queued job
or requests termination of a running job. The script requests Grid Engine
advance notification and handles its stop signals, but a hard kill, node
failure, or full quota can still leave `.partial` segments. Do not rename those
to pretend they are finalized. Grid Engine notification behavior is described
in the [upstream job guide](https://docs.oracle.com/cd/E19957-01/820-0699/chp5-19/index.html).

Optional email notifications can be added at submission:
`qsub -M "$USER@nd.edu" -m ae jobs/kalshi_btc_crc.job`.

If the job disappears from `qstat`, read `kalshi_btc.oJOB_ID` in the submission
directory. The November 10 attempt, job 1721365, reached compute node
`d32cepyc218` but reported `startup_failed` / `FileNotFoundError`; no healthy
capture was confirmed. A likely cause is a missing credential JSON or PEM:
Conda setup and Git pull do not provision either file. New versions of the job
check that credential paths are readable before launching Python and report
the specific missing path without printing secret contents. Correct the paths
in `jobs/crc_capture.local.sh` or securely provision the existing matching files
outside Git, then submit a new job. Preserve the failed attempt's log.

`qacct -j JOB_ID` can provide a finished job's accounting record when CRC
accounting is available. If it reports a missing accounting file, use the
scheduler log and saved run status/manifest instead; that accounting error
does not explain the recorder's startup failure.

## Output and validation

Each Kalshi UTC-hour file retains all delivered parsed book/trade/ticker
messages, receipt clocks, connection epochs, gap markers, and periodic exact
decimal book checkpoints. Rotation keeps the socket connected and carries
the pre-event book into the next file. The first and last hours may be partial
hours. Open files end in `.jsonl.gz.partial`; graceful rotation/shutdown writes
the gzip trailer, renames to `.jsonl.gz`, and writes SHA-256/count manifests.

For a finalized healthy run, validate every closed file offline:

```bash
python market_data/audit_btc_archive.py --out market_data/recordings/crc/RUN_DIRECTORY
```

The audit checks hashes, gzip integrity, row counts and exact book replay.
It reports observed interruptions and rejects detected book/trade sequence
gaps; a failed strict audit is evidence to inspect, not permission to erase
the run. Local offline deployment checks use:

```bash
python -B -m unittest discover -s tests -v
bash -n jobs/kalshi_btc_crc.job jobs/crc_capture.example.sh jobs/setup_crc.sh jobs/crc_conda.sh
```

To also collect the previous 2 Hz Coinbase BTC-USD quote/trade-aggregate
reference, set `CAPTURE_COINBASE=1` and `COINBASE_CREDENTIALS` in the local
config. This requires the existing supported ECDSA CDP key. It remains a
sampled reference, not a Coinbase full-depth archive. An enabled feed that
fails terminally stops the job so it does not silently consume a compute
slot collecting only the remaining feed.
