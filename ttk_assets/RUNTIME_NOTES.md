# Working runtime on this Mac

Verified October 1, 2026: ParaView 6.1.1 opens with the full TTK 1.4.0 plugin, the desktop Morse–Smale filter runs on `landscape.vti`, and `run_ttk.sh` completes the persistence/Morse–Smale pipeline.

The Finder entry point is `../ParaView TTK.app`, also linked from `~/Applications/ParaView TTK.app`. It invokes `../Open ParaView.command`, which loads `terrain_demo.pvsm`. The original packages are under `~/ttk-binary/ttk-paraview` and `~/ttk-binary/ttk`; preserve those folders.

Opening the downloaded `paraview.app` directly does not apply the runtime environment. The October 1 02:57 and 02:58 crash reports show a missing `@rpath/libpqApplicationComponents-pv6.1.1.dylib` and no LC_RPATH. The `/usr/local` copy also retains download quarantine. Use **ParaView TTK.app** for Finder launches; it was tested through macOS Launch Services with the saved terrain and TTK filter visible. The wrapper's source is `paraview_launcher.c`; it is compiled locally and ad-hoc signed. No additional quarantine changes were made for this launcher repair.

## Compatibility settings

- The downloaded binaries reference Python 3.13 under `/Library/Frameworks`. `DYLD_FRAMEWORK_PATH=/opt/homebrew/Frameworks` resolves this to the existing Homebrew Python 3.13. No binary patch is required by the final setup.
- TTK's PlanarGraphLayout library requires `libcgraph.8.dylib`. Homebrew Graphviz 16.1.0 supplies `libcgraph.10.dylib`. A separate Graphviz 15.1.1 build supplies compatible Graphviz libraries under `~/ttk-binary/compat/graphviz-15.1.1`. Homebrew's installed version is unchanged.
- `ttk_env.sh` sets these paths only for the launched process. The full plugin is explicitly loaded from `~/ttk-binary/ttk/bin/plugins/TopologyToolKit/TopologyToolKit.so`.
- The extracted TTK/ParaView packages had their download quarantine removed with the user's authorization earlier in setup. This was limited to those package directories.
- `segmentation.vti` is the correct output extension because this pipeline preserves the image-data input geometry.

## Graphviz source and build

Source: the official [Graphviz source releases](https://graphviz.org/download/source/), version 15.1.1. The downloaded archive's SHA-256 was verified against its published `.sha256` file.

Build prefix: `~/ttk-binary/compat/graphviz-15.1.1`. Compiler: Apple Clang. Configuration used shared libraries, disabled SWIG bindings and optional image/UI integrations, and retained Graphviz's layout plugins. To work with this Mac's Command Line Tools layout, CXXFLAGS included `-isystem /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include/c++/v1`.

The source and build logs were staged in `/private/tmp/graphviz-15.1.1` and `/private/tmp/ttk-graphviz-*.log`; they are not needed to run the installed compatibility libraries. Keep the prefix under `~/ttk-binary/compat`.
