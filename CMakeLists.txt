###############################################################################
# Copyright (c) ATTX Inc 2026. All Rights Reserved.
#
# This software and associated documentation (the "Software") are the
# proprietary and confidential information of ATTX INC. The Software is
# furnished under a license agreement between ATTX and the user organization
# and may be used or copied only in accordance with the terms of the agreement.
# Refer to 'license/attx_license.adoc' for standard license terms.
#
# EXPORT CONTROL NOTICE: THIS SOFTWARE MAY INCLUDE CONTENT CONTROLLED UNDER THE
# INTERNATIONAL TRAFFIC IN ARMS REGULATIONS (ITAR) OR THE EXPORT ADMINISTRATION
# REGULATIONS (EAR99). No part of the Software may be used, reproduced, or
# transmitted in any form or by any means, for any purpose, without the express
# written permission of ATTX INC.
###############################################################################
#
# Custom model repository for an installed WarpTwin.
#
# This project does not build WarpTwin. It compiles and SWIG-wraps the models in
# src/ against a WarpTwin that is already installed on the machine -- the headers
# under <prefix>/include/warptwin and the shared libraries beside them -- and
# produces a `custom` Python package that sits alongside the installed `warptwin`
# one.
#
cmake_minimum_required(VERSION 3.16)
project(warptwin-custom VERSION 26.09 LANGUAGES C CXX)

cmake_policy(SET CMP0078 NEW)   # UseSWIG generates standard target names
cmake_policy(SET CMP0086 NEW)   # UseSWIG honours the SWIG_MODULE_NAME property
set(USE_SWIG_DEPENDENCIES TRUE)

# Set basic standards for the project
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_C_STANDARD 99)
set(CMAKE_CXX_STANDARD_REQUIRED True)
set(CMAKE_CXX_FLAGS "-g -Og -Wall -fPIC")
set(CMAKE_C_FLAGS "-g -Og -Wall -fPIC")
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

##############################################################################
# Locate the installed WarpTwin
##############################################################################
# Everything this project links against comes out of the WarpTwin package, so
# find it before anything else and fail early -- with something readable -- if
# it is not installed. WARPTWIN_ROOT overrides the search for an install in a
# non-standard prefix:
#
#   cmake .. -DWARPTWIN_ROOT=/opt/warptwin
#
set(WARPTWIN_ROOT "" CACHE PATH "Install prefix of WarpTwin (contains include/warptwin and lib/)")

if(WARPTWIN_ROOT)
    set(WT_SEARCH_PREFIXES ${WARPTWIN_ROOT})
else()
    # The Ubuntu package installs under /usr; the macOS package under
    # /usr/local/warptwin. See packaging/docker/stage2-build.sh and
    # packaging/macos/stage2-build-macos.sh in the warptwin repository.
    set(WT_SEARCH_PREFIXES /usr /usr/local/warptwin /usr/local /opt/warptwin)
endif()

find_path(WARPTWIN_INCLUDE_DIR
          NAMES simulation/Model.h
          HINTS ${WT_SEARCH_PREFIXES}
          PATH_SUFFIXES include/warptwin
          NO_DEFAULT_PATH)
if(NOT WARPTWIN_INCLUDE_DIR)
    message(FATAL_ERROR
            "WarpTwin headers not found (looked for include/warptwin/simulation/Model.h under "
            "${WT_SEARCH_PREFIXES}). Install the WarpTwin package, or point this build at it "
            "with -DWARPTWIN_ROOT=<prefix>.")
endif()

# The shared libraries live in their own subdirectory of the library path rather
# than directly on it, so they do not collide with anything else on the system
# and are found through the RUNPATH baked into the package's own binaries.
set(WT_LIB_SUFFIXES lib/warptwin lib64/warptwin lib)
if(CMAKE_LIBRARY_ARCHITECTURE)
    list(INSERT WT_LIB_SUFFIXES 0 lib/${CMAKE_LIBRARY_ARCHITECTURE}/warptwin)
endif()

