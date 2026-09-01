/******************************************************************************
* Copyright (c) ATTX INC 2026. All Rights Reserved.
*
* This software and associated documentation (the "Software") are the 
* proprietary and confidential information of ATTX, INC. The Software is 
* furnished under a license agreement between ATTX and the user organization 
* and may be used or copied only in accordance with the terms of the agreement.
* Refer to 'license/attx_license.adoc' for standard license terms.
*
* EXPORT CONTROL NOTICE: THIS SOFTWARE MAY INCLUDE CONTENT CONTROLLED UNDER THE
* INTERNATIONAL TRAFFIC IN ARMS REGULATIONS (ITAR) OR THE EXPORT ADMINISTRATION 
* REGULATIONS (EAR99). No part of the Software may be used, reproduced, or 
* transmitted in any form or by any means, for any purpose, without the express 
* written permission of ATTX, INC.
******************************************************************************/
/* File : WarpTwinPy.i */
%module(directors="1") WarpTwinPy
%include <stl.i>
%include <cstring.i>
%include <std_string.i>
%include <std_vector.i>
%include <std_array.i>
%include <stdint.i>

%feature("flatnested", "3");
%feature("director") SimLogger;

#pragma SWIG nowarn=302,509,362,389,314
%template(VecString) std::vector<std::string>;
%{
// Define our macros
// #include "core/macros.h"

#include "types.h"
#include "configuration.h"

// Include our "core" modules containing math functions
#include "core/Matrix.hpp"
#include "core/CartesianVector.hpp"
#include "core/matrixmath.hpp"
#include "core/vectormath.hpp"

// Attitude math
#include "dynamics/DCM.h"
#include "dynamics/Euler321.h"
#include "dynamics/MRP.h"
#include "dynamics/Quaternion.h"

// Data management/graph tree
#include "architecture/GraphTreeObject.h"
#include "architecture/Time.h"
#include "architecture/DataIOBase.h"
#include "architecture/DataIO.hpp"
#include "architecture/signalutils.h"

// warpOS Includes
#include "flight/FlightExecutive.h"
#include "flight/App.h"
#include "flight/OS.h"
#include "flight/Platform.h"
#include "flight/Setup.h"
#include "flight/Scheduler.h"
#include "flight/flighterrors.h"

// Logging
#include "logging/SimLogger.h"
#include "logging/CsvLogger.h"
#include "logging/Hdf5Logger.h"
#include "logging/LogManager.h"

// Frames and frame derivatives
#include "frames/Joint.h"
#include "frames/Frame.h"
#include "frames/Body.h"
#include "frames/Node.h"
#include "frames/frameutils.h"

// Architecture modules
#include "simulation/SimScheduler.h"
#include "flight/Scheduler.h"
#include "architecture/Time.h"
#include "simulation/SimTimeManager.h"

// Unit utils
#include "constants/unitutils.h"
#include "cr3bputils/conversions.h"
#include "constants/planetdefaults.h"

// Spice manager
#include "utils/spiceutils.h"

// Simulation
#include "simulation/SimulationExecutive.h"
#include "simulation/SimulationSteps.h"
#include "simulation/ArgParser.h"
#include "simulation/DispersionEngine.h"
#include "simulation/Model.h"
#include "simulation/SimTimeManager.h"
#include "simulation/stateinit.h"

// PlanetRel stuff
#include "utils/planetrelutils.h"
#include "gncutils/states/planetrelutils.h"
#include "utils/googleearthkml.h"

using namespace warptwin;

%}
// Macros
// %include "core/macros.h"

// CONFIGURE IGNORE VARIABLES
// Signals are read-only from Python. SWIG emits a setter for every public member, and for a
// DataIO member that setter assigns one signal object over another -- replacing a fixed position
// on the graph tree instead of setting the value it holds. Values are set through the call
// operator (obj.signal(value)), which is unaffected.
%ignore clockwerk::GraphTreeObject::children;
%ignore warpos::FlightExecutive::getRegistry;
// The hardware configuration structs are not exposed to Python. Each one holds a `const char*
// device` field, and SWIG's generated setter for a const char* member assigns the pointer
// without owning it -- warning 451 -- so a Python string handed in would be freed underneath
// the struct. These are flight configuration, set from C++ at platform bring-up, so there is
// nothing to give up by leaving them out.
%ignore warpos::GpioConfig_t;
%ignore warpos::SpiConfig_t;
%ignore warpos::UartConfig_t;
%ignore warpos::I2cConfig_t;
%ignore warpos::PwmConfig_t;
%ignore warpos::HwTimerConfig_t;
%ignore warpos::CanConfig_t;
%ignore warpos::AdcConfig_t;
%ignore warpos::Os::yield;

