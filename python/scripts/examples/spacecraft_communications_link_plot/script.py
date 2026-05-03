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
Simple LivePlot tutorial
-------------------------
This is an example code that uses the Spacecraft construct 
and propagates a spacecraft orbit for 100 seconds.
It liveplots the spacecraft orbit in 2D.

Author: Alex Reynolds
"""
import sys
from warptwin.WarpTwinPy import (Time, SimulationExecutive, Frame, Node, 
                                     Body, CartesianVector3, CsvLogger, connectSignals,
                                     DEGREES_TO_RADIANS)
from warptwin.Spacecraft import Spacecraft
from warptwin.OrbitalElementsStateInit import OrbitalElementsStateInit
from warptwin.SpicePlanet import SpicePlanet
from warptwin.FrameStateSensorModel import FrameStateSensorModel
from warptwin.SpacecraftLinkModel import SpacecraftLinkModel
from warptwin.GroundStationModel import GroundStationModel

# Create a simple simulation to plot a spacecraft
exc = SimulationExecutive()     # Create our executive -- by convention named exc
exc.args().addDefaultArgument("end",     10000)
exc.parseArgs(sys.argv)         # this interperets command-line inputs

# Create a planet and spacecraft
earth = SpicePlanet(exc, "earth")

oe_state = OrbitalElementsStateInit(exc, "oe")

sc = Spacecraft(exc, "sc")
connectSignals(oe_state.outputs.pos__inertial, sc.params.initial_position)
connectSignals(oe_state.outputs.vel__inertial, sc.params.initial_velocity)
sc.params.planet_ptr(earth)

oe_state.params.a(9314000.0)
oe_state.params.e(0.3)
oe_state.params.i(0.4)
oe_state.params.RAAN(0.0)
oe_state.params.w(0.0)
oe_state.params.f(0.0)

# Create our attx groundstation
attx = GroundStationModel(exc, "attx")                                  #Create the ground station and establish the ENU frame   
attx.params.spacecraft_frame.mapTo(sc.outputs.body)                     #Assign the spacecraft that we will be tracking
attx.params.planet_rotating_frame.mapTo(earth.outputs.rotating_frame)   #Set the planet fixed frame
attx.params.R_planet(6378140.0)                                         #Set the ground station radius from the center of the Earth 
attx.params.latitude_detic_rad(DEGREES_TO_RADIANS*40.0)               #Set the ground station geocentric longitude in radians
attx.params.longitude_rad(DEGREES_TO_RADIANS*-105.0)                    #Set the ground station longitude in radians
attx.params.elevation_mask_rad(DEGREES_TO_RADIANS*10.0)                 #Set the elevation mask in radians

scs = []
oes = []
scls = []
c_links = []
gs = []
MAX_RANGE = 1000000
for i in range(10):
    # Generate spacecraft and add orbital elements
    oes.append(OrbitalElementsStateInit(exc, "oe_" + str(i)))
    scs.append(Spacecraft(exc, "sc_" + str(i)))

    # Produce a link between spacecraft and the constellation
    scls.append(SpacecraftLinkModel(exc, "scl_" + str(i)))
    scls[i].params.sc_1_frame(sc.body())
    scls[i].params.sc_2_frame(scs[i].body())
    scls[i].params.planet_frame(earth.outputs.inertial_frame())
    # scls[i].params.max_range(MAX_RANGE)

    # Produce intra-constellation links
    for j in range(i):
        c_links.append(SpacecraftLinkModel(exc, "sc" + str(i) + "_" + str(j)))
        c_links[-1].params.sc_1_frame(scs[i].body())
        c_links[-1].params.sc_2_frame(scs[j].body())
        c_links[-1].params.planet_frame(earth.outputs.inertial_frame())
        # c_links[-1].params.max_range(MAX_RANGE)

    # Create our attx groundstation
    gs.append(GroundStationModel(exc, "attx_" + str(i)))                                  #Create the ground station and establish the ENU frame   
    gs[-1].params.spacecraft_frame.mapTo(scs[i].outputs.body)                     #Assign the spacecraft that we will be tracking
    gs[-1].params.planet_rotating_frame.mapTo(earth.outputs.rotating_frame)   #Set the planet fixed frame
    gs[-1].params.R_planet(6378140.0)                                         #Set the ground station radius from the center of the Earth 
    gs[-1].params.latitude_detic_rad(DEGREES_TO_RADIANS*40.0)               #Set the ground station geocentric longitude in radians
    gs[-1].params.longitude_rad(DEGREES_TO_RADIANS*-105.0)                    #Set the ground station longitude in radians
    gs[-1].params.elevation_mask_rad(DEGREES_TO_RADIANS*10.0)                 #Set the elevation mask in radians
    
    connectSignals(oes[i].outputs.pos__inertial, scs[i].params.initial_position)
    connectSignals(oes[i].outputs.vel__inertial, scs[i].params.initial_velocity)
    scs[i].params.planet_ptr(earth)
    
    oes[i].params.a(8000000)
    oes[i].params.e(0.01)
    oes[i].params.i(97.0*DEGREES_TO_RADIANS)
    oes[i].params.RAAN(9.0*i*DEGREES_TO_RADIANS)
    oes[i].params.w(1.0)
    oes[i].params.f(2.0*i)

exc.startup()

exc.run()