foreach(_wt_lib warptwin locations warpos_flight_lib)
    string(TOUPPER ${_wt_lib} _wt_lib_var)
    find_library(WARPTWIN_${_wt_lib_var}_LIBRARY
                 NAMES ${_wt_lib}
                 HINTS ${WT_SEARCH_PREFIXES}
                 PATH_SUFFIXES ${WT_LIB_SUFFIXES}
                 NO_DEFAULT_PATH)
    if(NOT WARPTWIN_${_wt_lib_var}_LIBRARY)
        message(FATAL_ERROR
                "WarpTwin library '${_wt_lib}' not found under ${WT_SEARCH_PREFIXES}. The "
                "headers were found at ${WARPTWIN_INCLUDE_DIR}, so the install looks "
                "incomplete -- reinstall the WarpTwin package.")
    endif()
endforeach()

# The data directory the compiled-in paths in locations.h have to resolve to.
# Everything the simulation reads at runtime -- spice kernels, planet data,
# visuals -- is addressed relative to it, so a wrong value here is invisible
# until a simulation runs and then fails to open a kernel.
find_path(WARPTWIN_SHARE_DIR
          NAMES cspice/data
          HINTS ${WT_SEARCH_PREFIXES}
          PATH_SUFFIXES share/warptwin
          NO_DEFAULT_PATH)
if(NOT WARPTWIN_SHARE_DIR)
    message(FATAL_ERROR
            "WarpTwin data directory not found (looked for share/warptwin/cspice/data under "
            "${WT_SEARCH_PREFIXES}). On Ubuntu this comes from the warptwin-data package.")
endif()

# The license file is per-machine customer configuration rather than package
# content, so on Linux it sits in /etc; the macOS package keeps it inside the
# prefix. Match whichever the installed package used -- this has to name the
# same directory the installed libwarptwin was built against.
if(APPLE)
    set(WARPTWIN_LICENSE_DIR "${WARPTWIN_SHARE_DIR}")
else()
    set(WARPTWIN_LICENSE_DIR "/etc/warptwin")
endif()

message(STATUS "WarpTwin headers:   ${WARPTWIN_INCLUDE_DIR}")
message(STATUS "WarpTwin library:   ${WARPTWIN_WARPTWIN_LIBRARY}")
message(STATUS "WarpTwin data:      ${WARPTWIN_SHARE_DIR}")

# locations.h reads these four out of the compiler command line. They are not
# defaulted in the header, so anything that includes it -- which is every model,
# through Model.h -- fails to compile without them.
add_definitions(-DMODELSPACE_ROOT_DIR="${WARPTWIN_SHARE_DIR}")
add_definitions(-DCLOCKWERK_ROOT_DIR="${WARPTWIN_SHARE_DIR}")
add_definitions(-DPROJECT_ROOT_DIR="${WARPTWIN_SHARE_DIR}")
add_definitions(-DLICENSE_ROOT_DIR="${WARPTWIN_LICENSE_DIR}")

include_directories(SYSTEM ${WARPTWIN_INCLUDE_DIR})

# The warpOS simulation-package headers -- types.h, configuration.h, SimLinux.h,
# SimPlatform.h and SimSetup.h -- are included by bare name from GraphTreeObject.h
# and SimulationExecutive.h, so transitively by every model. They are not
# currently part of the installed header tree, so copies matching the release
# live in includes/warptwin_sim/ and are used only when the install lacks them.
if(EXISTS "${WARPTWIN_INCLUDE_DIR}/configuration.h")
    message(STATUS "warpOS package headers: ${WARPTWIN_INCLUDE_DIR} (from the install)")
else()
    message(STATUS "warpOS package headers: ${PROJECT_SOURCE_DIR}/includes/warptwin_sim "
                   "(vendored -- the installed header tree does not carry them)")
    include_directories(SYSTEM ${PROJECT_SOURCE_DIR}/includes/warptwin_sim)
endif()

##############################################################################
# Set up remaining dependencies
##############################################################################
# We have a dependency on Python for CMake and for SWIG. Find it here and ensure
# it is included. The legacy find_package(PythonLibs) is deliberately not used:
# on macOS it can resolve to a different Python installation than Python3 does,
# which fails at link time.
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)
include_directories(${Python3_INCLUDE_DIRS})