%include "types.h"
%include "configuration.h"

// Error and warning codes. Every call that can fail returns one of these, and without them a
// script has no way to check a return value except against a hardcoded integer.
%include "core/clockwerkerrors.h"

// Swig include of core modules
%include "core/Matrix.hpp"
%include "core/CartesianVector.hpp"
%include "core/matrixmath.hpp"
%include "core/vectormath.hpp"

// Matrix and vector instantiations, together with the Python operator support that makes them
// behave the way they do in C++ -- indexing, arithmetic, comparison and conversion. The
// %template declarations for every matrix and vector type live in there, since a %extend has to
// precede the %template it applies to.
%include "mathoperators.swg"

// Attitude
%include "dynamics/DCM.h"
%include "dynamics/Euler321.h"
%include "dynamics/MRP.h"
%include "dynamics/Quaternion.h"

// The attitude types derive from the matrix and vector templates, so their operator support has
// to come after both those instantiations and the headers above
%include "attitudeoperators.swg"

// Data management
%include "architecture/GraphTreeObject.h"
%include "architecture/Time.h"
%include "architecture/DataIOBase.h"
%immutable;
%include "architecture/DataIO.hpp"
%mutable;
%include "architecture/signalutils.h"

// warpOS Includes
%include "flight/FlightExecutive.h"
%immutable;
%include "flight/App.h"
%mutable;
%include "flight/OS.h"
%include "flight/Platform.h"
%include "flight/Setup.h"
%include "flight/Scheduler.h"
%include "flight/flighterrors.h"

// Frames
%include "architecture/GraphTreeObject.h"
%include "frames/Joint.h"
%immutable;
%include "frames/Frame.h"
%mutable;
%immutable;
%include "frames/Body.h"
%mutable;
%immutable;
%include "frames/Node.h"
%mutable;
%include "frames/frameutils.h"

// Logging
%include "logging/SimLogger.h"
%include "logging/CsvLogger.h"
%include "logging/Hdf5Logger.h"
%include "logging/LogManager.h"

// Unit utils
%include "constants/unitutils.h"
%include "cr3bputils/conversions.h"
// PlanetDefaults has const data members and no default constructor; prevent
// SWIG from generating wrapper code that tries to call PlanetDefaults().
%nodefaultctor warpos::PlanetDefaults;
%include "constants/planetdefaults.h"

// Spice manager
%include "utils/spiceutils.h"

// Simulation
%include "simulation/SimulationSteps.h"
%immutable;
%include "simulation/DispersionEngine.h"
%mutable;
%immutable;
%include "simulation/SimTimeManager.h"
%mutable;
%include "simulation/SimulationExecutive.h"
%include "simulation/ArgParser.h"
%include "simulation/Model.h"
%include "simulation/stateinit.h"

// Type definitions for Python
%include "simulation/ArgParser.h"

%template(dotd21) clockwerk::dot<2>;
%template(dotd31) clockwerk::dot<3>;
%template(dotd41) clockwerk::dot<4>;
%template(dotd61) clockwerk::dot<6>;

%template(DataIODouble) clockwerk::DataIO<double>;
%template(DataIOFloat) clockwerk::DataIO<float>;
%template(DataIOBool) clockwerk::DataIO<bool>;
%template(DataIOPointer) clockwerk::DataIO<void*>;
%template(DataIOString) clockwerk::DataIO<std::string>;

// All this crap is just to swig wrap a char* into a DataIO as a string
%include "std_string.i"
%extend clockwerk::DataIO<char*> {
  // Route through setValueFromString rather than pointing the signal straight
  // at s.c_str(): the Python string is a temporary here, so the signal has to
  // take its own copy of the value to still hold it after this returns
  void set(const std::string& s) {$self->setValueFromString(s.c_str());}
  std::string get() const {const char* p = (*$self)();return p ? std::string(p) : std::string();}

  %pythoncode %{
  # Make obj("...") work with Python str by dispatching to set/get
  def __call__(self, *args):
      if len(args) == 0:
          return self.get()
      if len(args) == 1 and isinstance(args[0], str):
          return self.set(args[0])
      # fall back to the original overloads (e.g., bytes)
      return _WarpTwinPy.DataIOCharPtr___call__(self, *args)
  %}
}
%template(DataIOCharPtr) clockwerk::DataIO<char*>;

