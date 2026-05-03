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

#pragma SWIG nowarn=302,509,362,389
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
%ignore clockwerk::GraphTreeObject::children;
%ignore warpos::FlightExecutive::getRegistry;
%ignore warpos::GpioConfig_t;
%ignore warpos::SpiConfig_t;
%ignore warpos::UartConfig_t;
%ignore warpos::I2cConfig_t;
%ignore warpos::PwmConfig_t;
%ignore warpos::Os::yield;

%include "types.h"
%include "configuration.h"

// Swig include of core modules
%include "core/Matrix.hpp"
%include "core/CartesianVector.hpp"
%include "core/matrixmath.hpp"
%include "core/vectormath.hpp"

%template(DoubleArray2) std::array<double, 2>;
%template(DoubleArray3) std::array<double, 3>;
%template(DoubleArray4) std::array<double, 4>;
%template(DoubleArray6) std::array<double, 6>;
%template(DoubleArray22) std::array<std::array<double, 2>, 2>;
%template(DoubleArray33) std::array<std::array<double, 3>, 3>;
%template(DoubleArray44) std::array<std::array<double, 4>, 4>;
%template(DoubleArray66) std::array<std::array<double, 6>, 6>;
%template(DoubleArray63) std::array<std::array<double, 3>, 6>;

%template(Matrix2) clockwerk::Matrix<2, 2>;
%template(Matrix3) clockwerk::Matrix<3, 3>;
%template(Matrix4) clockwerk::Matrix<4, 4>;
%template(Matrix6) clockwerk::Matrix<6, 6>;
%template(Matrix16) clockwerk::Matrix<16, 16>;
%template(Matrix21) clockwerk::Matrix<2, 1>;
%template(Matrix31) clockwerk::Matrix<3, 1>;
%template(Matrix41) clockwerk::Matrix<4, 1>;
%template(Matrix61) clockwerk::Matrix<6, 1>;
%template(Matrix63) clockwerk::Matrix<6, 3>;

%template(CartesianVector2) clockwerk::CartesianVector<2>;
%template(CartesianVector3) clockwerk::CartesianVector<3>;
%template(CartesianVector4) clockwerk::CartesianVector<4>;
%template(CartesianVector6) clockwerk::CartesianVector<6>;

// Attitude
%include "dynamics/DCM.h"
%include "dynamics/Euler321.h"
%include "dynamics/MRP.h"
%include "dynamics/Quaternion.h"

// Data management
%include "architecture/GraphTreeObject.h"
%include "architecture/Time.h"
%include "architecture/DataIOBase.h"
%include "architecture/DataIO.hpp"
%include "architecture/signalutils.h"

// warpOS Includes
%include "flight/FlightExecutive.h"
%include "flight/App.h"
%include "flight/OS.h"
%include "flight/Platform.h"
%include "flight/Setup.h"
%include "flight/Scheduler.h"
%include "flight/flighterrors.h"

// Frames
%include "architecture/GraphTreeObject.h"
%include "frames/Joint.h"
%include "frames/Frame.h"
%include "frames/Body.h"
%include "frames/Node.h"
%include "frames/frameutils.h"

// Logging
%include "logging/SimLogger.h"
%include "logging/CsvLogger.h"
%include "logging/Hdf5Logger.h"
%include "logging/LogManager.h"

// Unit utils
%include "constants/unitutils.h"
%include "cr3bputils/conversions.h"
%immutable;
%include "constants/planetdefaults.h"
%mutable;

// Spice manager
%include "utils/spiceutils.h"

// Simulation
%include "simulation/SimulationSteps.h"
%include "simulation/DispersionEngine.h"
%include "simulation/SimTimeManager.h"
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
  void set(const std::string& s) {(*$self)(const_cast<char*>(s.c_str()));}
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
%template(DataIOMatrix21) clockwerk::DataIO<clockwerk::Matrix<2, 1>>;
%template(DataIOMatrix31) clockwerk::DataIO<clockwerk::Matrix<3, 1>>;
%template(DataIOMatrix41) clockwerk::DataIO<clockwerk::Matrix<4, 1>>;
%template(DataIOMatrix61) clockwerk::DataIO<clockwerk::Matrix<6, 1>>;
%template(DataIOMatrix63) clockwerk::DataIO<clockwerk::Matrix<6, 3>>;

%template(DataIOCartesianVector2) clockwerk::DataIO<clockwerk::CartesianVector<2>>;
%template(DataIOCartesianVector3) clockwerk::DataIO<clockwerk::CartesianVector<3>>;
%template(DataIOCartesianVector4) clockwerk::DataIO<clockwerk::CartesianVector<4>>;
%template(DataIOCartesianVector6) clockwerk::DataIO<clockwerk::CartesianVector<6>>;

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

%template(VecString) std::vector<std::string>;
%template(VecDouble) std::vector<double>;
%template(VecDouble2d) std::vector<std::vector<double>>;

// PlanetRel stuff
%include "utils/planetrelutils.h"
%include "gncutils/states/planetrelutils.h"
%include "utils/googleearthkml.h"