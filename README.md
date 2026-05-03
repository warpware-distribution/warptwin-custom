# WarpTwin
WarpTwin: Next generation simulation for mission design, GN&C development, flight software test, and more.

## References
- Detailed documentation on WarpTwin, including model documentation can be found here: https://github.com/attx-engineering/warptwin-users-guide/blob/main/WarpTwin%20User's%20Guide.pdf
- WarpTwin is also equipped with an AI chatbot trained on its source code and user's manuals here: http://assist.attxsoftware.com:8504/

## Release Notes
WarpTwin is released on a quarterly cadence with releases tagged as month.year-release. At minimum, ATTX does our best to cut a release per quarter on the third Friday of that month. For example 25.03-0 is release on the third Friday of March, 2025, and is the first release in that quarter. 

ATTX may optionally release WarpTwin on a faster cadence.

## Installing packages for WarpTwin
WarpTwin requires a number of packages to build and run correctly. These packages are defined in install.sh, which may be run to fully install warptwin for convenience. They can also be run independently as desired.

```
./install.sh
```

IMPORTANT: Users should always run install.sh before attempting to build WarpTwin.

## Building WarpTwin
Modelspace is built using cmake. First create a build directory, which will hold our binaries, and cd into it.

```
mkdir build
cd build
```

Now run cmake. Cmake should be run under the following conditions
- First build of the repo
- Any target files (.h, .cpp, .i) are added or removed
- The .h header file for a model or app is changed

```
cmake ..
```

Finally, compile WarpTwin. This should run in approx. 1 minute and produce no errors. The argument `-j<n>` sets the number of cores which should be used to build. Any number up to 20 is usually fine, depending on the system -- higher is faster.

```
make -j20
```

Run the unit tests to ensure everything is working and passing. 100% of tests should always pass

```
make test
```

Running the GUI with custom models involves telling the GUI where the custom models live when running:

```
ms-gui --custom-model-file=custom_models.json
```

By default, WarpTwin compiles into SWIG-wrapped Python in addition to c++. Python scripts are held at `python/scripts/` and should work out of the box. Try running a few to verify this.