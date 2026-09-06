# WarpTwin Custom Models — working guide

This repository is the **custom-model workspace** for WarpTwin. It does not build
WarpTwin. It compiles and SWIG-wraps the C++ models in `src/` against a WarpTwin
that is already installed on the machine, and produces a `custom` Python package
that sits alongside the installed `warptwin` one.

Two kinds of work happen here, and this guide is organized around them:

1. **Python simulation scripts** — assembling built-in and custom models into a
   scenario, running it, and analyzing the output.
2. **C++ models** — new vehicle subsystems, sensors, actuators, or GN&C
   algorithms that become first-class citizens of the simulation.

## What WarpTwin is, and why the WarpWare stack matters

WarpTwin is WarpWare's simulation engine for space mission design, GN&C
development, and flight-software test and verification. It propagates the 6-DOF
state of one or more rigid bodies through a modeled space environment, with
high-precision ephemerides and time from NAIF SPICE, and lets you instrument,
perturb, and analyze that propagation.

The reason to build here rather than in a general-purpose ODE stack is that the
whole WarpWare toolchain shares **one model contract** — `params` / `inputs` /
`outputs`, `start()` / `execute()`. That single interface is what makes the
following progression possible without rewriting the algorithm at each stage:

| Stage | Where the logic lives | What you get |
| --- | --- | --- |
| Prototype | Python, driving `exc.step()` in a loop | Fastest iteration on a control law |
| Productionize | A custom C++ model in this repo | Full speed, reusable across scenarios, appears in `wt-gui` |
| Verify | Real flight software in the loop (WarpOS app or your own code) | The code that flies, exercised against the simulated vehicle |

Everything a model exposes is addressable, loggable, and connectable, so the same
scenario also feeds **MultiBodyViz** (browser-based 3D visualization),
**WarpLink** (a ground operator driving a running simulation as they would a real
vehicle), and the built-in Monte Carlo dispersion engine — with no extra
plumbing on your side. A custom model you write here is usable from a Python
script, from the GUI, and by flight software in the loop, because it obeys the
same contract as everything WarpWare ships.

WarpTwin is *not* a real-time OS, a ground system, a flight computer, or an
orbit-determination product. It propagates trajectories you define; it does not
estimate them from tracking data.

## Where authority lives

When sources disagree, trust them in this order:

1. **The installed C++ headers** (`<prefix>/include/warptwin/`). These are the
   complete, exact interface to every model: every signal with its type,
   default, and Doxygen comment. Read the header before asserting what a model's
   signals are — do not guess from the model's name.
2. **The Doxygen reference**, generated from those headers.
3. **`WarpTwin_Users_Manual.pdf`** in this repo — the tutorial and conceptual
   reference. Chapter numbers are cited throughout this file.
4. **This file** and `README.md`.

