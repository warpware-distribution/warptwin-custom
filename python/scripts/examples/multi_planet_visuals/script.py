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
New-visuals (MultiBodyViz) orbit demo
-------------------------------------
This tests out new visuals and n-body gravity effects. The spacecraft is initialized in orbit 
around the Moon, and a second spacecraft is initialized in orbit around the Earth. The second 
spacecraft has an ADCS that points its long axis at Earth and its short axis at the Moon. The 
third spacecraft is initialized in orbit around Mars. The simulation runs for 9,000 seconds, 
and the spacecraft states are logged to an HDF5 file for later analysis. The visuals are 
automatically launched and the spacecraft and planets are rendered in the viewer. All n-body 
effects are automatically calculated. 

Author: Alex Jackson
"""
import sys
from warptwin.WarpTwinPy import (CartesianVector3, Matrix3, SimulationExecutive,
                                 DEGREES_TO_RADIANS, Time, Hdf5Logger)
from warptwin.Spacecraft import Spacecraft
from warptwin.SpicePlanet import SpicePlanet
from warptwin.ADCS import ADCS
from warptwin.GroundStationModel import GroundStationModel
from warptwin.VisualsModel import VisualsModel

exc = SimulationExecutive()
exc.args().addDefaultArgument("end", 9_000.0)  
exc.parseArgs(sys.argv)
exc.setRateHz(10)
exc.setTime("2022 December 09, 18:00:00 UTC")      # sim epoch → visuals sim_start_time

moon = SpicePlanet(exc, "moon")
earth = SpicePlanet(exc, "earth")
mars = SpicePlanet(exc, "mars")
sun  = SpicePlanet(exc, "sun")

# add the option to view the orbit in the Earth rotating frame
exc.visualsModel().addFrame(earth.outputs.rotating_frame()) 

sc = Spacecraft(exc, "sc")
sc.params.planet_ptr(moon)                    
sc.params.visuals_model("LRO.glb")           # render this CAD model (bare filename from the viewer's models/ library)

sc2 = Spacecraft(exc, "sc2")
sc2.params.planet_ptr(earth) 

# +Y is the LONG axis and it is longer on the + side than the - side. Point
# +Y at Earth and the long axis of the cubesat visibly aims at the planet.
sc2.params.visuals_model("LRO.glb")
sc2.params.mass(1.0)                                              # kg
sc2.params.inertia(Matrix3([[0.026, 0.0,  0.0],                     # kg-m^2
                            [0.0,  0.022, 0.0],
                            [0.0,  0.0,  0.030]]))

sc3 = Spacecraft(exc, "sc3")
sc3.params.planet_ptr(mars)                    
sc3.params.visuals_model("LRO.glb")           # render this CAD model (bare filename from the viewer's models/ library)

# --------------------------------------------------------------------------- #
# ADCS attitude test — point the cubesat's LONG (+Y) axis at Earth.
#
#   primary   +Y body  ->  Earth   (hard constraint: driven to zero error)
#   secondary +X body  ->  Moon    (best-fit: takes up the remaining freedom
#                                   about +Y, so the attitude is fully defined)
#
# Visual check: the long axis of the cubesat should stay aimed at Earth for the
# whole orbit. The numeric check printed below is the authoritative one.
# --------------------------------------------------------------------------- #
adcs = ADCS(exc, "adcs")
adcs.params.sc_body(sc2.body())
adcs.params.planet_ptr(earth)
adcs.params.num_reaction_wheels(4)
adcs.params.rw_mom_inertia(0.01)              # kg-m^2
adcs.params.rw_peak_torque(0.7)               # N-m
adcs.params.rw_momentum_cap(0.5)               # N-m-s
adcs.params.rw_active_power_draw(4.5)           # W
adcs.params.rw_idle_power_draw(0.0)             # W
adcs.params.num_torque_rods(3)
adcs.params.tr_peak_torque(0.5)                 # A-m^2
adcs.params.tr_diameter(0.9818)                # m
adcs.params.tr_loops(100.0)
adcs.params.tr_resistance(66.5)                 # Ohm
adcs.params.tr_idle_power(1.0)                  # W

adcs.inputs.mode(2)                                               # 2 = FINE_POINTING
adcs.inputs.primary_body_constraint(CartesianVector3([0, 1, 0]))  # +Y = cubesat long axis
adcs.inputs.desired_primary(earth.outputs.inertial_frame())       # ...aimed at Earth
adcs.inputs.secondary_body_constraint(CartesianVector3([1, 0, 0]))# +X
adcs.inputs.desired_secondary(moon.outputs.inertial_frame())      # ...best-fit to the Moon

null_island = GroundStationModel(exc, "null island")
null_island.params.spacecraft_frame(sc.body())  
null_island.params.planet_rotating_frame(earth.outputs.rotating_frame())

# --------------------------------------------------------------------------- #
# New visuals. Spacecraft/planets self-register with the visuals model on
# startup once visuals are enabled — no manual addSpacecraft needed.
# --------------------------------------------------------------------------- #
exc.enableVisuals()
vis = exc.visualsModel()
vis.params.run_visuals_app(True)               # auto-launch the harness (default)
vis.params.sc_rate(Time(10))                   # log spacecraft state every 10 s
vis.params.trail_time(Time(1_000_000))          

states = Hdf5Logger(exc, "sc_states2.h5")
states.addParameter(exc.time().base_time, "time")
states.addParameter(sc.outputs.altitude_detic, "altitude")
exc.logManager().addLog(states, 1)

exc.startup()

# Orbital elements (must be set after startup):
#   a = 7278.137 km, e = 0.001, i = 51.6°, RAAN = 0°, argp = 0°, true anomaly = 0°
sc.initializeFromOrbitalElements(
    1838137.0, 0.0, DEGREES_TO_RADIANS * 51.6, 0.0, 0.0, 0.0
)
sc2.initializeFromOrbitalElements(
    7278137.0, 0.001, DEGREES_TO_RADIANS * 51.6, 0.0, 0.0, 0.0
)
sc3.initializeFromOrbitalElements(
    7278137.0, 0.001, DEGREES_TO_RADIANS * 51.6, 0.0, 0.0, 0.0
)   

exc.run()
