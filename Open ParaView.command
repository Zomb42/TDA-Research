#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$project_dir/ttk_assets/ttk_env.sh"

if [ "$#" -eq 0 ]; then
    set -- "--state=$project_dir/ttk_assets/terrain_demo.pvsm"
fi
exec "$ttk_pv_root/Applications/paraview.app/Contents/MacOS/paraview" \
    "--plugins=$TTK_PLUGIN_PATH" "$@"