# What the SWIG extension modules link against for CPython. An extension module
# resolves CPython symbols from the interpreter that imports it, never from a
# libpython of its own, so on macOS it must not link libpython at all.
if(APPLE)
    set(WARPTWIN_PYTHON_LINK Python3::Module)
    set(CMAKE_MACOSX_RPATH ON)
    set(CMAKE_INSTALL_RPATH_USE_LINK_PATH TRUE)
    set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -undefined dynamic_lookup")
    set(CMAKE_MODULE_LINKER_FLAGS "${CMAKE_MODULE_LINKER_FLAGS} -undefined dynamic_lookup")
else()
    set(WARPTWIN_PYTHON_LINK Python3::Python)
endif()

# HDF5 comes in through Hdf5Logger.h, which SimulationExecutive.h includes, so
# its headers are needed to compile a model even though nothing here calls it.
find_package(HDF5 REQUIRED COMPONENTS C)
include_directories(SYSTEM ${HDF5_INCLUDE_DIRS})

find_package(SWIG REQUIRED)
include(UseSWIG)

##############################################################################
# Python package layout
##############################################################################
# The build directory doubles as the Python path: `custom` is the package the
# generated model wrappers land in, next to the installed `warptwin` one.
set(CUSTOM_PY_MODULE custom)
set(CUSTOM_PY_DIR ${PROJECT_BINARY_DIR}/${CUSTOM_PY_MODULE})
file(MAKE_DIRECTORY ${CUSTOM_PY_DIR})
file(MAKE_DIRECTORY ${PROJECT_BINARY_DIR}/swig_auto)
file(TOUCH ${PROJECT_BINARY_DIR}/__init__.py)

