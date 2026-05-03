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
import sys, os
from warptwin.WarpTwinPy import (Time, SimulationExecutive, Frame, Node, 
                                     Body, CartesianVector3, CsvLogger, connectSignals,
                                     DEGREES_TO_RADIANS, HOURS_TO_SECONDS)
from warptwin.Spacecraft import Spacecraft
from warptwin.SpicePlanet import SpicePlanet
from warptwin.FrameStateSensorModel import FrameStateSensorModel
from warptwin.SolarPanelPowerModel import SolarPanelPowerModel
from warptwin.EffectiveSolarAreaModel import EffectiveSolarAreaModel
from warptwin.OccultationModel import OccultationModel
from warptwin.SimpleBatterySystem import SimpleBatterySystem
from warptwin.PlanetRelativeStatesModel import PlanetRelativeStatesModel
from warptwin.SolarPanelModel import SolarPanelModel

##########################################################################
# PARAMETERS FOR SPACECRAFT POWER BUDGET STUDY
##########################################################################
SIM_RUNTIME = 10                    # hours

# Orbit Parameters
# The following parameters are defined as a list, and can range any number of elements.
# Adding an element to the list, for example multiple inclinations, altitudes, etc. 
# causes the simulation to loop through those elements and run the simulation for each.
# BE CAREFUL adding elements here -- the study is set up to cover all permutations of
# the parameters, so for example setting each list to have 2 items will cause the study
# to run 2^4 = 16 times. 
ORBIT_SEMIMAJOR_AXIS = [6778140, 6878140]     # m
ORBIT_ECCENTRICITY = [0.0000001]
ORBIT_INCLINATION = [25.0, 35.0, 45.0]            # degrees
ORBIT_RAAN = [0.0, 90.0]                    # degrees

# Battery configuration
# The battery system is configured from the list of defaults in data/defaults/SimpleBatterySystem
BATTERY_SYSTEM = "GOMspace_nanopower_bp4_4s1p"

# Solar panel configuration. Consists of a list with surface area and body pointing
# Each element in the list is a separate solar panel
# Columns:              Surface Area (m^2),         Body Pointing
SOLAR_PANELS = [[       0.01,                       [1.0,0.0,0.0]],
                [       0.01,                       [0.0,1.0,0.0]],
                [       0.01,                       [0.0,0.0,1.0]],
                [       0.01,                       [-1.0,0.0,0.0]],
                [       0.01,                       [0.0,-1.0,0.0]],
                [       0.01,                       [0.0,0.0,-1.0]]]
SOLAR_PANEL_EFF = 0.27            # Efficiency of the solar panel as a %, 1-->0

# Powered component list. Consists of a list of lists with name and power draw
# Columns:              Component Name,             Power Draw (W)
POWERED_COMPONENTS = [[ "Flight Computer",          0.5],
                      [ "NASA Payload",             3.0]]

##########################################################################
# END SCRIPT INPUTS
##########################################################################

def powerSimulationSingleRun(runtime_s, a, e, i, raan, battery_system, solar_panels, 
                             solar_panel_eff, powered_components, run_number):
    """
    Execute a single simulation run for the sake of the power study.
    Variables are as described above, except in seconds/meters.
    """
    # Create a simple simulation to plot a spacecraft
    exc = SimulationExecutive()     # Create our executive -- by convention named exc
    exc.end(runtime_s)
    exc.runNumber(run_number)
    os.makedirs("results", exist_ok=True)
    exc.logManager().outDir("results/run_" + str(run_number) + "/")

    # Create the Earth and Sun from SPICE kernels
    earth = SpicePlanet(exc, "earth")
    sun = SpicePlanet(exc, "sun")

    # Create our spacecraft
    sc = Spacecraft(exc, "sc")
    sc.params.planet_ptr(earth)

    # Create our solar panel models
    panels = []
    for i in range(len(solar_panels)):
        panels.append(SolarPanelModel(exc, "solar_panel_" + str(i)))
        panels[-1].params.panel_eff(SOLAR_PANEL_EFF)
        panels[-1].params.panel_area(solar_panels[i][0])
        panels[-1].params.panel_normal__body(CartesianVector3(solar_panels[i][1]))
        panels[-1].params.sun_frame_ptr(sun.outputs.inertial_frame())
        panels[-1].params.planet_frame_ptr(earth.outputs.inertial_frame())
        panels[-1].params.body_frame_ptr(sc.body())

    
    # Now create our battery system
    battery = SimpleBatterySystem(exc, "battery")
    battery.configureFromDefault(battery_system)
    power_draw = 0
    for powered_component in powered_components:
        power_draw += powered_component[1]
        battery.inputs.power_draw_out(power_draw)

    states = CsvLogger(exc, "states.csv")
    states.addParameter(exc.time().base_time, "time")
    states.addParameter(sc.planetInertialStateSensor().outputs.pos_tgt_ref__out, "pos")
    states.addParameter(sc.planetRelativeModel().outputs.altitude_detic, "altitude_m")
    states.addParameter(battery.inputs, "battery", True)
    states.addParameter(battery.outputs, "battery", True)
    exc.logManager().addLog(states, 1)

    exc.startup()

    sc.initializeFromOrbitalElements(a, e, i, raan, 0.0, 0.0)

    power_gen = 0
    while not exc.isTerminated():
        # Calculate our power generation from our solar panels
        power_gen = 0
        for panel in panels:
            power_gen += panel.outputs.power()
        battery.inputs.power_generation_in(power_gen)
        
        # Step the sim
        exc.step()
    
if __name__ == '__main__':
    # Do some math up front
    total_runs = len(ORBIT_SEMIMAJOR_AXIS)*len(ORBIT_ECCENTRICITY)*len(ORBIT_INCLINATION)*len(ORBIT_RAAN)
    
    # Create an empty DataFrame to store the simulation parameters
    # df = pd.DataFrame(columns=['run_number', 'a', 'e', 'i', 'raan'])
    
    # Loop through everyting
    count = 0
    for a in ORBIT_SEMIMAJOR_AXIS:
        for e in ORBIT_ECCENTRICITY:
            for i in ORBIT_INCLINATION:
                for raan in ORBIT_RAAN:
                    # Print our simulation run
                    print("Executing simulation run " + str(count) + " of " + str(total_runs))
                    
                    # Append the parameters to the DataFrame
                    # df = df.append({
                    #     'run_number': count,
                    #     'a': a*1000,
                    #     'e': e,
                    #     'i': i*DEGREES_TO_RADIANS,
                    #     'raan': raan*DEGREES_TO_RADIANS
                    # }, ignore_index=True)
                    
                    # And execute the run
                    powerSimulationSingleRun(SIM_RUNTIME*HOURS_TO_SECONDS, 
                                             a, 
                                             e, 
                                             i*DEGREES_TO_RADIANS, 
                                             raan*DEGREES_TO_RADIANS, 
                                             BATTERY_SYSTEM,
                                             SOLAR_PANELS, 
                                             SOLAR_PANEL_EFF, 
                                             POWERED_COMPONENTS,
                                             count)
                    
                    count += 1
                 
    # Save the DataFrame to a CSV file
    # df.to_csv('results/simulation_parameters.csv', index=False)   
    print("Runs complete.")