%template(DataIOInt) clockwerk::DataIO<int>;
%template(DataIOUInt) clockwerk::DataIO<unsigned int>;

%template(DataIOUInt8) clockwerk::DataIO<uint8>;
%template(DataIOUInt16) clockwerk::DataIO<uint16>;
%template(DataIOInt8) clockwerk::DataIO<int8>;
%template(DataIOInt16) clockwerk::DataIO<int16>;

// Vector types supported by DataIO
%template(DataIOVectorDouble) clockwerk::DataIO<std::vector<double>>;
%template(DataIOVectorFloat) clockwerk::DataIO<std::vector<float>>;
%template(DataIOVectorInt) clockwerk::DataIO<std::vector<int>>;

// Custom types supported by DataIO
%template(DataIOTime) clockwerk::DataIO<clockwerk::Time>;

%template(DataIOMatrix2) clockwerk::DataIO<clockwerk::Matrix<2, 2>>;
%template(DataIOMatrix3) clockwerk::DataIO<clockwerk::Matrix<3, 3>>;
%template(DataIOMatrix4) clockwerk::DataIO<clockwerk::Matrix<4, 4>>;
%template(DataIOMatrix6) clockwerk::DataIO<clockwerk::Matrix<6, 6>>;
%template(DataIOMatrix16) clockwerk::DataIO<clockwerk::Matrix<16, 16>>;
%template(DataIOMatrix10) clockwerk::DataIO<clockwerk::Matrix<10, 10>>;
%template(DataIOMatrix21) clockwerk::DataIO<clockwerk::Matrix<2, 1>>;
%template(DataIOMatrix31) clockwerk::DataIO<clockwerk::Matrix<3, 1>>;
%template(DataIOMatrix41) clockwerk::DataIO<clockwerk::Matrix<4, 1>>;
%template(DataIOMatrix61) clockwerk::DataIO<clockwerk::Matrix<6, 1>>;
%template(DataIOMatrix63) clockwerk::DataIO<clockwerk::Matrix<6, 3>>;

%template(DataIOCartesianVector2) clockwerk::DataIO<clockwerk::CartesianVector<2>>;
%template(DataIOCartesianVector3) clockwerk::DataIO<clockwerk::CartesianVector<3>>;
%template(DataIOCartesianVector4) clockwerk::DataIO<clockwerk::CartesianVector<4>>;
%template(DataIOCartesianVector6) clockwerk::DataIO<clockwerk::CartesianVector<6>>;
%template(DataIOCartesianVector16) clockwerk::DataIO<clockwerk::CartesianVector<16>>;

%template(DataIODCM) clockwerk::DataIO<clockwerk::DCM>;
%template(DataIOEuler321) clockwerk::DataIO<clockwerk::Euler321>;
%template(DataIOMRP) clockwerk::DataIO<clockwerk::MRP>;
%template(DataIOQuaternion) clockwerk::DataIO<clockwerk::Quaternion>;

%template(DataIOJointPtr) clockwerk::DataIO<warptwin::Joint*>;
%template(DataIOFrameDPtr) clockwerk::DataIO<warptwin::Frame*>;
%template(DataIOBodyPtr) clockwerk::DataIO<warptwin::Body*>;
%template(DataIONodePtr) clockwerk::DataIO<warptwin::Node*>;
%template(DataIOGTPtr) clockwerk::DataIO<clockwerk::GraphTreeObject*>;

%template(VecFramePtr) std::vector<warptwin::Frame*>;

%include <std_vector.i>
%include <std_string.i>
%include <stl.i>

%template(VecDouble) std::vector<double>;
%template(VecDouble2d) std::vector<std::vector<double>>;

// PlanetRel stuff
%include "utils/planetrelutils.h"
%include "gncutils/states/planetrelutils.h"
%include "utils/googleearthkml.h"

