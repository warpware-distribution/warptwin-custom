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
Power Beaming Tutorial
----------------------
This example shows a power beaming case between two spacecraft in 
GEO.

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
from warptwin.SpacecraftLinkModel import SpacecraftLinkModel
from warptwin.SolarPanelPowerModel import SolarPanelPowerModel
from warptwin.EffectiveSolarAreaModel import EffectiveSolarAreaModel
from warptwin.OccultationModel import OccultationModel
from warptwin.SimpleBatterySystem import SimpleBatterySystem
from warptwin.SolarPanelModel import SolarPanelModel
from warptwin.PowerLoad import PowerLoad

SOLAR_ARRAY_DROPOUT_TIME = 1000.0
POWER_BEAM_START_TIME = 3500.0
BEAM_POWER = 10      # kW

# Create our base simulation infrastructure
exc = SimulationExecutive()                                                 # Create our executive -- by convention named exc
exc.setRateSec(1.0)                                                         # We can setRateHz or setRateSec -- default is 1 second
exc.args().addDefaultArgument("end",     10000)                             # Default can be overridden by command line
exc.parseArgs(sys.argv)                                                     # This interperets command-line inputs

# Create instances of the Earth and Sun as SPICE planets
earth = SpicePlanet(exc, "earth")
sun = SpicePlanet(exc, "sun")

# Now create our beaming and receiving spacecraft
sc_beam = Spacecraft(exc, "beaming_sc")
sc_beam.params.planet_ptr(earth)

sc_receive = Spacecraft(exc, "receiving_sc")
sc_receive.params.planet_ptr(earth)

power_link = SpacecraftLinkModel(exc, "power_link")
power_link.params.sc_1_frame(sc_beam.body())
power_link.params.sc_2_frame(sc_receive.body())
power_link.params.planet_frame(earth.outputs.inertial_frame())

# Create our solar panel models
panel = SolarPanelModel(exc, "panel")
panel.params.panel_body_fixed(False)            # Set panel to always point right at the sun
panel.params.sun_frame_ptr(sun.outputs.inertial_frame())
panel.params.planet_frame_ptr(earth.outputs.inertial_frame())
panel.params.panel_area(40.0)

# Create power load
load = PowerLoad(exc, "power_draw")
load.params.active_power_draw_W(7000)
load.inputs.mode(2)        # Put always in active mode

# Configure spacecraft for powered components/power draw
panel.params.body_frame_ptr(sc_receive.body())
sc_receive.addPowerLoad(load.outputs.power_draw_W)
sc_receive.addPowerSource(panel.outputs.power)

# Now create our battery system
battery = SimpleBatterySystem(exc, "battery")
battery.params.peak_battery_voltage(50)
battery.params.single_battery_capacity(7000)
connectSignals(sc_receive.outputs.total_power_in,       battery.inputs.power_generation_in)
connectSignals(sc_receive.outputs.total_power_out,      battery.inputs.power_draw_out)

# And set up logging for just a single spacecraft
log = Hdf5Logger(exc, "states.h5")
log.addParameter(exc.time().base_time,                  "time")
log.addParameter(sc_beam.outputs.pos_sc_pci,            "beam_eci_pos")
log.addParameter(sc_beam.outputs.vel_sc_pci,            "beam_eci_vel")
log.addParameter(sc_receive.outputs.pos_sc_pci,         "receive_eci_pos")
log.addParameter(sc_receive.outputs.vel_sc_pci,         "receive_eci_vel")
log.addParameter(sc_receive.outputs.total_power_in,                          "power_generation_w")
log.addParameter(sc_receive.outputs.total_power_out,                         "power_draw_w")
log.addParameter(battery.outputs.depth_of_discharge,                 "depth_of_discharge")
log.addParameter(battery.outputs.system_voltage,                     "system_voltage")
exc.logManager().addLog(log, 10)

exc.startup()

# Init phased apart
sc_beam.initializeFromOrbitalElements(42164137.0, 0.0001, 0.0005, 0.0, 0.0, 270.0*DEGREES_TO_RADIANS)

sc_receive.initializeFromOrbitalElements(42164137.0, 0.0001, 0.0005, 0.0, 0.0, 330.0*DEGREES_TO_RADIANS)

exc.step(Time(0,0))
dropout_triggerred = False
beam_started = False
power_link.deactivate()
power_link.outputs.visible(False)
while not exc.isTerminated():
    exc.step()

    if not dropout_triggerred and exc.time().base_time().asFloatingPoint() > SOLAR_ARRAY_DROPOUT_TIME:
        panel.deactivate()
        panel.outputs.power(0.0)
        dropout_triggerred = True
    elif not beam_started and exc.time().base_time().asFloatingPoint() > POWER_BEAM_START_TIME:
        power_link.activate()
        panel.outputs.power(BEAM_POWER*1000)
        beam_started = True