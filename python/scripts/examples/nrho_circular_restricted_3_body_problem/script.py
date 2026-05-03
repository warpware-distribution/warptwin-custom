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
Advanced Space Trajectory Planning
----------------------------------
This script serves as a baseline for planning an Earth-Moon Halo orbit for 
the Advanced Space Capstone mission. 

Author: Alex Reynolds 
"""
import sys
from warptwin.WarpTwinPy import Time, connectSignals, SimulationExecutive, ALL, DERIVATIVE, Frame, Body, Node, \
                         CartesianVector3, CsvLogger, DEGREES_TO_RADIANS, SpiceManager, muStar, lStar, tStar
from warptwin.CustomPlanet import CustomPlanet
from warptwin.FrameStateSensorModel import FrameStateSensorModel
from warptwinutils.vizkit.VizKitThreeBody import VizKitThreeBody
from warptwin.CR3BPDynamicsModel import CR3BPDynamicsModel

# Calculate our CR3BP parameters based on the Earth-Moon system
mu_earth = 398600.435507
mu_moon = 4902.800118
R = 384800.0000
mu_star = muStar(mu_earth, mu_moon)
l_star = lStar(R)
t_star = tStar(R, mu_earth + mu_moon)

exc = SimulationExecutive()     # Create our executive -- by convention named exc
exc.args().addDefaultArgument("end",     10*86400)
exc.parseArgs(sys.argv)         # this interperets command-line inputs
exc.setRateSec(Time(3000))

# Create our custom Earth and Moon, and set their positions in the fixed "synodic frame"
# which has Moon and Earth on X
earth = CustomPlanet(exc, "earth")
earth.outputs.inertial_frame().setRootRelPosition(CartesianVector3([-mu_star*l_star, 0.0, 0.0]))
moon = CustomPlanet(exc, "moon")
moon.outputs.inertial_frame().setRootRelPosition(CartesianVector3([(1.0-mu_star)*l_star, 0.0, 0.0]))

# Generate our spacecraft frame
spacecraft_1 = Body("spacecraft_1", exc.rootFrame())
sc_node_1 = Node("sc_node_1", spacecraft_1)

# Add frame state sensor model to sense the Moon state wrt Earth
fs_sc_synodic_1 = FrameStateSensorModel(exc, ALL, "fs_sc_synodic_1")
fs_sc_synodic_1.params.target_frame_ptr(spacecraft_1)
fs_sc_synodic_1.params.reference_frame_ptr(exc.rootFrame())

# Create our CR3BP dynamics model and connect to our spacecraft node
cr3bp_1 = CR3BPDynamicsModel(exc, DERIVATIVE, "cr3bp_1")
cr3bp_1.params.mu_primary(mu_earth)
cr3bp_1.params.mu_secondary(mu_moon)
cr3bp_1.params.orbit_radius(l_star)
cr3bp_1.params.use_canonical(False)
connectSignals(fs_sc_synodic_1.outputs.pos_tgt_ref__out, cr3bp_1.inputs.pos_synodic)
connectSignals(fs_sc_synodic_1.outputs.vel_tgt_ref__out, cr3bp_1.inputs.vel_synodic)

connectSignals(cr3bp_1.outputs.accel_synodic, sc_node_1.force)
sc_node_1.force_frame(exc.rootFrame())

# Configure logger for our spacecraft 
sc_synodic_states = CsvLogger(exc, "sc_synodic_states.csv")
sc_synodic_states.addParameter(exc.time().base_time, "sim_time")
sc_synodic_states.addParameter(fs_sc_synodic_1.outputs.pos_tgt_ref__out, "sc1_position")
sc_synodic_states.addParameter(fs_sc_synodic_1.outputs.vel_tgt_ref__out, "sc1_velocity")
exc.logManager().addLog(sc_synodic_states, Time(3600))

# Configure our liveplot
vk = VizKitThreeBody(exc)
vk.target(spacecraft_1)
vk.primary(earth.outputs.inertial_frame())
vk.secondary(moon.outputs.inertial_frame())
vk.radius_primary(0.001*vk.radius_primary())
vk.radius_secondary(0.001*vk.radius_secondary())
exc.logManager().addLog(vk, 10000)

exc.startup()

# Generate halo orbit for our first spacecraft
spacecraft_1.pos_f_p__p(CartesianVector3([0.98796165*l_star, 0.0, 0.029770651*l_star]))
spacecraft_1.vel_f_p__p(CartesianVector3([0.0,  0.86446415*l_star/t_star, 0.0]))

exc.run()