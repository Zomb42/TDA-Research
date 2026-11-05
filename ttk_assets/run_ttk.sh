#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$project_dir/ttk_assets/ttk_env.sh"
exec "$ttk_pv_root/bin/pvpython" "$project_dir/ttk_assets/ttk_pipeline.py" \
    "$project_dir/ttk_assets/landscape.vti" "$project_dir/ttk_assets/results"
