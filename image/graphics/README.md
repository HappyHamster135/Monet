# Task Manager's Graphics column

`ksysguard_plugin_monetgraphics` is a process-data plugin for KDE's process model
(`ksysguard/process`). It adds a **Graphics** attribute, each program's share of the
graphics card, which Monet's Applications and Processes pages show beside CPU and
Memory. KDE adds a program's processes up for its row in Applications.

The plugin measures nothing itself. While the column is in view it runs
`/usr/libexec/monet-graphics-use --watch` and reads one JSON line every two seconds,
`{"version": 1, "pids": {"1201": 7.0}}`. That helper reads AMD's and Intel's per-program
engine time (DRM fdinfo) and NVIDIA's report (`nvidia-smi pmon`, by column name). Once
the column is gone, the plugin stops the helper; nothing is measured in the background.
KDE's own NVIDIA plugin expects the column layout of drivers before 2023 and doesn't
cover AMD or Intel.

Build with `sh build.sh /out` in an image build stage with the native runtime. The
build refuses a changed runtime; `bundle.py install` verifies the runtime and checksums.
With `MONET_GRAPHICS_TESTING=1` it also runs `tests/graphics-column-test` through KDE's
own `ProcessDataModel`, with a stand-in helper. The source and build scripts are kept in
`source.tar.xz`.