# Importing the package makes every custom model available as an attribute, the
# same way the installed warptwin package behaves.
file(WRITE ${CUSTOM_PY_DIR}/__init__.py
"\"\"\"Custom WarpTwin models, generated at build time by CMakeLists.txt.\"\"\"

import importlib as _importlib
import pkgutil as _pkgutil

__all__ = []

for _module_info in _pkgutil.iter_modules(__path__):
    _name = _module_info.name
    # Skip the compiled extension halves; the proxy module of the same name
    # imports its own.
    if _name.startswith(\"_\"):
        continue
    try:
        globals()[_name] = _importlib.import_module(\".\" + _name, __name__)
        __all__.append(_name)
    except Exception:  # pragma: no cover - a broken module must not break the package
        pass

del _importlib, _pkgutil
")

##############################################################################
# Library Source Code
##############################################################################
set(SRC_DIR ${PROJECT_SOURCE_DIR}/src)
include_directories(${SRC_DIR})

# Mark the source directory for our models, tasks, monitors, events, systems
# This block builds a library from our source to be linked into test and
# analysis scripts
file(GLOB_RECURSE CXX_SRC ${SRC_DIR}/*.cpp)
add_library(${PROJECT_NAME} SHARED ${CXX_SRC})
target_link_libraries(${PROJECT_NAME} PUBLIC
                      ${WARPTWIN_WARPTWIN_LIBRARY}
                      ${WARPTWIN_WARPOS_FLIGHT_LIB_LIBRARY}
                      ${WARPTWIN_LOCATIONS_LIBRARY})

##############################################################################
# Testing Code
##############################################################################
# Set our test directory
set(TEST_DIR ${PROJECT_SOURCE_DIR}/test)
file(GLOB_RECURSE CXX_TEST ${TEST_DIR}/*.cpp)

# Fetch our googletest support code
include(FetchContent)
FetchContent_Declare(
  googletest
  GIT_REPOSITORY https://github.com/google/googletest.git
  GIT_TAG        release-1.12.0
)
# For Windows: Prevent overriding the parent project's compiler/linker settings
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

# Enable our testing
enable_testing()

# Build all of our tests. These lines loop through the test directory and
# build all cpp tests
add_executable(${PROJECT_NAME}_test ${CXX_TEST})
target_link_libraries(${PROJECT_NAME}_test gtest_main ${PROJECT_NAME})

include(GoogleTest)
gtest_discover_tests(${PROJECT_NAME}_test)

##############################################################################
# SWIG Code
##############################################################################
# First, we need to auto-generate our swig .i files for our models. Get a
# handle to all the header files in our directory
file(GLOB_RECURSE ITEM_HEADERS ${SRC_DIR}/models/*.h
                               ${SRC_DIR}/monitors/*.h
                               ${SRC_DIR}/events/*.h)

# Preprocess and auto-generate our SWIG files as well as our build metadata json
# for use in the WarpTwin GUI:
#
#   wt-gui --custom-model-file=<build>/custom_models.json
#
# BuildProcessFiles.py reconciles swig_auto/ against the target list on every
# configure: it renders each header's interface, writes only the files whose
# contents actually changed, and deletes any .i file that no target header
# generates any more. Leaving an unchanged .i alone is what keeps its timestamp
# still, and CMake's SWIG integration treats that timestamp as a build
# dependency, so nothing needs clearing here -- clearing would re-SWIG and
# recompile every wrapper on each reconfigure.
#
# The node and connection ids start high so they cannot collide with the ids the
# WarpTwin build assigns to its own models in the same GUI session.
set(BUILDUTILS_DIR ${PROJECT_SOURCE_DIR}/python/buildutils)
execute_process(COMMAND ${Python3_EXECUTABLE} ${BUILDUTILS_DIR}/BuildProcessFiles.py
                "--info-file=${PROJECT_BINARY_DIR}/custom_models.json"
                "--incl_swig_dir=${PROJECT_SOURCE_DIR}/swig"
                "--out_dir=${PROJECT_BINARY_DIR}/swig_auto"
                "--template_file=${PROJECT_SOURCE_DIR}/swig/swigtemplate.txt"
                "--py-module=${CUSTOM_PY_MODULE}"
                "--targets=${ITEM_HEADERS}"
                "--start-node=80000"
                "--start-connection=90000"
                WORKING_DIRECTORY ${BUILDUTILS_DIR}
                RESULT_VARIABLE rv
                OUTPUT_VARIABLE out
                ERROR_VARIABLE err)
if(NOT rv EQUAL 0)
    message(FATAL_ERROR "BuildProcessFiles.py failed:\n${out}\n${err}")
endif()
# Report what the generator did. It says which interfaces it wrote and which it
# removed, and that is the only place a deleted model shows up in the log.
string(STRIP "${out}" out)
if(NOT out STREQUAL "")
    message(STATUS "${out}")
endif()

set(CMAKE_SWIG_OUTDIR ${CUSTOM_PY_DIR})

# Turn one .i file into an importable extension module in the custom package.
function(add_custom_swig_module tgt)
    set_property(SOURCE ${tgt} PROPERTY CPLUSPLUS ON)
    get_filename_component(tgt_name ${tgt} NAME_WE)
    message(STATUS "Configuring CMake for SWIG target module ${tgt_name}")
    swig_add_library(${tgt_name}
                     LANGUAGE python
                     SOURCES ${tgt}
                     OUTPUT_DIR ${CMAKE_SWIG_OUTDIR}
                     OUTFILE_DIR ${CMAKE_SWIG_OUTDIR})
    set_target_properties(${tgt_name}
                          PROPERTIES LIBRARY_OUTPUT_DIRECTORY "${CMAKE_SWIG_OUTDIR}"
                          SWIG_COMPILE_OPTIONS "-fvirtual")
    target_link_libraries(${tgt_name} ${PROJECT_NAME} ${WARPTWIN_PYTHON_LINK})
endfunction()

# Hand-written interfaces, for a model whose wrapping the auto-generator cannot
# express. WarpTwinPy.i is not one of them: it is the shared interface every
# generated module %includes, and the installed warptwin package already ships
# the module built from it.
set(MAN_SWIG_DIR ${PROJECT_SOURCE_DIR}/swig)
file(GLOB MAN_SWIG ${MAN_SWIG_DIR}/*.i)
list(REMOVE_ITEM MAN_SWIG ${MAN_SWIG_DIR}/WarpTwinPy.i)
foreach(tgt ${MAN_SWIG})
    add_custom_swig_module(${tgt})
endforeach()

# Everything BuildProcessFiles.py generated above
set(AUTO_SWIG_DIR ${PROJECT_BINARY_DIR}/swig_auto)
file(GLOB AUTO_SWIG ${AUTO_SWIG_DIR}/*.i)
foreach(tgt ${AUTO_SWIG})
    add_custom_swig_module(${tgt})
endforeach()
