# WarpTwin Custom Models

A starting point for building your own WarpTwin models. This repository does
**not** build WarpTwin -- it compiles and SWIG-wraps the C++ models in `src/`
against a WarpTwin that is already installed on the machine, and produces a
`custom` Python package that sits alongside the installed `warptwin` one.

## References
- Detailed documentation on WarpTwin, including model documentation, can be found here: https://github.com/attx-engineering/warptwin-users-guide/blob/main/WarpTwin%20User's%20Guide.pdf
- WarpTwin is also equipped with an AI chatbot trained on its source code and user's manuals here: https://assist.warpware.co/

## Prerequisites

Ubuntu and macOS are both supported.

WarpTwin itself must be installed first. It ships as a signed release, not
through apt or Homebrew:

```
tar xzf warptwin-<version>-*.tar.gz
cd warptwin-<version>-*/
./install.sh
```

That gives you the headers, the libraries beside them, the `warptwin` Python
package, and `wt-gui`. Confirm it with `warptwin-doctor`. The two platforms use
different prefixes, which is worth knowing when you go looking for anything:

| | Ubuntu | macOS |
| --- | --- | --- |
| Headers | `/usr/include/warptwin` | `/usr/local/warptwin/include/warptwin` |
| Libraries | `/usr/lib/<triplet>/warptwin` | `/usr/local/warptwin/lib` |
| Data | `/usr/share/warptwin` | `/usr/local/warptwin/share/warptwin` |
| Python package | on the default `sys.path` | `/usr/local/warptwin/python`, added by a `.pth` file |

Then install the toolchain this repository needs to compile against it -- a C++
compiler, cmake, SWIG, and the Python and HDF5 development headers:

```
./install.sh
```

On Ubuntu that is apt; on macOS it is Homebrew, and it expects the Xcode Command
Line Tools (`xcode-select --install`) and `brew` to already be present, since
neither can be installed unattended.

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

cmake finds the installed WarpTwin itself, searching `/usr` and
`/usr/local/warptwin` among others, and prints what it found. If yours is
somewhere else, point cmake at the prefix:

```
cmake .. -DWARPTWIN_ROOT=/opt/warptwin
```

If the machine has several Python installations -- common on macOS, where a
Homebrew upgrade can move `python3` to a new minor version while the installed
WarpTwin stays on the old one -- pick the interpreter WarpTwin was installed
for. cmake warns at configure time when the one it picked cannot import the
installed `warptwin` package:

```
cmake .. -DPython3_EXECUTABLE=$(which python3.14)
```

Compile. `-j<n>` sets the number of cores to build with.

```
make -j$(nproc)                  # Ubuntu
make -j$(sysctl -n hw.ncpu)      # macOS
```

Run the unit tests. 100% of tests should always pass.

```
make test
```

## What the build produces

| Path | Contents |
| --- | --- |
| `build/libwarptwin-custom.so` (`.dylib` on macOS) | Your models, compiled and linked against WarpTwin |
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

Only the `custom` package needs this. The installed `warptwin` package is
already importable on both platforms -- on macOS through a `.pth` file that puts
`/usr/local/warptwin/python` on `sys.path`.

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

On macOS, the three examples that import `warptwinutils`
(`earth_observation`, `geo_transfer_impulsive`, `monte_carlo_sun_synchronous`)
fail with `ModuleNotFoundError`. That package is part of the WarpTwin release on
Ubuntu but is not currently staged into the macOS one, so it is missing from the
install rather than from here; the other thirteen examples run.

## Files vendored from the WarpTwin release

Some of what the build needs is not currently part of the installed package, so
copies matching the release live here and must be kept in step with the WarpTwin
version you are building against:

| Path | Why |
| --- | --- |
| `swig/WarpTwinPy.i`, `swig/*.swg`, `swig/swigtemplate.txt` | The shared SWIG interface and the model interface template |
| `python/buildutils/` | `BuildProcessFiles.py`, which generates a SWIG interface per model header |
| `includes/warptwin_sim/` | warpOS package headers (`types.h`, `configuration.h`, `SimLinux.h`, `SimPlatform.h`, `SimSetup.h`) included by bare name from the installed headers |
| `includes/thirdparty/` | `nlohmann/json.hpp` and `highfive/`, which the installed headers include by name. The Ubuntu package copies these trees in alongside its own headers; the macOS package does not |

The build prefers the installed copies of all of these when the install provides
them, and falls back to the vendored ones otherwise; cmake says which it used
for each.

The versions here have to be the ones WarpTwin itself was built against. Both
are header-only and their types cross into the compiled `libwarptwin`, so a
Homebrew `nlohmann-json` or `highfive` of a different version is not an
equivalent substitute even where it compiles.
