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
Monte Carlo Tutorial
--------------------
This script illustrates a simple example with a single spacecraft orbiting
the Earth with dispersed orbit values. It disperses semimajor axis and
local time of the ascending node (LTAN) to generate sun synchronous orbits.

Author: Alex Reynolds
"""
import sys
from warptwin.WarpTwinPy import SimulationExecutive, ALL, START_STEP, END_STEP, CsvLogger, connectSignals
from warptwin.SpicePlanet import SpicePlanet
from warptwin.Spacecraft import Spacecraft
from warptwin.OrbitalElementsStateInit import OrbitalElementsStateInit
from warptwin.FrameStateSensorModel import FrameStateSensorModel
from warptwin.PointMassGravityModel import PointMassGravityModel
from warptwin.LvlhFrameManagerModel import LvlhFrameManagerModel
from warptwinutils.orbitutils import computeSunSyncElements     # For our sun synchronous orbit utilities

if __name__ == '__main__':
    # First, initialize our executive. Set default arguments for time, etc. that can
    # be overwritten from command line
    exc = SimulationExecutive()
    exc.args().addDefaultArgument("end",     15000)
    exc.parseArgs(sys.argv)         # this interperets command-line inputs

    # Create a planet and spacecraft
    earth = SpicePlanet(exc, "earth")
    sun = SpicePlanet(exc, "sun")

    sc = Spacecraft(exc, "sc")
    sc.params.planet_ptr(earth)

    # Set up our logging. Here we'll create a simple CSV logger to record our
    # time and spacecraft state in the root frame
    state = CsvLogger(exc, "states.csv") 
    state.addParameter(exc.time().base_time, "time")
    state.addParameter(sc.outputs.pos_sc_pci, "sc_pos")  # Add our spacecraft position via direct ref
    exc.logManager().addLog(state, 1)   

    # Disperse our spacecraft orbit. In this example, we create two dispersions:
    # semimajor_axis and the local ascending node time, to disperse our orbit. Valid choices
    # are a uniform or gaussian input distribution. Values are set on each to parameterize
    # the dispersed values, as well as set a default value. The default value is the value
    # which the sim uses for run 0, which is undispersed. All other runs, which may be
    # set using the --run=<number> command line argument, will use dispersed values drawn from
    # the dispersion.
    #                                                       NAME,     DEFAULT,     MIN,          MAX
    alt_km = exc.dispersions().createUniformInputDispersion("alt_km", 500.0,       480.0,        520.0)

    #                                                    NAME,     DEFAULT,        MEAN,         STDEV
    LTAN = exc.dispersions().createNormalInputDispersion("LTAN",   6.0,            6.0,          1.0)

    # Call startup on our executive. This will initialize our exec and,
    # recursively, all of our models.
    exc.startup()

    # Here we actually use our dispersions to calculate the spacecraft orbital elements. Note
    # how each dispersion is called twice with () -- the first call returns the actual dispersion value,
    # which contains information about the dispersion as well as its current value. The second call returns
    # the current value of the dispersion as set by the run number.
    (a_km, e, i_rad, raan_rad, aop_rad, ltan_hours) = computeSunSyncElements(alt_km()(), 
                                                                             sun.outputs.inertial_frame().rootRelPosition(), 
                                                                             LTAN()())

    # Now initialize our spacecraft state using values calculated from our sun synchonous orbit
    # calculator
    sc.initializeFromOrbitalElements(a_km*1000.0, e, i_rad, raan_rad, aop_rad, 0.0)

    # Now run our simulation by calling our sim.run. This will automatically
    # terminate when our sim reaches its end time
    exc.run()