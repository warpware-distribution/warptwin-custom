# ##############################################################################
# Copyright (c) ATTX INC 2026. All Rights Reserved.

# This software and associated documentation (the "Software") are the 
# proprietary and confidential information of ATTX INC. The Software is 
# furnished under a license agreement between ATTX and the user organization 
# and may be used or copied only in accordance with the terms of the agreement.
# Refer to 'license/attx_license.adoc' for standard license terms.

# EXPORT CONTROL NOTICE: THIS SOFTWARE MAY INCLUDE CONTENT CONTROLLED UNDER THE
# INTERNATIONAL TRAFFIC IN ARMS REGULATIONS (ITAR) OR THE EXPORT ADMINISTRATION 
# REGULATIONS (EAR99). No part of the Software may be used, reproduced, or 
# transmitted in any form or by any means, for any purpose, without the express 
# written permission of ATTX INC.
# ##############################################################################
"""
Rendezvous and WarpLink Connection Tutorial
-------------------------------------------
This script serves three purposes:
1) To demonstrate two spacecraft performing proximity operations in Low Earth Orbit
2) To demonstrate basic GN&C and Flight Software scheduling in WarpTwin
3) To demonstrate connecting WarpOS to WarpLink while running the sim in real time mode

TO RUN:
- By default, this script runs in faster-than-realtime mode. Simply run script.py and
  the sim will run to completion with visuals
- When running the sim in realtime mode:
  python3 script.py --real-time=true
  The simulation will operate in real-time, allowing users to view its output in WarpLink
  and operate it as if a spacecraft were on orbit

Author: Alex Reynolds
"""
import sys
from warptwin.WarpTwinPy import Time, Node, SimulationExecutive, END_STEP, connectSignals, CartesianVector3, \
    Quaternion, CsvLogger, Scheduler
from warptwin.CustomPlanet import CustomPlanet
from warptwin.Spacecraft import Spacecraft
from warptwin.FrameStateSensorModel import FrameStateSensorModel
from warptwin.PointMassGravityModel import PointMassGravityModel
from warptwin.LvlhFrameManagerModel import LvlhFrameManagerModel
from warptwin.PdAttitudeControl import PdAttitudeControl
from warptwin.PidTranslationalControl import PidTranslationalControl
from warptwin.VisualsModel import VisualsModel
from warptwin.TelemetryManager import TelemetryManager
from warptwin.CommandManager import CommandManager
from warptwin.SimTableScheduleModel import SimTableScheduleModel

