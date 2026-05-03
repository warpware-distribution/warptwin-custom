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

# ATTX WarpTwin version 0.1
cmake_minimum_required(VERSION 3.8)
project(warptwin-custom VERSION 0.1)
cmake_policy(SET CMP0078 NEW)
cmake_policy(SET CMP0086 NEW)
cmake_policy(SET CMP0072 NEW)
set(USE_SWIG_DEPENDENCIES TRUE)

# Set basic standards for the project
set(CMAKE_CXX_STANDARD 17) 
set(CMAKE_C_STANDARD 99)
set(CMAKE_CXX_STANDARD_REQUIRED True)
set(CMAKE_CXX_FLAGS "-g -Og -Wall -fPIC")
set(CMAKE_C_FLAGS "-g -Og -Wall -fPIC")

# Export our project dir for access in Python
execute_process(COMMAND touch ${PROJECT_BINARY_DIR}/__init__.py)
execute_process(COMMAND mkdir -p ${PROJECT_BINARY_DIR}/custom)
execute_process(COMMAND mkdir -p ${PROJECT_BINARY_DIR}/swig_auto)
execute_process(COMMAND touch ${PROJECT_BINARY_DIR}/custom/__init__.py)

##############################################################################
# Set up dependencies
##############################################################################
# We have a dependency on Python (and other languages) for CMake. Find python
# here and ensure it is included
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)
find_package(PythonLibs REQUIRED)
include_directories(${PYTHON_INCLUDE_DIRS})

find_package(HDF5 REQUIRED)
include_directories(libdeps SYSTEM INTERFACE ${HDF5_INCLUDE_DIRS})

add_definitions(-DMODELSPACE_ROOT_DIR="/usr/share/warptwin")
add_definitions(-DCLOCKWERK_ROOT_DIR="/usr/share/warptwin")
add_definitions(-DPROJECT_ROOT_DIR="/usr/share/warptwin")
add_definitions(-DLICENSE_ROOT_DIR="/usr/share/warptwin")

##############################################################################
# Library Source Code
##############################################################################
set(SRC_DIR ${PROJECT_SOURCE_DIR}/src)
include_directories(${SRC_DIR})
include_directories(/usr/include/warptwin)

# Mark the source directory for our models, tasks, monitors, events, systems
# This block builds a library from our source to be linked into test and 
# analysis scripts
file(GLOB_RECURSE CXX_SRC ${SRC_DIR}/*.cpp)
add_library(${PROJECT_NAME} SHARED ${CXX_SRC})
target_link_libraries(${PROJECT_NAME} PUBLIC warptwin locations)

##############################################################################
# Testing Code
##############################################################################
# Set our test directory
set(EXECUTABLE_OUTPUT_PATH ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
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
target_link_libraries(${PROJECT_NAME}_test gtest_main ${PROJECT_NAME} warptwin locations gcov)

include(GoogleTest)
gtest_discover_tests(${PROJECT_NAME}_test)

##############################################################################
# SWIG Code
##############################################################################
# First, we need to auto-generate our swig .i files for our models. Get a 
# handle to all the header files in our directory
file(GLOB_RECURSE ITEM_HEADERS ${SRC_DIR}/models/*.h)

# Preprocess and auto-generate our SWIG files as well as our build metadata json for use
# in the warptwin GUI     
execute_process(COMMAND BuildProcessFiles.py
                "--info-file=${PROJECT_BINARY_DIR}/custom_models.json"
                "--incl_swig_dir=${PROJECT_SOURCE_DIR}/swig"
                "--out_dir=${PROJECT_BINARY_DIR}/swig_auto"
                "--template_file=${PROJECT_SOURCE_DIR}/swig/swigtemplate.txt"
                "--targets=${ITEM_HEADERS}"
                "--start-node=80000"
                "--start-connection=90000"
                WORKING_DIRECTORY ${PROJECT_BINARY_DIR}
                RESULT_VARIABLE rv
                OUTPUT_VARIABLE out)

find_package (SWIG)
include (UseSWIG)
set(CMAKE_SWIG_OUTDIR ${PROJECT_BINARY_DIR}/custom)
set(MAN_SWIG_DIR ${PROJECT_SOURCE_DIR}/swig)
file(GLOB_RECURSE MAN_SWIG ${MAN_SWIG_DIR}/*.i)

get_directory_property(hasParent PARENT_DIRECTORY)
foreach(tgt ${MAN_SWIG})    
    set_property(SOURCE ${tgt} PROPERTY CPLUSPLUS ON)
    string(REPLACE ${MAN_SWIG_DIR}/ "" tgt_name ${tgt})
    string(REPLACE ".i" "" tgt_name ${tgt_name})
    message("Configuring CMake for SWIG target module ${tgt_name}")
    if(hasParent)
        swig_add_library(${tgt_name} 
                            LANGUAGE python
                            SOURCES ${tgt}                     
                            OUTPUT_DIR ${CMAKE_SWIG_OUTDIR} 
                            OUTFILE_DIR ${CMAKE_SWIG_OUTDIR})
        set_target_properties(${SWIG_MODULE_${tgt_name}_REAL_NAME} 
                              PROPERTIES LIBRARY_OUTPUT_DIRECTORY "${CMAKE_SWIG_OUTDIR}"
                              SWIG_COMPILE_OPTIONS "-fvirtual")
        target_link_libraries(${tgt_name} warptwin ${PROJECT_NAME})
    else()
        swig_add_library(${tgt_name} 
                         LANGUAGE python
                         SOURCES ${tgt}                     
                         OUTPUT_DIR ${CMAKE_SWIG_OUTDIR} 
                         OUTFILE_DIR ${CMAKE_SWIG_OUTDIR})
        set_target_properties(${SWIG_MODULE_${tgt_name}_REAL_NAME} 
                              PROPERTIES LIBRARY_OUTPUT_DIRECTORY "${CMAKE_SWIG_OUTDIR}"
                              SWIG_COMPILE_OPTIONS "-fvirtual")
        target_link_libraries(${tgt_name} warptwin ${PROJECT_NAME})
    endif()
endforeach()

set(AUTO_SWIG_DIR ${PROJECT_BINARY_DIR}/swig_auto)
file(GLOB_RECURSE AUTO_SWIG ${AUTO_SWIG_DIR}/*.i)

foreach(tgt ${AUTO_SWIG})
    set_property(SOURCE ${tgt} PROPERTY CPLUSPLUS ON)
    string(REPLACE ${AUTO_SWIG_DIR}/ "" tgt_name ${tgt})
    string(REPLACE ".i" "" tgt_name ${tgt_name})
    message("Configuring CMake for SWIG target module ${tgt_name}")
    swig_add_library(${tgt_name} 
                     LANGUAGE python
                     SOURCES ${tgt} 
                     OUTPUT_DIR ${CMAKE_SWIG_OUTDIR} 
                     OUTFILE_DIR ${CMAKE_SWIG_OUTDIR})
    set_target_properties(${SWIG_MODULE_${tgt_name}_REAL_NAME} 
                          PROPERTIES LIBRARY_OUTPUT_DIRECTORY "${CMAKE_SWIG_OUTDIR}"
                          SWIG_COMPILE_OPTIONS "-fvirtual")
    target_link_libraries(${tgt_name} warptwin ${PROJECT_NAME})
endforeach()