###############################################################################
# Copyright (c) ATTX INC 2026. All Rights Reserved.
#
# This software and associated documentation (the "Software") are the 
# proprietary and confidential information of ATTX, INC. The Software is 
# furnished under a license agreement between ATTX and the user organization 
# and may be used or copied only in accordance with the terms of the agreement.
# Refer to 'license/attx_license.adoc' for standard license terms.
#
# EXPORT CONTROL NOTICE: THIS SOFTWARE MAY INCLUDE CONTENT CONTROLLED UNDER THE
# INTERNATIONAL TRAFFIC IN ARMS REGULATIONS (ITAR) OR THE EXPORT ADMINISTRATION 
# REGULATIONS (EAR99). No part of the Software may be used, reproduced, or 
# transmitted in any form or by any means, for any purpose, without the express 
# written permission of ATTX, INC.
###############################################################################
"""
Spacecraft Constellation Tutorial
---------------------------------
This example shows how to create a constellation of spacecraft in WarpTwin
and visualize them using the visuals model.

Author: Alex Reynolds
"""
import sys
from warptwin.WarpTwinPy import (Time, SimulationExecutive, Frame, Node, 
                                     Body, CartesianVector3, Hdf5Logger, connectSignals,
                                     DEGREES_TO_RADIANS, HOURS_TO_SECONDS)
from warptwin.Spacecraft import Spacecraft
from warptwin.OrbitalElementsStateInit import OrbitalElementsStateInit
from warptwin.SpicePlanet import SpicePlanet
from warptwin.FrameStateSensorModel import FrameStateSensorModel
from warptwin.VisualsModel import VisualsModel
from warptwin.EarthObservationModel import EarthObservationModel

##########################################################################
# PARAMETERS FOR SPACECRAFT CONSTELLATION STUDY
##########################################################################
SIM_RUNTIME = 10                    # hours

# Orbit Parameters
# The following parameters are defined to configure a single constellation of 
# spacecraft in a single orbit with even spacing. Additional inclinations,
# altitudes, RAAN, etc. can easily be added by following this example.
TOTAL_NUM_SATELLITES = 10
ORBIT_SEMIMAJOR_AXIS = 6678.14e3                # km   
ORBIT_ECCENTRICITY = 0.0000001
ORBIT_INCLINATION = 97.0                        # degrees
ORBIT_RAAN = 10.0                               # degrees

# Create our base simulation infrastructure
exc = SimulationExecutive()                                                 # Create our executive -- by convention named exc
exc.setRateSec(5.0)                                                         # We can setRateHz or setRateSec -- default is 1 second
exc.args().addDefaultArgument("end",     SIM_RUNTIME*HOURS_TO_SECONDS)      # Default can be overridden by command line
exc.parseArgs(sys.argv)                                                     # This interperets command-line inputs

# Create instances of the Earth and Sun as SPICE planets
earth = SpicePlanet(exc, "earth")
sun = SpicePlanet(exc, "sun")

# Now loop and create our spacecraft constellation
spacecraft = []
for i in range(TOTAL_NUM_SATELLITES):
    spacecraft.append(Spacecraft(exc, "sc_" + str(i)))          # Create the spacecraft
    spacecraft[i].params.planet_ptr(earth)                      # Configure it from earth

# Add an Earth Observation Model to each spacecraft
eom = []
for i in range(TOTAL_NUM_SATELLITES):
    eom.append(EarthObservationModel(exc, "eom_" + str(i)))
    eom[i].params.planet_rotating_frame(earth.outputs.rotating_frame())    # Set the planet rotating frame to Earth
    eom[i].params.spacecraft_frame(spacecraft[i].outputs.body())           # Set the spacecraft frame to the body frame of the spacecraft
    eom[i].params.target_lat_rad(DEGREES_TO_RADIANS*40.0)                  # Set the ground station geocentric longitude in radians
    eom[i].params.target_lon_rad(DEGREES_TO_RADIANS*-105.0)                # Set the ground station longitude in radians
    eom[i].params.off_nadir_mask_rad(70.0*DEGREES_TO_RADIANS)              # Off-nadir mask in radians

# And set up logging for just a single spacecraft
log = Hdf5Logger(exc, "states.h5")
log.addParameter(exc.time().base_time,                  "time")
log.addParameter(spacecraft[0].outputs.pos_sc_pci,      "eci_pos")
log.addParameter(spacecraft[0].outputs.vel_sc_pci,      "eci_vel")
log.addParameter(eom[0].outputs.look_angle,             "look_angle_rad")
log.addParameter(eom[0].outputs.range,                  "range_m")
log.addParameter(eom[0].outputs.range_rate,             "range_rate_mps")
log.addParameter(eom[0].outputs.visible,                "visible")
log.addParameter(eom[0].outputs.total_visits,           "visits")
exc.logManager().addLog(log, 10)

exc.startup()

# Now loop and initialize our spacecraft states with equal spacing. Note this
# must occur after startup
for i in range(TOTAL_NUM_SATELLITES):
    spacecraft[i].initializeFromOrbitalElements(ORBIT_SEMIMAJOR_AXIS, 
                                                ORBIT_ECCENTRICITY, 
                                                DEGREES_TO_RADIANS*ORBIT_INCLINATION, 
                                                DEGREES_TO_RADIANS*ORBIT_RAAN, 
                                                0.0, 
                                                DEGREES_TO_RADIANS*i*(361.0/TOTAL_NUM_SATELLITES))

exc.run()