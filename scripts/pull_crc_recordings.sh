#!/bin/bash
# Run on your Mac. Pull the specific week-long Kalshi recording.
set -euo pipefail
umask 077

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
capture_run='2026-11-10T23-50-19Z-job-1724180'
source_archive="dshi2@crcfe01.crc.nd.edu:/users/dshi2/TDA-Research/market_data/recordings/crc/$capture_run/"
destination_archive="$repo_root/market_data/recordings/crc/$capture_run/"
options=(-rtvP --exclude=.collector.lock)
case "${1:-}" in
    '') ;;
    --dry-run) options+=(--dry-run) ;;
    --check) options+=(--dry-run --checksum --itemize-changes) ;;
    -h|--help)
        printf 'Usage: bash scripts/pull_crc_recordings.sh [--dry-run|--check]\n'
        printf 'Copy only run %s; retain partial transfers for retry.\n' "$capture_run"
        printf '%s\n' '--dry-run: preview copies without transferring files.'
        printf '%s\n' '--check: compare source/destination checksums without transferring files.'
        exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
esac
if [[ $# -gt 1 ]]; then
    echo 'Supply at most one option; see --help.' >&2
    exit 2
fi
command -v rsync >/dev/null 2>&1 || { echo 'rsync is required.' >&2; exit 2; }
mkdir -p "$destination_archive"
printf 'Source: %s\nDestination: %s\n' "$source_archive" "$destination_archive"
# No --delete or --remove-source-files. Trailing slashes copy the contents.
# Data is already gzip compressed; no additional transport compression needed.
rsync "${options[@]}" -e ssh "$source_archive" "$destination_archive"
printf '\nTransfer/comparison completed successfully.\n'
printf 'Copied files retain gzip compression; this does not certify a finished capture.\n'
printf 'Check the run manifest and any remaining .partial files before final validation.\n'
