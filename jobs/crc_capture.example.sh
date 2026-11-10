# Copy to jobs/crc_capture.local.sh ON THE CRC MACHINE and edit paths.
# This file contains settings only; signing credentials stay outside the repo.
# setup_crc.sh saves the actual Conda path automatically. Override only if needed:
# CONDA_SH="/actual/conda/installation/etc/profile.d/conda.sh"
KALSHI_CREDENTIALS="$HOME/.config/kalshi/kalshi_credentials.json"
KALSHI_KEY="$HOME/.config/kalshi/private_key.pem"
CAPTURE_ROOT="$PWD/market_data/recordings/crc"
CAPTURE_SECONDS=604800       # Seven days, below the job's 168h10m hard limit.
CAPTURE_MAX_GIB=20           # Current run, all output files.
CAPTURE_TOTAL_GIB=20         # All runs under CAPTURE_ROOT combined.
CAPTURE_MIN_FREE_GIB=10      # Filesystem free-space floor; NOT your quota.
CAPTURE_STARTUP_TIMEOUT=120  # Fail if the feed never becomes healthy.
CAPTURE_COINBASE=0
# To also retain the previous lightweight 2 Hz BTC-USD reference:
# CAPTURE_COINBASE=1
# COINBASE_CREDENTIALS="$HOME/.config/coinbase/cdp_api_key.json"
