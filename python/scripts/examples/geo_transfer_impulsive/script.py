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
# written permission of ATTX, INC.
###############################################################################
"""
Electric Propulsion Transfer GTO-->GEO
--------------------------------------
This script demonstrates a simple analysis with spacecraft transfer from LEO to GEO
using the WarpTwin Lambert solver to achieve the transfer.
"""
import sys, math
import numpy as np
from warptwin.WarpTwinPy import (SimulationExecutive, CsvLogger, DEGREES_TO_RADIANS,
                                     Time, Node, END_STEP, connectSignals, CartesianVector3,
                                     Frame, NOT_SCHEDULED)
from warptwin.CustomPlanet import CustomPlanet
from warptwin.Spacecraft import Spacecraft
from warptwin.OrbitalElementsSensorModel import OrbitalElementsSensorModel
from warptwin.OrbitalElementsStateInit import OrbitalElementsStateInit
from warptwinutils.lambert import lambert

##########################################################################
# PARAMETERS FOR SPACECRAFT LAMBERT TOF STUDY
##########################################################################
# Starting Orbit
# These orbital elements represent the starting orbit for the spacecraft
# and are provided as a/e/i/RAAN/w/ta
STARTING_ORBIT = [6878140, 0.00001, 28*DEGREES_TO_RADIANS, 0, 0, 0]        # 500 km orbit

# Insertion orbit
# The insertion orbit represents a particular point at GEO into which we want
# to insert. Here we've selected a phase almost 180 degrees from our start for 
# a hohmann transfer. This is to avoid a singularity at 180 degrees which
# occurs in the f and g functions used to calculate the transfer
INSERTION_ORBIT = [42000000, 0.00001, 28*DEGREES_TO_RADIANS, 0, 0, 179.5*DEGREES_TO_RADIANS] # GEO

# Set the range of times of flight to try and granularity of the search
TOF_RANGE = [6*3600, 16*3600]
TOF_GRANULARITY = 500

##########################################################################
# END SCRIPT INPUTS
##########################################################################

# Boilerplate simulation executive initialization
exc = SimulationExecutive()     # Create our executive -- by convention named exc
exc.args().addDefaultArgument("end",     1.0*86400.0)
exc.parseArgs(sys.argv)         # this interperets command-line inputs
exc.setTime("2026 FEB 28 12:00:00.000")     # Arbitrarily set date to guess for launch date
step_size = 1.0
exc.setRateSec(step_size)

# Create an Earth SPICE planet for our propagation
earth = CustomPlanet(exc, "earth")

# Generate spacecraft and configure mass
sc = Spacecraft(exc, "sc")
sc.params.planet_ptr(earth.outputs.self_id())
sc.params.mass(500) # kg

# Generate a model to output our spacecraft orbital elements for control and plotting
sc_oe = OrbitalElementsSensorModel(exc, "sc_oe")
connectSignals(sc.outputs.pos_sc_pci, sc_oe.inputs.pos__inertial)
connectSignals(sc.outputs.vel_sc_pci, sc_oe.inputs.vel__inertial)

# Set up logging
states = CsvLogger(exc, "states.csv")
states.addParameter('.exc.schedule.time.base_time', "time")
states.addParameter(sc.outputs.pos_sc_pci, "pos")
states.addParameter(sc.outputs.latitude_detic, "latitude")
states.addParameter(sc.outputs.longitude, "longitude")
states.addParameter(sc.outputs.altitude_detic, "altitude_m")
states.addParameter(sc_oe.outputs.a, "a")
states.addParameter(sc_oe.outputs.e, "e")
states.addParameter(sc_oe.outputs.i, "i")
states.addParameter(sc.params.mass, "mass")
exc.logManager().addLog(states, Time(1))

# Schedule burns
# First get our XYZ position and velocity at starting orbit and geo
sc_init = OrbitalElementsStateInit(exc, NOT_SCHEDULED, "sc_init")

