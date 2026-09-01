# WarpTwin Custom Models

A starting point for building your own WarpTwin models. This repository does
**not** build WarpTwin -- it compiles and SWIG-wraps the C++ models in `src/`
against a WarpTwin that is already installed on the machine, and produces a
`custom` Python package that sits alongside the installed `warptwin` one.

## References
- Detailed documentation on WarpTwin, including model documentation, can be found here: https://github.com/attx-engineering/warptwin-users-guide/blob/main/WarpTwin%20User's%20Guide.pdf
- WarpTwin is also equipped with an AI chatbot trained on its source code and user's manuals here: https://assist.warpware.co/

## Prerequisites

WarpTwin itself must be installed first. It ships as a signed release tarball,
not through apt:

```
tar xzf warptwin-<version>-*.tar.gz
cd warptwin-<version>-*/
./install.sh
```

That gives you the headers under `/usr/include/warptwin`, the libraries beside
them, the `warptwin` Python package, and `wt-gui`. Confirm it with
`warptwin-doctor`.

Then install the toolchain this repository needs to compile against it -- a C++
compiler, cmake, SWIG, and the Python and HDF5 development headers:

```
./install.sh
```

## Building

The build is cmake. Create a build directory, which will hold the binaries and
doubles as the Python path for the generated package.

```
mkdir build
cd build
```

Run cmake. It has to be re-run whenever:
- It is the first build of the repository
- Target files (`.h`, `.cpp`, `.i`) are added or removed
- The `.h` header file for a model or app is changed

```
cmake ..
```

If WarpTwin is installed somewhere other than `/usr` or `/usr/local/warptwin`,
point cmake at the prefix:

```
cmake .. -DWARPTWIN_ROOT=/opt/warptwin
```

Compile. `-j<n>` sets the number of cores to build with.

```
make -j$(nproc)
```

Run the unit tests. 100% of tests should always pass.

```
make test
```

## What the build produces

| Path | Contents |
| --- | --- |
| `build/libwarptwin-custom.so` | Your models, compiled and linked against WarpTwin |
| `build/custom/` | The `custom` Python package -- one module per model |
| `build/custom_models.json` | Model metadata for the GUI |
| `build/warptwin-custom_test` | The gtest binary `make test` runs |
| `build/swig_auto/` | Generated SWIG interfaces (regenerated on every cmake run) |

## Using your models from Python

Put the build directory on `PYTHONPATH` -- `.vscode/settings.json` and
`.vscode/launch.json` already do this for the integrated terminal and the
debugger -- and import your models beside the WarpTwin ones:

```python
from warptwin.WarpTwinPy import SimulationExecutive
from custom.SlopeIntercept import SlopeIntercept

exc = SimulationExecutive()
slope = SlopeIntercept(exc, "slope")
slope.params.m(2.0)
slope.params.b(3.0)
```

```
export PYTHONPATH=$PWD/build:$PYTHONPATH
```

## Using your models from the GUI

The build writes GUI metadata for every model it wraps. Point `wt-gui` at it:

```
wt-gui --custom-model-file=build/custom_models.json
```

## Adding a model

1. Add `YourModel.h` and `YourModel.cpp` under `src/models/`. `SlopeIntercept`
   is a complete, commented example of the pattern -- the `MODEL()` macro, the
   `START_PARAMS` / `START_INPUTS` / `START_OUTPUTS` blocks, and the
   `start()` / `execute()` / `activate()` / `deactivate()` overrides.
2. Add `test/test_YourModel.cpp`. Every `.cpp` under `test/` is compiled into
   the test binary automatically.
3. Re-run `cmake ..` so the SWIG interface for the new header is generated, then
   `make`.

Nothing needs to be registered anywhere. `cmake` globs `src/**/*.cpp` for the
library, `src/models`, `src/monitors` and `src/events` for headers to wrap, and
`test/**/*.cpp` for tests.

If a model needs wrapping the auto-generator cannot express, write the interface
by hand as `swig/YourModel.i` and it is built instead. `swig/WarpTwinPy.i` is not
one of those -- it is the shared interface every generated module includes, and
the installed `warptwin` package already ships the module built from it.

## Example scripts

`python/scripts/examples/` mirrors the examples shipped with WarpTwin. They use
only installed WarpTwin models, so they run without building anything:

```
cd python/scripts/examples
./run_all_examples.sh
```

## Files vendored from the WarpTwin release

Three things the build needs are not currently part of the installed package, so
copies matching the release live here and must be kept in step with the WarpTwin
version you are building against:

| Path | Why |
| --- | --- |
| `swig/WarpTwinPy.i`, `swig/*.swg`, `swig/swigtemplate.txt` | The shared SWIG interface and the model interface template |
| `python/buildutils/` | `BuildProcessFiles.py`, which generates a SWIG interface per model header |
| `includes/warptwin_sim/` | warpOS package headers (`types.h`, `configuration.h`, `SimLinux.h`, `SimPlatform.h`, `SimSetup.h`) included by bare name from the installed headers |

The build prefers the installed copies of the warpOS package headers when the
install provides them, and falls back to these otherwise; cmake says which it
used.