`WarpAssist` (https://assist.warpware.co/) is a good first stop for "how do I…"
questions, but confirm anything it says about an interface against the header.
Support: support@warpware.co.

## Repository layout

| Path | Contents |
| --- | --- |
| `src/models/` | Your models — one `.h` and one `.cpp` each. `SlopeIntercept` is the worked example |
| `src/monitors/`, `src/events/` | Also scanned for SWIG wrapping (create as needed) |
| `test/` | GoogleTest cases. Every `.cpp` here is compiled into the test binary automatically |
| `swig/` | Hand-written SWIG interfaces plus the shared `WarpTwinPy.i` and the generator template |
| `python/buildutils/` | `BuildProcessFiles.py`, which renders a SWIG interface per model header |
| `python/scripts/examples/` | 16 runnable example simulations mirroring those shipped with WarpTwin |
| `includes/warptwin_sim/`, `includes/thirdparty/` | Headers vendored from the release, used **only** when the install does not carry them (cmake reports which) |
| `build/` | Created by you; doubles as the Python path for the generated package |

Nothing needs registering anywhere. cmake globs `src/**/*.cpp` into the library,
`src/models`, `src/monitors` and `src/events` for headers to wrap, and
`test/**/*.cpp` for tests.

## Build, test, run

WarpTwin must already be installed (`warptwin-doctor` confirms it). Then:

```bash
./install.sh                 # toolchain only: compiler, cmake, SWIG, Python + HDF5 headers
mkdir build && cd build
cmake ..
make -j$(nproc)              # Ubuntu
make -j$(sysctl -n hw.ncpu)  # macOS
make test                    # 100% is expected to pass, always
```

cmake prints where it found the install, which Python it will use, and whether
each vendored header set came from the install or from `includes/`. Read that
output — it is the fastest diagnosis of a mis-detected environment.

**Re-run `cmake ..` when:** it is the first build; a `.h`/`.cpp`/`.i` is added or
removed; **or a model's header changes.** The last one matters and is easy to
forget — SWIG interfaces are regenerated at *configure* time, so a plain `make`
after editing a header compiles the new C++ against the *old* wrapper and fails
with confusing errors in `*PYTHON_wrap.cxx`.

Useful overrides:

```bash
cmake .. -DWARPTWIN_ROOT=/opt/warptwin              # install in a non-standard prefix
cmake .. -DPython3_EXECUTABLE=$(which python3.14)   # match the interpreter WarpTwin was built for
```

The installed extension modules carry no ABI tag in their filenames, so a
mismatched Python cannot fall back to anything — it simply fails to import.
cmake warns at configure time when the interpreter it picked cannot
`import warptwin`.

Build products: `build/libwarptwin-custom.so` (`.dylib` on macOS), `build/custom/`
(the Python package), `build/custom_models.json` (GUI metadata),
`build/warptwin-custom_test`, `build/swig_auto/` (generated interfaces).

To use the models: put the build directory on `PYTHONPATH` (`.vscode/settings.json`
and `launch.json` already do this). The installed `warptwin` package is already
importable; only `custom` needs the path.

```bash
export PYTHONPATH=$PWD/build:$PYTHONPATH
wt-gui --custom-model-file=build/custom_models.json   # your models in the GUI
```

---

# Writing Python simulation scripts

## Units and naming — the most common source of wrong answers

WarpTwin is unit-agnostic internally; it does arithmetic on the numbers you give
it. Everything built-in uses **SI base units**: meters, m/s, seconds, **radians**,
kilograms, N, Nm, W.

> A semimajor axis of `7000` is seven kilometers — deep inside the Earth — not a
> 622 km orbit. Multiply degrees by `DEGREES_TO_RADIANS`. This is the single most
> common first-time mistake; check it before debugging anything else.

Dynamic quantities are named `descriptor_item_referencepoint__representation`.
`pos_sc_pci` is "position of the spacecraft relative to the planet-centered
inertial point, expressed in PCI". Where reference and representation frames are
the same, the trailing `__representation` is dropped.

## The skeleton, and why the order is load-bearing

Almost every script has these seven parts in this order. Several steps depend on
earlier ones having happened.

```python
import sys
from warptwin.WarpTwinPy import SimulationExecutive, Hdf5Logger, DEGREES_TO_RADIANS
from warptwin.SpicePlanet import SpicePlanet
from warptwin.Spacecraft import Spacecraft

# 2. Executive
exc = SimulationExecutive()
exc.setRateHz(10)                              # or setRateSec; integrator(4)=RK4 default, 1=Euler
exc.args().addDefaultArgument("end", 5400)     # MUST precede parseArgs
exc.parseArgs(sys.argv)

# 3. World — order irrelevant; every body gravitates on every vehicle automatically
earth = SpicePlanet(exc, "earth")

# 4. Vehicles and models — distinct, meaningful names; they become addresses
sc = Spacecraft(exc, "sc")
sc.params.planet_ptr(earth)
sc.params.mass(200.0)

# 5. Wiring (see below)

# 6. Logging and visuals
log = Hdf5Logger(exc, "states.h5")
log.addParameter(exc.time().base_time, "t")
log.addParameter(sc.outputs.pos_sc_pci, "pos")
exc.logManager().addLog(log, 1)                # int = Hz, Time(60) = period

# 7. startup() -> initial states -> run()
exc.startup()
sc.initializeFromOrbitalElements(6778137.0, 0.001, DEGREES_TO_RADIANS*51.6, 0.0, 0.0, 0.0)
exc.run()
```

Ordering rules that will silently give wrong results if broken:

- **`params` and all pointer wiring go before `startup()`.** Changing a param
  after startup has undefined effect.
- **Initial vehicle states go after `startup()`** — whether you call `run()` or
  step by hand. They are defined relative to frames that only exist once startup
  has placed the frame tree.
- **`addDefaultArgument` before `parseArgs`.** After it, the arguments have
  already been read and the call does nothing for that run.
- Loggers lock their column set at `startup()`; add every parameter first.

`startup()` registers visuals and checks the license, loads SPICE kernels, starts
every planet (which elects the central body), runs `start()` on every other
scheduled unit in registration order, then re-synchronizes planet frames.

## Signals: reading, writing, and connecting

Every configurable or observable quantity is a **signal**. Read it by calling with
empty parentheses; write it by calling with a value:

```python
m = sc.params.mass()        # read
sc.params.mass(12.5)        # write
```

Signals are deliberately **read-only as Python attributes** — `sc.params.mass = 12.5`
raises `AttributeError: property 'mass' … has no setter`. That is intentional: a
signal is a fixed position on the graph tree, and assignment would replace the
object rather than set the value it holds. Always use the call operator.

There are **two distinct ways** to connect models, and they are not
interchangeable:

```python
# Pointer configuration — a frame, planet, or model handle. Set ONCE, by value,
# before startup(). Note the trailing () — you pass the current value.
eom.params.spacecraft_frame(sc.outputs.body())
sc.params.planet_ptr(earth)

# Signal connection — an input that must track an output every step.
# Note there are NO parentheses: you pass the signal objects themselves.
from warptwin.WarpTwinPy import connectSignals
connectSignals(planet_relative.outputs.altitude,   # upstream output
               atmosphere.inputs.altitude)         # downstream input
```

One output may fan out to many inputs; a given input should be driven by only one
output.

## Finding signal addresses

Every signal and frame has a dotted address rooted at the executive, e.g.
`.exc.sc.outputs.pos_sc_pci`. Addresses are how you log something buried in a
sub-model, and how WarpLink injects values into a running simulation.

```python
exc.search("altitude_detic")     # -> ('.exc.sc.outputs.altitude_detic',
                                 #     '.exc.sc.planet_rel.outputs.altitude_detic')
exc.searchSimTree("thruster")    # models only
exc.searchFrameTree("lvlh")      # frames only
```

**`search` matches whole dot-separated address components, not substrings.** This
is the usual reason a search comes back empty: `search("altitude")` finds nothing
while `search("altitude_detic")` finds it, and `search("planet")` finds nothing
while `search("planet_rel")` finds the sub-model. Search for the exact component
name, or browse `results/graph_tree.json`, which is written after every run and is
the complete address map with each signal's type and value.

## Driving the run

`exc.run()` is `exc.step()` in a loop until the end time. Step it yourself when
Python logic has to interleave with the run — a prototype controller, a custom
stopping condition, a quantity Python computes:

```python
while not exc.isTerminated():
    exc.step()
    if sc.outputs.altitude_detic() < 100_000.0:
        exc.terminate()
```

## Logging and analysis

`Hdf5Logger` is the recommended default (exact values, compact, fast to read
back); `CsvLogger` has the same interface and writes text. Always log
`exc.time().base_time` as the time column. A vector signal expands to one column
per element (`pos_0`, `pos_1`, `pos_2`).

```python
log.addParameter(sc.outputs.pos_sc_pci, "pos")            # by object
log.addParameter(".exc.sc.planet_rel.outputs.altitude_detic", "alt")   # by address
```

Output lands in `results/` (`--out-dir` changes it), alongside `sim_data.json`
(every model's params as run) and `graph_tree.json`. Read it back with:

```python
from warptwinutils.analysisutils import readH5Dataframe, loadFilesMultiRun
df = readH5Dataframe("results/states.h5")                         # one run
runs = loadFilesMultiRun(path="results", filename="states.h5", runpath="run_")
```

Keep analysis in a separate `analysis.py` from the script that runs the
simulation — most shipped examples are organized that way.

## Monte Carlo

Run 0 is always the nominal, undispersed case; every other run number is a
reproducible draw. Declare dispersions **after `parseArgs`** (which reads `--run`
and seeds the engine) and before `startup()`:

```python
d = exc.dispersions()
a = d.createUniformInputDispersion("a_m", 6.878e6, 6.858e6, 6.898e6, "Semimajor axis")
ecc = d.createNormalInputDispersion("ecc", 1e-3, 1e-3, 2e-4, "Eccentricity")

exc.startup()
sc.initializeFromOrbitalElements(a()(), ecc()(), 0.0, 0.0, 0.0, 0.0)
```

A dispersion object is called **twice**: `a()` is the tracked value object (connect
it with `connectSignals` for traceability), `a()()` is the number drawn for this
run. Seed any model with internal randomness from `exc.runNumber()` so noise is
reproducible per run, and special-case run 0 to be clean.

`./multirun.sh -f script.py -n 500 -o results -j 8` runs the sweep.

## Built-in command-line arguments

`--end` (10000 s), `--run` (0), `--out-dir` (`results/`), `--rng-seed` (0),
`--write-data-json` (true), `--save-all-outputs` (false, very large),
`--dispersions-file`, `--enable-visuals` (false), `--real-time` (false).

Add your own with `addDefaultArgument`, then read it back with the **call
operator**, which returns a string:

```python
exc.args().addDefaultArgument("my_flag", 3)
exc.parseArgs(sys.argv)                    # e.g. script.py --my_flag=9
my_flag = int(exc.args()("my_flag"))       # the call operator returns a string
```

`ArgParser::get` is another out-parameter method (`get(name, value)`) and is not
usable in the single-argument form from Python — see the gotcha on out-parameters
below.

## Running the examples

```bash
cd python/scripts/examples && ./run_all_examples.sh
```

They use only installed WarpTwin models, so they run without building anything.
Good starting points: `simple_gravity_spacecraft` (minimal propagation),
`constellation` (loops and repeated structure), `orbital_insertion` (a full ascent
GN&C loop), `monte_carlo_sun_synchronous` (dispersions),
`custom_spacecraft_analysis` (subsystem modeling and reporting).

---

# Writing C++ models

## The model contract

A model is a class declared with the `MODEL` macro, exposing three signal groups
and overriding a small set of lifecycle methods:

- `START_PARAMS … END_PARAMS` — configuration, set once before the run.
- `START_INPUTS … END_INPUTS` — values that change during the run, usually driven
  from another model's outputs.
- `START_OUTPUTS … END_OUTPUTS` — results the model computes.
- `int16 start()` — once, at `startup()`. Load a file, precompute a table.
- `int16 execute()` — every scheduled step. Map params and inputs to outputs.
- `int16 activate()` / `int16 deactivate()` — turn per-step execution on and off
  during a run without changing the model's schedule slot.

Every lifecycle method returns an `int16`: `NO_ERROR` (zero) is success, and any
non-zero value is treated as a fault that stops the run.

Each entry is `SIGNAL(name, type, default)`. `src/models/SlopeIntercept.{h,cpp}`
is a complete, commented example — read it first, and copy its four-constructor
boilerplate verbatim into a new model.

## The header is the interface

The header is what is delivered as documentation, what the Doxygen reference is
generated from, and what the GUI metadata generator parses. Put Doxygen
`@brief`/`@param` comments **in the header, not the `.cpp`**.

The leading comment block drives the GUI:

```cpp
/*
imdata = {"displayname" : "Slope Intercept Model",
          "exclude" : False,
          "category" : "Custom"}
aliases = {"m" : "Multiplier", "b" : "Offset", "x" : "Input", "y" : "Output"}
*/
```

- `displayname` — the block label; defaults to a name derived from the class.
- `category` — the GUI palette group; defaults to `"Custom"`.
- `exclude: True` — hides the model from the GUI entirely.
- `aliases` — renames signals for display without changing the names used in
  code. The special value `"EXCLUDE"` hides that signal from the GUI.

## Schedule slots

A model is placed in the schedule when it is constructed, at the slot its
constructor names (`START_STEP` in the `SlopeIntercept` boilerplate). Each step
advances simulation time by the step size and runs three phases:

| Slot | When | Use for |
| --- | --- | --- |
| `START_STEP` | Once, before state is updated | Sensing and setup |
| `DERIVATIVE` | Once (Euler) or four times (RK4) per step | Anything whose output must be **integrated this step** — forces, torques, accelerations |
| `END_STEP` | Once, after state is advanced | Logging (default), post-processing |
| `ALL` | All three phases | |
| `STARTUP_ONLY` / `NOT_SCHEDULED` | `start()` only / neither | Addressable and loggable but not run |

Override the slot at construction: `SlopeIntercept(exc, DERIVATIVE, "si")`.

There is **no per-unit rate** in the sim scheduler — everything in a slot runs
every step. To make a model effectively run slower, gate its own `execute()` on
`base_time`, or drive it from a stepped loop in Python. Rate limiting applies to
loggers, not to models.

## Verified gotchas

These were each hit and confirmed in this workspace. They are not obvious from
the headers alone.

**Math type names are preprocessor macros, not typedefs.** `core/mathmacros.h`
defines `#define CartesianVector3 clockwerk::CartesianVector<3>` (and the same for
`CartesianVector2/4/6`, `Matrix3/4/6/…`). Writing `clockwerk::CartesianVector3`
therefore expands to `clockwerk::clockwerk::CartesianVector<3>` and fails with
*"no member named 'clockwerk' in namespace 'clockwerk'"*. **Write these types
unqualified.** Real classes such as `Quaternion` are ordinary types and *can* be
written `clockwerk::Quaternion`, which is why shipped headers mix the two styles.

```cpp
SIGNAL(cmd_rate__body, CartesianVector3, CartesianVector3({0.0, 0.0, 0.0}))   // correct
SIGNAL(mount_alignment_mf, clockwerk::Quaternion, clockwerk::Quaternion({1.0, 0.0, 0.0, 0.0}))
```

**Many methods return an error code and hand the result back by reference.** This
is the house style throughout the C++ API, and because SWIG wraps it faithfully
it shows through in Python too. `CartesianVector::unit()` is
`int16 unit(CartesianVector<L> &result) const` — it does *not* return a vector.
`norm()` happens to have a value-returning convenience overload; `unit()` does
not. Check the header rather than assuming a value-returning form exists.

```cpp
CartesianVector3 u;
v.unit(u);            // or v.unitize() to normalize in place
```

Where a value-returning convenience exists it is often the **call operator**
rather than a getter — `exc.args()("end")` works while `exc.args().get("end")`
does not, because `get` takes an out-parameter. The same pattern is why signals
are read as `sc.params.mass()`.

**A changed model header needs a `cmake ..` re-run** before `make`, as described
in the build section.

**Only `src/models`, `src/monitors` and `src/events` are scanned for wrapping.**
A model header elsewhere under `src/` compiles into the library but gets no Python
module and no GUI metadata.

## Testing

Tests use GoogleTest and run without a full simulation. Every `.cpp` under `test/`
is compiled into the test binary automatically.

```cpp
#include <gtest/gtest.h>
#include "simulation/SimulationExecutive.h"
#include "models/SlopeIntercept.h"

using namespace clockwerk;
using namespace warpos;
using namespace warptwin;

TEST(warptwin_custom, SlopeInterceptExample) {
    SimulationExecutive exc;
    SlopeIntercept si(exc);

    si.params.m(2.0);
    si.params.b(3.0);
    si.inputs.x(5.0);

    EXPECT_EQ(NO_ERROR, exc.startup());
    EXPECT_EQ(NO_ERROR, exc.step());
    EXPECT_DOUBLE_EQ(13.0, si.outputs.y());
}
```

`test/testtools.hpp` provides `matrixCompare`, `matrixCompareTol`, and
`arrayCompareTol` for comparing math types with a tolerance. Assert on `NO_ERROR`
from lifecycle calls, not just on the numbers — a fault would otherwise pass
silently.

## Adding a model — checklist

1. `src/models/YourModel.h` and `.cpp`, following `SlopeIntercept`.
2. `test/test_YourModel.cpp`.
3. `cmake ..` (regenerates the SWIG interface), then `make`, then `make test`.
4. `from custom.YourModel import YourModel` with `build/` on `PYTHONPATH`.

If the auto-generator cannot express the wrapping, write `swig/YourModel.i` by
hand and it is built instead. `swig/WarpTwinPy.i` is **not** one of those — it is
the shared interface every generated module includes, and the installed `warptwin`
package already ships the module built from it.

---

# Built-in model catalog

Construct these from `warptwin.<Name>`. The header is the authoritative signal
list, under `<prefix>/include/warptwin/models/` in subdirectories that match the
groupings below — `assemblies/`, `environment/`, `sensors/`, `actuators/`,
`propulsion/`, `power/`, `communications/`, `ground/`, `states/`, `interfaces/`.
Chapter 10 of the manual is the annotated catalog. Use these rather than
reimplementing physics that already ships.

**Assemblies** — `Spacecraft` (the workhorse: rigid body plus gravity, drag,
gravity gradient, third-body, planet-relative state), `LaunchVehicle` (gimballed
throttleable engine, mass depletion, rocket aero, recovery chutes), `SpicePlanet`,
`CustomPlanet`, `ADCS`, `LaunchPadModel`, `GroundStationModel`, `RadioModel`.

**Gravity and orbital dynamics** — `AsphericalGravityModel` (J2/J3),
`SphericalHarmonicsGravityModel`, `PointMassGravityModel`,
`NBodyPerturbationModel`, `GravityGradientModel`, `CR3BPDynamicsModel`.

**Atmosphere, drag, aerodynamics** — `MSISAtmosphereModel` (NRLMSISE-00),
`FlatPlateDragModel`, `FlatPlateDrag3D`, `LaunchVehicleAerodynamicForceModel`,
`AerodynamicsStateModel`, `Parachute`, `SimpleMeanWindModel`,
`SimpleDisturbanceWindModel`, `CompositeWindModel`, `TabularAtmosphereModel`.

**Other environment** — `SolarRadiationPressureModel`, `OccultationModel`,
`DipoleMagneticFieldModel`, `WorldMagneticFieldModel`.

**Actuators and propulsion** — `SimpleThrusterModel`, `ReactionWheelModel`,
`TorqueRodModel`, `TorqueCoilModel`, `Servo`, `TimedImpulsiveBurnModel`,
`PropellantTankModel`, `TabularThrustModel`, `ImpulseModel`.

**Sensors** — `IMU`, `Gyroscope`, `Accelerometer`, `StarTracker`, `SunSensor`,
`Magnetometer`, `GPS`, `SimpleCamera`, `FrameStateSensorModel`,
`OrbitalElementsSensorModel`, `RangeAzElSensorModel`, `GroundStationSensor`,
`PressureSensor`. Nearly all share a pattern: `mount_frame`, `rate_hz`,
`seed_value`, optional `latency` (ms), a `..._power_draw`, a truth `perfect_…`
output, a noisy `meas_…` output, an `output_time`, and an `is_valid` flag; noise
standard deviations come in through the **inputs**.

**Navigation, guidance, control** — `StochasticNavigation`,
`DirectionalAdaptiveGuidance`, `PidTranslationalControl`, plus the WarpOS flight
apps (`PdAttitudeControl`, `SingleAxisPointingControl`, `TwoAxisPointingGuidance`,
`UnifiedPoweredFlightGuidance`, the EKF suites), which run in the loop like real
flight code.

**Power** — `SolarPanelModel`, `SolarPanelPowerModel`, `SimpleBatterySystem`,
`PowerLoad`, `EffectiveSolarAreaModel`. Register a model's power **signal** (not
the model) with `sc.addPowerSource(…)` / `sc.addPowerLoad(…)` — both take a
`DataIO<double>*` — and it folds into `sc.outputs.total_power_in` /
`total_power_out`.

**Communications and access** — `RadioModel`, `SimpleComAnalysisModel`,
`SpacecraftLinkModel`, `EarthObservationModel`.

**Utility** — `LogEvent`, `SimTerminationEvent`, `ProximityMonitor`,
`RateMonitor`, `TimeTriggerMonitor`, `FaultInjection`, `MarkovUncertaintyModel`,
`BiasNoiseModel`, `LlaDeticStateInit`, `OrbitalElementsStateInit`.

## Math types

From `warptwin.WarpTwinPy`: `CartesianVector2/3/4/6`, sized matrices (`Matrix3`,
`Matrix3x4`, `Matrix6x6`, … — the bare `Matrix` template is not exported, only its
instantiations), and the attitude representations `DCM`, `Quaternion`
(scalar-first), `Euler321` (3-2-1 yaw-pitch-roll, radians, singular at ±90° pitch)
and `MRP`. `RotationVector` exists in C++ only. All are passive rotations
following Schaub & Junkins conventions.

`A * B` composes two rotations of the same representation; `R * v` rotates a
vector, so `quat_A_B * v_B` gives `v_A`. There is no implicit conversion between
representations — convert first with `toDCM()`, `toQuaternion()`, etc.

For the vector products, C++ has the free functions `dot(a, b)`, `cross(a, b)`
and `tilde(v)`. In Python `cross` and `tilde` are free functions, but **`dot` is
not** — use the method `a.dot(b)` (the free function is exported only under
size-suffixed names such as `dotd31`).

Constants: `DEGREES_TO_RADIANS`, `RADIANS_TO_DEGREES`, `KM_TO_METERS`,
`AU_TO_METERS`, `M_PI`, `TWO_PI`, `SPEED_OF_LIGHT`, the time-conversion set, and
planetary constants.

## Style

- **Python** follows WarpWare's convention, not PEP 8: `lowerCamelCase` for
  functions and methods, `UPPER_SNAKE_CASE` for constants. Signal names stay in
  the `snake_case` form the C++ declares.
- **C++** is C++17. Doxygen comments belong in headers only. Keep the license
  header block on new files, matching the surrounding files.
- Give models distinct, meaningful names at construction (`"star_tracker_a"`, not
  `"m1"`) — the name becomes the address used by logging, telemetry, and the
  command router, and is fixed at construction.
- Put named constants in a block at the top of a script rather than burying magic
  numbers in calls.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Orbit is inside the planet, or attitude is wildly wrong | Kilometers or degrees passed where meters or radians were expected |
| Errors in `*PYTHON_wrap.cxx` after editing a header | `cmake ..` not re-run before `make` |
| `no member named 'clockwerk' in namespace 'clockwerk'` | A `CartesianVector3`/`Matrix3` macro was namespace-qualified |
| `AttributeError: property '…' has no setter` | Signal assigned with `=` instead of the call operator |
| `exc.search("…")` returns nothing | Searches match whole address components, not substrings |
| A param seems to have no effect | It was set after `startup()` |
| Initial state ignored or wrong | `initialize…` called before `startup()` |
| Custom model missing from Python or the GUI | Header is not under `src/models`, `src/monitors` or `src/events`; or `imdata` has `exclude: True` |
| `import warptwin` fails, or custom modules will not import beside it | Python version does not match the one WarpTwin was installed for; pass `-DPython3_EXECUTABLE=…` |
| `ModuleNotFoundError: warptwinutils` on macOS | That package is missing from some macOS releases; it is part of the WarpTwin install, not this repo. Contact support |

`warptwin-doctor --verbose` is the first thing to run for anything installation-
shaped, and its output is what support asks for.
