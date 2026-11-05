#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
paraview_root="$HOME/ttk-binary/ttk-paraview"
ttk_root="$HOME/ttk-binary/ttk"
export PYTHONPATH="$paraview_root/lib/python3.13/site-packages:$ttk_root/lib/python3.13/site-packages${PYTHONPATH:+:$PYTHONPATH}"
export DYLD_LIBRARY_PATH="$paraview_root/lib:$ttk_root/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
export TTK_MODULE_DIR="$ttk_root/lib/python3.13/site-packages/topologytoolkit"

exec /opt/homebrew/bin/python3.13 "$project_dir/ttk_assets/ttk_vtk_pipeline.py" \
    "$project_dir/ttk_assets/landscape.vti" "$project_dir/ttk_assets/results"
