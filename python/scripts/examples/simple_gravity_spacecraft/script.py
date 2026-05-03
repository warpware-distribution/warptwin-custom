###############################################################################
# Copyright (c) ATTX INC 2026. All Rights Reserved.
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
"""
Simple Point Mass Gravity Spacecraft Tutorial
----------------------------------
This is an example code that uses the Spacecraft construct 
and propagates a spacecraft orbit for 5400 seconds.
It also logs the simulation time, spacecraft position, 
and spacecraft velocity to a csv file.

Author: Alex Jackson
"""
import sys
from warptwin.Spacecraft import Spacecraft
from warptwin.WarpTwinPy import SimulationExecutive, Hdf5Logger, DEGREES_TO_RADIANS, connectSignals, CartesianVector3, Quaternion, Time, LOG_DEBUG
from warptwin.SpicePlanet import SpicePlanet
from warptwin.FrameStateSensorModel import FrameStateSensorModel
from warptwin.PlanetRelativeStatesModel import PlanetRelativeStatesModel
from warptwin.AsphericalGravityModel import AsphericalGravityModel
from warptwin.MSISAtmosphereModel import MSISAtmosphereModel
from warptwin.FlatPlateDragModel import FlatPlateDragModel

exc = SimulationExecutive()     # Create our executive -- by convention named exc
exc.parseArgs(sys.argv)         # this interperets command-line inputs
exc.setRateHz(1)                #  We can setRateHz or setRateSec -- default is 1 second
# exc.logLevel(LOG_DEBUG)

earth = SpicePlanet(exc, "earth")

sc = Spacecraft(exc, "sc")
sc.params.planet_ptr(earth)

states = Hdf5Logger(exc, "sc_states.h5")
states.addParameter('.exc.schedule.time.base_time', "sim_time")     # Example adding time by string
states.addParameter(sc.outputs.pos_sc_pci, "sc_inrtl_position")
states.addParameter(sc.planetRelativeModel().outputs.latitude_detic, "latitude")
states.addParameter(sc.planetRelativeModel().outputs.longitude, "longitude")
states.addParameter(sc.planetRelativeModel().outputs.altitude_detic, "altitude_m")
exc.logManager().addLog(states, 1)

exc.startup()

sc.initializeFromOrbitalElements(7278137.0, 0.1, DEGREES_TO_RADIANS*40.0, DEGREES_TO_RADIANS*10.0, DEGREES_TO_RADIANS*10.0, DEGREES_TO_RADIANS*30.0)

exc.run()