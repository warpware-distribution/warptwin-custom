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
This script demonstrates a simple analysis with spacecraft transfer from GTO to GEO.
"""
import sys
from warptwin.WarpTwinPy import (SimulationExecutive, CsvLogger, DEGREES_TO_RADIANS,
                                     Time, Node, END_STEP, connectSignals, CartesianVector3,
                                     Frame)
from warptwin.SpicePlanet import SpicePlanet
from warptwin.Spacecraft import Spacecraft
from warptwin.OrbitalElementsSensorModel import OrbitalElementsSensorModel

# GN&C-specific stuff
from warptwin.DirectionalAdaptiveGuidance import DirectionalAdaptiveGuidance

# Create an instance of the thruster model. This is just a python dictionary to store
# basic data. Nothing exciting here
thruster = {
    'thrust_N' : 300.0/1000.0,      # mN convert to N
    'isp' : 1200.0,                 # Specific impulse, s
    'mdot_kg_s' : 3.5*1e-6*2.35,    # mdot of the thruster
    'sc_dry_mass_kg' : 500,         # Dry mass of the spacecraft
    'sc_prop_mass_kg' : 150,        # Propellant mass in kg
}

# Boilerplate simulation executive initialization
exc = SimulationExecutive()     # Create our executive -- by convention named exc
exc.args().addDefaultArgument("end",     60.0*86400.0)
exc.parseArgs(sys.argv)         # this interperets command-line inputs
exc.setTime("2026 FEB 28 12:00:00.000")     # Arbitrarily set date to guess for launch date
step_size = 10.0
exc.setRateSec(step_size)

# Create an Earth SPICE planet for our propagation
earth = SpicePlanet(exc, "earth")

# Generate spacecraft and configure mass
sc = Spacecraft(exc, "sc")
sc.params.planet_ptr(earth.outputs.self_id())
sc.params.mass(thruster['sc_prop_mass_kg'] + thruster['sc_dry_mass_kg'])

# Set up our directional adaptive guidance, which controls the electric thrust
# module. Note we set our target orbital elements and weight their value
dg = DirectionalAdaptiveGuidance(exc, END_STEP, "dg")
dg.params.a_weight(1.0)
dg.inputs.a_target(42000000.0)
dg.inputs.e_target(1e-6)
dg.inputs.i_target(DEGREES_TO_RADIANS*18.0)

# Connect spacecraft position to EP control input position
connectSignals(sc.outputs.pos_sc_pci, dg.inputs.pos_pci)
connectSignals(sc.outputs.vel_sc_pci, dg.inputs.vel_pci)

# Generate a node, which applies our electric thrust force on the vehicle.
# Alternatively, we could use the thruster model, but for this simple example
# using a node directly is sufficient
dg_node = Node("dg_node", sc.body())
dg_node.force_frame(earth.outputs.inertial_frame())

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
exc.logManager().addLog(states, Time(100))

# Allow startup to initialize frames
exc.startup()

# Set initial spacecraft states. Set from orbital elements to be GTO 
sc.initializeFromOrbitalElements(0.5*(6378137.0+180000.0 + 6378137.0+35786000.0),
                                 0.73080,
                                 28.5*DEGREES_TO_RADIANS,
                                 0.0*DEGREES_TO_RADIANS,
                                 0.0*DEGREES_TO_RADIANS,
                                 0.0*DEGREES_TO_RADIANS)

exc.step(Time(0))

# And finally run simulation
updated = False
while not exc.isTerminated():
    # Map our DG output to our node input by multiplying by accel
    dg_node.force(CartesianVector3([
        thruster['thrust_N']*dg.outputs.accel_pnt_pci().get(0),
        thruster['thrust_N']*dg.outputs.accel_pnt_pci().get(1),
        thruster['thrust_N']*dg.outputs.accel_pnt_pci().get(2)
    ]))
    sc.params.mass(sc.params.mass() - thruster['mdot_kg_s']*step_size)
    err = exc.step()
    if(err):
        exit(1)
    
    if not updated and sc_oe.outputs.a() > 40000000:
        print("SMA Target Reached. Exiting Spiral Phase and entering Alignment")
        print("At time: " + str(exc.time().base_time().asFloatingPoint()))
        print("Setting targets to: ")
        print("\t SMA: " + str(dg.inputs.a_target()))
        print("\t e: " + str(dg.inputs.e_target()))
        print("\t i: " + str(dg.inputs.i_target()))
        updated = True
        dg.params.a_weight(10.0)
        dg.params.e_weight(1.0)
        dg.params.i_weight(1.0)