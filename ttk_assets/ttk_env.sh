# Shared runtime settings for this Mac's TTK 1.4 / ParaView 6.1.1 packages.
# Source this file from a launcher; these settings only affect that process.
ttk_pv_root="$HOME/ttk-binary/ttk-paraview"
ttk_filter_root="$HOME/ttk-binary/ttk"
ttk_graphviz_root="$HOME/ttk-binary/compat/graphviz-15.1.1"

if [ ! -f "$ttk_graphviz_root/lib/libcgraph.8.dylib" ]; then
    echo "Missing TTK compatibility libraries: $ttk_graphviz_root" >&2
    exit 1
fi

export PATH="$ttk_pv_root/bin:$ttk_filter_root/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export DYLD_FRAMEWORK_PATH="/opt/homebrew/Frameworks"
export DYLD_LIBRARY_PATH="$ttk_graphviz_root/lib:$ttk_pv_root/lib:$ttk_filter_root/lib"
export PYTHONPATH="$ttk_pv_root/lib/python3.13/site-packages:$ttk_filter_root/lib/python3.13/site-packages"
export PV_PLUGIN_PATH="$ttk_filter_root/bin/plugins"
export TTK_PLUGIN_PATH="$ttk_filter_root/bin/plugins/TopologyToolKit/TopologyToolKit.so"
export QT_PLUGIN_PATH="/opt/homebrew/opt/qt@5/plugins"
unset PYTHONHOME
