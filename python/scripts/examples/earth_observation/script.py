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
Earth Observation Example
-------------------------
This example shows setting up one or multiple WarpTwin spacecraft models to perform an earth
observation mission on multiple ground sites.

Author: Alex Reynolds
"""
import sys
from warptwin.WarpTwinPy import (Time, SimulationExecutive, Frame, Node, 
                                     Body, CartesianVector3, CsvLogger, connectSignals,
                                     DEGREES_TO_RADIANS, HOURS_TO_SECONDS, LOG_DEBUG,
                                     END_STEP)
from warptwin.Spacecraft import Spacecraft
from warptwin.OrbitalElementsStateInit import OrbitalElementsStateInit
from warptwin.SpicePlanet import SpicePlanet
from warptwin.FrameStateSensorModel import FrameStateSensorModel
from warptwin.VisualsModel import VisualsModel
from warptwin.EarthObservationModel import EarthObservationModel
from warptwin.StarTracker import StarTracker
from warptwin.TwoAxisPointingGuidance import TwoAxisPointingGuidance
from warptwin.PdAttitudeControl import PdAttitudeControl
from warptwinutils.orbitutils import computeSunSyncElements

##########################################################################
# PARAMETERS FOR SPACECRAFT CONSTELLATION STUDY
##########################################################################
SIM_RUNTIME = 10                    # hours

# Orbit Parameters
# The following parameters are defined to configure a single constellation of 
# spacecraft in a single sun synchronous orbit with even spacing. Additional inclinations,
# altitudes, RAAN, etc. can easily be added by following this example.
TOTAL_NUM_SATELLITES = 3
ORBIT_ALTITUDE = 500                            # km   
ORBIT_ASC_NODE = 5.5                              # Hours
TARGET_OBS_SITES = [
    [40.0, -105.0],
    [26.907115, -11.522161],
    [17.16, -14.0]
]   # lat, lon (deg)

# Create our base simulation infrastructure
exc = SimulationExecutive()                                                 # Create our executive -- by convention named exc
exc.setRateHz(10)                                                           # We can setRateHz or setRateSec -- default is 1 second
exc.args().addDefaultArgument("end",     SIM_RUNTIME*HOURS_TO_SECONDS)      # Default can be overridden by command line
exc.parseArgs(sys.argv)                                                     # This interperets command-line inputs

# Manually enable visuals because we want to see our slews, and that requires faster rates.
# Normally you do not need to do this and can instead do by --enable-visuals=true in script args
# For anything with fast attitude maneuvers it may be worth enabling visuals and manually setting 
# spacecraft rate higher
exc.enableVisuals()
exc.visualsModel().params.sc_rate(Time(1, 0))

# Create instances of the Earth and Sun as SPICE planets
earth = SpicePlanet(exc, "earth")
sun = SpicePlanet(exc, "sun")

# Now loop and create our spacecraft constellation
spacecraft = []
for i in range(TOTAL_NUM_SATELLITES):
    spacecraft.append(Spacecraft(exc, "sc_" + str(i)))          # Create the spacecraft
    spacecraft[i].params.planet_ptr(earth)                      # Configure it from earth

# Add Earth Observation Models to each spacecraft
eom = []
for i in range(TOTAL_NUM_SATELLITES):
    eom.append([])
    for j in range(len(TARGET_OBS_SITES)):
        eom[i].append(EarthObservationModel(exc, "site" + str(i) + str(j)))
        eom[i][j].params.planet_rotating_frame(earth.outputs.rotating_frame())       # Set the planet rotating frame to Earth
        eom[i][j].params.spacecraft_frame(spacecraft[i].outputs.body())              # Set the spacecraft frame to the body frame of the spacecraft
        eom[i][j].params.target_lat_rad(DEGREES_TO_RADIANS*TARGET_OBS_SITES[j][0])   # Set the ground station geocentric longitude in radians
        eom[i][j].params.target_lon_rad(DEGREES_TO_RADIANS*TARGET_OBS_SITES[j][1])   # Set the ground station longitude in radians
        eom[i][j].params.off_nadir_mask_rad(60.0*DEGREES_TO_RADIANS)                 # Off-nadir mask in radians

# Add star trackers to each spacecraft
# These are just here for visualization -- we're not going to use their output and we're using
# them in a nonsensical way, i.e. pointed at Earth
cameras = []
for i in range(TOTAL_NUM_SATELLITES):
    cameras.append(StarTracker(exc, "camera" + str(i)))
    cameras[i].params.mount_frame(spacecraft[i].outputs.body())

# Add pointing guidance to each spacecraft
guidance = []
for i in range(TOTAL_NUM_SATELLITES):
    guidance.append(TwoAxisPointingGuidance(exc))
    exc.registerApp(guidance[i], END_STEP)           # Apps must be scheduled manually -- not automatic!

# Finally configure logging
states = CsvLogger(exc, "sc_states.csv")
states.addParameter('.exc.schedule.time.base_time', "time")     # Example adding time by string
states.addParameter(spacecraft[0].outputs.quat_sc_pci, "sc_quat_sim")
exc.logManager().addLog(states, 1)

err = exc.startup()
if(err):
    exit(1)

# Now loop and initialize our spacecraft states with equal spacing. Note this
# must occur after startup
(a_km, e, i_rad, raan_rad, aop_rad, ltan_hours) = computeSunSyncElements(ORBIT_ALTITUDE, 
                                                                         sun.outputs.inertial_frame().rootRelPosition(), 
                                                                         ORBIT_ASC_NODE)
for i in range(TOTAL_NUM_SATELLITES):
    spacecraft[i].initializeFromOrbitalElements(a_km*1000.0, 
                                                e, 
                                                i_rad, 
                                                raan_rad, 
                                                aop_rad, 
                                                DEGREES_TO_RADIANS*i*(361.0/TOTAL_NUM_SATELLITES))

exc.step(Time(0))
while not exc.isTerminated():
    # Select the spacecraft target site manually
    for i in range(TOTAL_NUM_SATELLITES):
        closest_idx = -1
        closest_range = 999999999999999999
        for j in range(len(TARGET_OBS_SITES)):
            if eom[i][j].outputs.visible():
                if eom[i][j].outputs.range() < closest_range:
                    closest_range = eom[i][j].outputs.range()
                    closest_idx = j
            
        if closest_idx >= 0:
            target = CartesianVector3([
                eom[i][closest_idx].outputs.site_position__pci().get(0) - spacecraft[i].outputs.pos_sc_pci().get(0),
                eom[i][closest_idx].outputs.site_position__pci().get(1) - spacecraft[i].outputs.pos_sc_pci().get(1),
                eom[i][closest_idx].outputs.site_position__pci().get(2) - spacecraft[i].outputs.pos_sc_pci().get(2),
            ])
            guidance[i].inputs.desired_primary(target)
        else:
            target = CartesianVector3([
                -spacecraft[i].outputs.pos_sc_pci().get(0),
                -spacecraft[i].outputs.pos_sc_pci().get(1),
                -spacecraft[i].outputs.pos_sc_pci().get(2)
            ])
            guidance[i].inputs.desired_primary(target)

        spacecraft[i].body().setRootRelAttitude(guidance[i].outputs.quat_body_ref())

        next_time = exc.time().base_time().asFloatingPoint()

    err = exc.step()
    if(err):
        print("Error on step. Code " + str(err))
        exit(1)