if __name__ == '__main__':
    # First, initialize our executive. Set default arguments for time, etc. that can
    # be overwritten from command line
    exc = SimulationExecutive()

    # Now parse our command line
    exc.args().addDefaultArgument("end",     2000)
    exc.parseArgs(sys.argv)
    exc.setRateHz(10)
    exc.enableVisuals()

    # Create our Earth planet 
    earth = CustomPlanet(exc, "earth")

    # Create our spacecraft bodies. Initialize a target and 
    # chaser spacecraft, where our chaser is maneuvering about our target
    target = Spacecraft(exc, "target")
    target.params.planet_ptr(earth)
    target.params.visuals_model("CubeSat-3U.glb")

    # Add a frame to the visuals for our target's LVLH frame
    exc.visualsModel().addFrame(target.lvlh(), "target_lvlh")  

    chaser = Spacecraft(exc, "chaser")
    chaser.params.planet_ptr(earth)
    chaser.params.visuals_model("CubeSat-3U.glb")

    # Build a frame state sensor model for our LVLH relative state
    fs_lvlh = FrameStateSensorModel(exc, END_STEP, "fs_lvlh")
    fs_lvlh.params.target_frame_ptr(chaser.body())                 # Set our target sensed frame as spacecraft
    fs_lvlh.params.reference_frame_ptr(target.lvlh())

    # Build a frame state sensor model for our body relative state.
    # Because our body is aligned to inertial, this doubles as a nice proxy for
    # inertial relative state
    fs_rel_inertial = FrameStateSensorModel(exc, END_STEP, "fs_rel_inertial")
    fs_rel_inertial.params.target_frame_ptr(chaser.body())                 # Set our target sensed frame as spacecraft
    fs_rel_inertial.params.reference_frame_ptr(target.body())

    # Now build a controller to hold our chaser at a relative state.
    # Here we'll command to hold exactly a position of -20 in y relative to
    # our body
    pos_ctrl = PidTranslationalControl(exc, END_STEP, "pos_ctrl")
    pos_ctrl.params.P(-1e-3)
    pos_ctrl.params.D(-1)
    connectSignals(fs_rel_inertial.outputs.pos_tgt_ref__out,    # Upstream
                   pos_ctrl.inputs.act_state)                   # Downstream
    connectSignals(fs_rel_inertial.outputs.vel_tgt_ref__out,
                   pos_ctrl.inputs.deriv_state)
    pos_ctrl.inputs.cmd_state(CartesianVector3([0.0, -10.0, 0.0]))
    pos_ctrl_node = Node("pos_ctrl_node", chaser.body())
    connectSignals(pos_ctrl.outputs.control_cmd,
                   pos_ctrl_node.force)
    pos_ctrl_node.force_frame(target.body())

    att_ctrl = PdAttitudeControl(exc)
    att_ctrl.params.P(CartesianVector3([1/180, 1/180, 1/180]))
    att_ctrl.params.K(CartesianVector3([1/6, 1/6, 1/6]))
    connectSignals(fs_rel_inertial.outputs.att_tgt_ref,
                   att_ctrl.inputs.act_quat)
    connectSignals(fs_rel_inertial.outputs.omega_tgt_ref__out,
                   att_ctrl.inputs.act_omega__act)
    att_ctrl.inputs.cmd_quat(Quaternion([1.0,0.0,0.0,0.0]))
    att_ctrl_node = Node("att_ctrl_node", chaser.body())
    connectSignals(att_ctrl.outputs.cmd_torque__body,
                   att_ctrl_node.moment)
    att_ctrl_node.moment_frame(target.body())

    # Set up a simulated table scheduler model. The table scheduler is a simplified
    # form of flight software scheduling which executes apps deterministically.
    table_schedule = SimTableScheduleModel(exc, "table_schedule")

    # Now schedule our apps. Note that apps can be scheduled directly in the simulation
    # using the built-in sim scheduler (which executes them every step) OR via the
    # simulated table scheduler. Here we will schedule them in the table scheduler,
    # but example code is provided commented for how to schedule them directly in the sim
    # exc.registerApp(att_ctrl, END_STEP)
    for i in range(0, 1000, 100):
        table_schedule.registerApp(att_ctrl, i + 0)
        table_schedule.registerApp(exc.telemetryManager(), i + 1)
        table_schedule.registerApp(exc.commandManager(), i + 2)

    # Finally, configure the IP address and ports for our connection with WarpLink. See
    # the WarpLink README for instructions on how to configure from the WarpLink side.
    # You can easily get your IP address over wifi by running "ip route" in the linux terminal
    exc.setFswWarpLinkInterface("192.168.112.1", 5005, 5006)   # 5005 is standard tlm, 5006 is standard cmd

    # Set up our logging. Here we'll create a simple CSV logger to record our
    # time and spacecraft state in the root frame
    state = CsvLogger(exc, "states.csv") 
    state.addParameter(exc.time().base_time, "sim_time")
    state.addParameter(fs_lvlh.outputs.pos_tgt_ref__out, "chaser_lvlh_state")  # Add our spacecraft position via direct ref
    state.addParameter(chaser.planetInertialStateSensor().outputs.pos_tgt_ref__out, "chaser_inrtl_state")  # Add our spacecraft position via direct ref
    exc.logManager().addLog(state, 1)                                   # Add our sc log and set it to run at a rate of 1 Hz

    # Call startup on our executive. This will initialize our exec and,
    # recursively, all of our models.
    exc.startup()

    # Now configure our telemetry -- in flight software we configure how packets are
    # sent and how often. We do the same here in the sim. We can either schedule 
    # telemetry by apid, or scheduling all. Here we schedule all telemetry at 10 Hz
    rate = Time()
    rate.fromFloatingPoint(0.5)         # 2 Hz
    exc.scheduleTelemetry(-1, rate)     # -1 means all, or we can schedule by apid

    # Initialize our spacecraft positions. First, our target -- we'll initialize to
    # a near-circular orbit at an altitude of 400 km with a 45 degree inclination
    err = target.initializeFromOrbitalElements(6778140.0, 0.001, 0.523, 0.0, 0.0, 0.0)

    # Now initialize our chaser state. Here we initialize state using the spacecraft
    # initializeFromSpacecraftRelative function. This function initializes the relative
    # state between two spacecraft using the planet inertial frame relative to which
    # both spacecraft are defined. Here, we initialize the chaser to be 13 meters away
    # from the target with zero initial velocity.
    chaser.initializePositionVelocity(CartesianVector3([13.0, 0.0, 0.0]), 
                                      CartesianVector3(), 
                                      target.lvlh())
    
    # Initialize the attitude of the chaser spacecraft using a simple quaternion. Here
    # we set the value, unitize it, and then set the attitude from it
    att = Quaternion([0.0, 0.0, 0.0, 1.0])
    att.unitize()
    chaser.initializeAttitude(att, CartesianVector3())

    # Now run our simulation by calling our sim.run. This will automatically
    # terminate when our sim reaches its end time
    err = exc.run()