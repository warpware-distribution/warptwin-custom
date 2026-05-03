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
Simple Point Mass Gravity Tutorial
----------------------------------
This script illustrates a simple example with a spacecraft
orbiting under the influence of point mass gravity.

The script illustrates how models and frames function together in WarpTwin
and are created, connected, and run. It does not make use of any
wrapper models (such as the Spacecraft or Planet) to fully illustrate
how each component of the simulation works together. It is not the
"recommended" way to build simulation scripts because of its complexity,
however, it is a very good example case for folks looking to build their
own simulation from the ground up.

An equivalent example is provided in C++ at:
cpp/scripts/examples/earth_orbit_no_spacecraft_model/script.cpp

This script can be used effectively as a means of translating between
the C++ and Python versions of how to build things.

Author: Alex Reynolds <alex.reynolds@attx.tech>
"""

import sys
from warptwin.WarpTwinPy import SimulationExecutive, ALL, connectSignals, Body, Node, \
    CartesianVector3, CsvLogger
from warptwin.FrameStateSensorModel import FrameStateSensorModel
from warptwin.PointMassGravityModel import PointMassGravityModel

# Our main is where the script is actually executed
if __name__ == '__main__':
    # Create our simulation executive. The simulation executive is a class designed to 
    # provide all utilities for execution of simulations -- it contains elements like
    # logging, scheduling, and base frames which form the "foundation" on which 
    # simulations are built. It also contains search functionality -- everything in the 
    # sim can be found and accessed via sim executive search. Check out
    # cpp/src/simulation/SimulationExecutive.h for more details and a full list of functionality.
    exc = SimulationExecutive() # Create our executive -- by convention named exc
    exc.parseArgs(sys.argv)     # This function parses arguments from the command line in C++. 
                                # Arguments are passed with --, for example --end=300 sets the
                                # sim to end at 300 seconds.
    exc.setRateHz(1)            # We can setRateHz or setRateSec -- default is 1 second. This is
                                # the frequency/step size at which the simulation runs.

    # Now create our frames, bodies, and nodes
    # Frames are the default container for 6-DOF dynamics. They contain information on 
    # their position, velocity, attitude, and angular rate and are automatically integrated
    # by WarpTwin. Frames may be "free", which means they can have velocity and angular
    # rates and "move". They may also be "fixed" to another frame, which means they 
    # do not move relative to that frame (such as an IMU fixed to a spacecraft body).
    # WarpTwin is built on frame chains and uses those to integrate its dynamics.
    # This makes it very powerful, because incredibly complex dynamics are abstracted
    # from the user. For example, the acceleration experienced by an IMU may be cauculated
    # automatically with no calculation done by the user. Similarly, the user does not
    # have to worry about ensuring frame states are updated.
    # Bodies are frames with mass and inertia, which may be used to resolve forces into
    # accelerations. Bodies are, by default, fully free to move
    # Nodes are frames used to apply forces and moments to a body. Nodes must be fixed
    # to their parent body, but may be offset from its center (which greatly simplifies
    # the calculation of complex forces applied to a body)
    # By default, the simulation comes with only a root frame, which is owned by the 
    # simulation executive. From that, we can create any number of frames, bodies, and
    # nodes for planets, bodies, etc.
    # For this VERY simple example, we will treat the root frame as if it is our planet
    # frame for the purposes of gravity, so we only need a spacecraft body and node to
    # apply forces
    spacecraft_body = Body("spacecraft_body", exc.rootFrame())         # Make our spacecraft body a child of root frame
    gravity_node = Node("gravity_node", spacecraft_body)               # Create a node to apply our gravity force 

    # Now, create our frame state sensor -- we'll use this model to evaluate
    # where our spacecraft is at. Note that models typically have three arguments --
    # The first is their "parent", which may be the simulation executive (and typically is)
    # or may be another model. By making the model a child of the simulation executive
    # we give it access to the utilities provided by the sim exec and also register
    # it to be found via search.
    # The second argument is when the model is scheduled to run. The sim has three step
    # "phases" which occur on every sim step. The first is START_STEP, which runs before
    # any sim dynamics. The next is DERIVATIVE, which runs as many times as necessary to 
    # calculate forces in the sim (by default four times for RK4). The last is END_STEP,
    # which runs at the end of the simulation step (good for sensor measurements, output,
    # etc. which are needed from the updated state). Models may be scheduled to these,
    # or to ALL which will run the model every step. They may also be scheduled as STATRUP_ONLY,
    # which configures them but does not run them when the sim steps.
    # The third argument is the model's name -- the name assigns it a unique string identifier
    # by which it may be searched. The name does not have to be (but is highly recommended to be!)
    # The same as the model's variable name, in this case fs_model
    fs_model = FrameStateSensorModel(exc, ALL, "fs_model")          # Create our frame state sensor model
    fs_model.params.target_frame_ptr(spacecraft_body)               # Set our target sensed frame as spacecraft
    fs_model.params.reference_frame_ptr(exc.rootFrame())            # Set our reference frame as root

    # First instantiate our gravity model with appropriate parameters
    # Here is an example of model creation where the default scheduling and name are taken
    gravity_model = PointMassGravityModel(exc)

    # Here we connect signals between the frame state sensor model and gravity model. Every 
    # model's parameters, inputs, and outputs may be connected to other models. Essentially,
    # this means that the "downstream" signal, represented here as the second input to connectSignals,
    # reflects the value held by the "upstream" signal, which is the first input. In doing so,
    # we can build large simulations in a flexible and modular way. Here we are taking the
    # frame state sensor output "pos_tgt_ref__out", which returns the position of the spacecraft
    # body relative to our root frame, and connecting it to our gravity model's position
    # input. In doing so, 
    connectSignals(fs_model.outputs.pos_tgt_ref__out, 
                   gravity_model.inputs.pos_body__f)
    # This connection is between the output of the gravity model, which is the force on 
    # the spacecraft, and the node which applies that force.
    connectSignals(gravity_model.outputs.grav_force__f,
                   gravity_node.force)
    # By default, nodes apply forces in their own frame. However, in some cases it is 
    # advantageous to apply forces in another frame -- in this case, we want to apply force
    # in the inertial frame, which is where we are calculating gravity. By setting force_frame,
    # the node will automatically rotate our force into the appropriate frame before
    # applying it.
    gravity_node.force_frame(exc.rootFrame())

    # Set up our logging. Here we'll create a simple CSV logger to record our
    # time and spacecraft state in the root frame
    # This line creates the logger. The logger is a class which stores a list of parameters
    # to be recorded and the filename to which output will be saved.
    sc_position_log = CsvLogger(exc, "sc_state.csv")                    # Create our CSV logger to file sc_state.csv

    # Now we add parameters to our logger. Adding parameters tells the logger to 
    # record them in its file. Parameters may be added in one of two ways. First,
    # they may be added by directly calling the object itself -- in the following two
    # addParameter calls, for example, we are adding parameters directly by passing
    # the object to our logger. 
    sc_position_log.addParameter(exc.time().base_time, "time")                          # Add time as a logged parameter with name "time"
    sc_position_log.addParameter(fs_model.outputs.pos_tgt_ref__out, "sc_pos")           # Add our spacecraft position via direct ref

    # The following line demonstrates adding a logged parameter by string. Remember
    # that when models are added, they are given a string name by which they are
    # identified. Every object in the sim, whether model, frame, input/output, etc.
    # may be accessed via its string address. In this case, we are adding the velocity
    # of the spacecraft as a logged parameter. Note the similarities and differences 
    # between this added parameter and the one above, which also used the fs_model. 
    # Either addition is perfectly valid.
    sc_position_log.addParameter(".exc.fs_model.outputs.vel_tgt_ref__ref", "sc_vel")    # Add our spacecraft velocity via string address
    
    # Once our logger is created, we need to tell the simulation executive it exists
    # so it can run and record values automatically. The addLog call here adds our
    # sc_position_log to the sim and tells it to run at a rate of once per second. That
    # means the values set in sc_position_log will be recorded every one second of 
    # simulation time.
    exc.logManager().addLog(sc_position_log, 1)                                         # Add our sc log and set it to run at a rate of 1 Hz

    # Call startup on our executive. This will initialize our exec and,
    # recursively, all of our models by calling their start function.
    # NOTE: Startup should be called before initializing
    # the states of frames. That's not a hard and fast rule, but many frames
    # are created and/or initialized inside of calls to model startup. By setting
    # frame states after startup is called, we can be assured that our frame tree will not 
    # change
    exc.startup()

    # Set the initial state of our spacecraft
    # Note: by default, all frame objects (including bodies and nodes) are initialized
    # at 0, 0, 0 -- we want our gravity node at the CG of our body, so no action necessary
    # Initialize our body to circular orbit at 400 km altitude
    body_position__root = CartesianVector3([6778000.0, 0.0, 0.0])      # All units are in meters
    body_velocity__root = CartesianVector3([0.0, 7668.64, 0.0])        # All units are in m/s
    spacecraft_body.setRootRelPosition(body_position__root)
    spacecraft_body.setRootRelVelocity(body_velocity__root)

    # Now run our simulation by calling our sim.run. Running the sim essentially
    # loops through sim steps until its stop condition is reached. Within the
    # sim, that means it is calling each model's execute() function at the 
    # sim step phase it was scheduled for (see note above on step phases)
    # until termination.
    exc.run()

    # Note, alternatively we could call our steps individually in a while
    # loop by checking our terminate flag or any other variable of choice.
    # This is ideal for cases where scripts or alternate software need to
    # be run outside of the simulation. Additionally, step() is excellent
    # for debugging code.
    # while(!exc.isTerminated()) {
    #     exc.step();
    # }
    # while(<custom_check_condition>) {
    #     exc.step();
    # }