# LEO start
sc_init.params.a(STARTING_ORBIT[0])
sc_init.params.e(STARTING_ORBIT[1])
sc_init.params.i(STARTING_ORBIT[2])
sc_init.params.RAAN(STARTING_ORBIT[3])
sc_init.params.w(STARTING_ORBIT[4])
sc_init.params.f(STARTING_ORBIT[5])
sc_init.startup()
p_start = [sc_init.outputs.pos__inertial().get(0), sc_init.outputs.pos__inertial().get(1), sc_init.outputs.pos__inertial().get(2)]
v_start = [sc_init.outputs.vel__inertial().get(0), sc_init.outputs.vel__inertial().get(1), sc_init.outputs.vel__inertial().get(2)]

# GEO insertion
sc_init.params.a(INSERTION_ORBIT[0])
sc_init.params.e(INSERTION_ORBIT[1])
sc_init.params.i(INSERTION_ORBIT[2])
sc_init.params.RAAN(INSERTION_ORBIT[3])
sc_init.params.w(INSERTION_ORBIT[4])
sc_init.params.f(INSERTION_ORBIT[5])
sc_init.startup()
p_end = [sc_init.outputs.pos__inertial().get(0), sc_init.outputs.pos__inertial().get(1), sc_init.outputs.pos__inertial().get(2)]
v_end = [sc_init.outputs.vel__inertial().get(0), sc_init.outputs.vel__inertial().get(1), sc_init.outputs.vel__inertial().get(2)]

# Execute the lambert solver at the granularity and across the range
best_dv = float("inf")
best_tof = None
best_idx = None

mu = earth.outputs.mu()
tofs = np.linspace(TOF_RANGE[0], TOF_RANGE[1], int(TOF_GRANULARITY))

prev_V1 = None
prev_V2 = None
dv1 = []
dv2 = []
for idx, tof in enumerate(tofs):
    A, P, V1, V2, conv = lambert(p_start, p_end, float(tof), mu, n=1000, JJ=1)

    # Basic validity checks
    if (not conv) or (not np.all(np.isfinite(V1))) or (not np.all(np.isfinite(V2))):
        continue

    # Heuristic to reject the "below Tmin" plateau: if V’s don’t change across TOFs.
    if prev_V1 is not None and np.allclose(V1, prev_V1, atol=1e-8, rtol=0.0) \
       and prev_V2 is not None and np.allclose(V2, prev_V2, atol=1e-8, rtol=0.0):
        # treat as non-feasible for this TOF
        continue

    # Correct Δv vectors
    dv1_vec = V1 - np.array(v_start)
    dv2_vec = np.array(v_end) - V2   # <-- fixed sign

    total_dv = np.linalg.norm(dv1_vec) + np.linalg.norm(dv2_vec)

    if total_dv < best_dv:
        best_dv  = total_dv
        best_tof = float(tof)
        best_idx = idx
        dv1 = dv1_vec
        dv2 = dv2_vec

    prev_V1, prev_V2 = V1, V2

# Store and print the variables associated with our best burn
if best_idx >= 0:
    print("Best DeltaV to Achieve Objective:")
    print("\tTOF: " + str(best_tof))
    print("\tTotal DV: " + str(best_dv))
else:
    print("Unable to identify a functional burn. Exiting")
    exit(1)

# And schedule our burns. programManeuver takes a velocity change (m/s) --
# the spacecraft scales it by its own mass internally.
period = 2*math.pi*STARTING_ORBIT[0]/np.linalg.norm(v_start)
sc.programManeuver(CartesianVector3([float(v) for v in dv1]), period, earth.outputs.inertial_frame())
sc.programManeuver(CartesianVector3([float(v) for v in dv2]), period + best_tof, earth.outputs.inertial_frame())

# Allow startup to initialize frames
exc.startup()

# Set initial spacecraft states. Set from orbital elements to be GTO 
sc.initializeFromOrbitalElements(STARTING_ORBIT[0],
                                 STARTING_ORBIT[1],
                                 STARTING_ORBIT[2],
                                 STARTING_ORBIT[3],
                                 STARTING_ORBIT[4],
                                 STARTING_ORBIT[5])

exc.step(Time(0))

# And finally run simulation
exc.run()