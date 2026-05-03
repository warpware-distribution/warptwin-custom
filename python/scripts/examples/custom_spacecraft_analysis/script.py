""" =====================================================
! FIRST READ CustomSpacecraft.py

he following python script is designed to perform an
energy budget analysis of your mission to help
inform power based design decisions. This script will
run a monte carlo analysis with a provided power configuration,
and inform the team if the configuration works.

In this simulation, it is assumed that the power draw of all
the components running in a given mission mode has already been
determined. At every time step, the power draw is perturbed by
a percentage the follows a Gaussian distribution with determined
mean and standard deviation.

This script accounts for eclipse zones and the fact that the
spacecraft will eclipse itself. We also model each mission mode
accurately (though under ideal conditions). There is a tumble in
safe mode and we are perfectly nadir pointing in nominal and 
experiment mode. This script also accounts for the power induced
by downlinking. The script accurately models a ground station with
a 10 degree elevation mask and will start a downlink every time
the ground station is not masked.

! To actually run this script see custom_deliverables_bash.sh

Author James Tabony <james.tabony@attx.tech> : 10/31/25
===================================================== """

import sys, os, argparse
from warptwin.WarpTwinPy import (SimulationExecutive, LOG_INFO, CsvLogger, DEGREES_TO_RADIANS, CartesianVector3, Time, connectSignals)
from warptwin.BiasNoiseModel import BiasNoiseModel
from warptwin.TwoAxisPointingGuidance import TwoAxisPointingGuidance
from CustomSpacecraft import CustomSpacecraft
from configs import (disperseDate, disperseOrbitParams)

#########################################################
# System Parameters
#########################################################

# Define the total power draws in each mission mode
# These values are gathered externally through data sheets and testing
POWER_DRAW_SAFE = 4.69          # Average power draw in safe mode [W]
POWER_DRAW_NOMINAL = 5.82       # Average power draw in nominal mode [W]
POWER_DRAW_EXPERIMENT = 11.52   # Average power draw in experiment mode [W]
POWER_DRAW_FROM_TRANSMIT = 9    # Average power draw induced by transmitting [W]
POWER_DRAW_PERTURBATION = 0.02  # Standard deviation to instantaneous power draw [%] - 2%

# Define the date dispersions
START_YEAR = 2028
START_MONTH_RANGE = [1, 12]

# Define the orbit element dispersions
ALTITUDE_RANGE = [400.0*1000.0, 500.0*1000.0]   # [meters]
INCLINATION_RANGE = [45.0, 85.0]                # [degrees]

# Define simulation duration
SIM_DURATION = 48*3600      # [seconds]

# Define component configuration
SOLAR_PANEL_NAME = "EnduroSat"
BATTERY_NAME = "GOMspace_nanopower_bp4_2s2p"

# Define uniform dispersions of battery initial charge
BATTERY_RANGE = [1.0, 0.7, 1.0] # Nominal, Minimum, Maximum [%]

#########################################################
# Setup Simulation
#########################################################
if __name__ == '__main__':
    # Set up the simulation executive
    exc = SimulationExecutive()     # Create a simulation executive
    exc.args().addDefaultArgument("end", SIM_DURATION)  # Set simulated end time to desired duration
    exc.parseArgs(sys.argv)         # Parse terminal line inputs
    exc.setRateHz(1)                # Set simulation rate to 1 Hz
    exc.logLevel(LOG_INFO)          # Set the Log level to none to receive more simulation information

    # Set the start time based on a dispersed date
    date_str = disperseDate(exc, START_YEAR, START_MONTH_RANGE)
    exc.setTime(date_str)

    # Gather the case from an argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=str, default="safe")
    parser.add_argument("--run", type=int, required=False)
    parser.add_argument("--out-dir", type=str, required=False)
    parser.add_argument("--end", type=str, required=False)
    args = parser.parse_args()
    case = args.case

    # Configure simulation based on mission mode
    match case:
        case 'safe':
            base_power_draw = POWER_DRAW_SAFE
            allow_downlink = False
            nadir_point = False
        case 'nominal':
            base_power_draw = POWER_DRAW_NOMINAL
            allow_downlink = True
            nadir_point = True
        case 'experiment':
            base_power_draw = POWER_DRAW_EXPERIMENT
            allow_downlink = True
            nadir_point = True
        case _:
            raise TypeError(f"Case {case} not valid")

    # Create an instance of the CustomSpacecraft class
    sc = CustomSpacecraft(exc)

    if allow_downlink:
        # Add ground station at ATTX site
        idx = sc.configGroundStation()
        # Set elevation mask to 10 degrees
        sc.ground_stations[idx].params.elevation_mask_rad(10.0*DEGREES_TO_RADIANS)

    # Disperse the initial battery charge
    battery_charge = sc._exc.dispersions().createUniformInputDispersion("initial_battery",
                                                                        BATTERY_RANGE[0],
                                                                        BATTERY_RANGE[1],
                                                                        BATTERY_RANGE[2])
    battery_charge = battery_charge()()

    # Configure the Solar Panels
    sc.configSolarPanelFromJson(SOLAR_PANEL_NAME)

    # Configure the Battery
    sc.configBatteryFromJson(BATTERY_NAME, battery_charge)

    # Create a bias noise model to purturb the power draw
    noise = BiasNoiseModel(sc._exc)
    # Set the standard deviation to determined value
    noise.params.noise_std(POWER_DRAW_PERTURBATION)

    if nadir_point:
        # Create a two axis pointing guidance algorithm
        guidance = TwoAxisPointingGuidance(sc._exc)
        guidance.inputs.current_primary_body(CartesianVector3([1.0, 0.0, 0.0]))     # X-axis points nadir
        guidance.inputs.current_secondary_body(CartesianVector3([0.0, 0.0, 1.0]))   # Z-axis points towards sun
        connectSignals(sc.nadir_pointing_sensor.outputs.pos_tgt_ref__out, guidance.inputs.desired_primary)
        connectSignals(sc.sun_pointing_sensor.outputs.pos_tgt_ref__out, guidance.inputs.desired_secondary)

    # Create Logger
    logger = CsvLogger(sc._exc, "states.csv")               # Create an instance of the logger and configure the file name
    logger.addParameter(sc._exc.time().base_time, "time")   # Save simulation time [sec]
    logger.addParameter(sc.battery.outputs.system_voltage, "voltage")           # Save the voltage stored in the battery [V]
    logger.addParameter(sc.battery.outputs.power_available, "power_available")  # Save the boolean denoting a battery SOH fault [0 true, 1 false]
    logger.addParameter(sc.battery.inputs.power_generation_in, "power_in")      # Save the power entering the battery [W]
    logger.addParameter(sc.battery.inputs.power_draw_out, "power_out")          # Save the power leaving the battery [W]
    exc.logManager().addLog(logger, Time(10))               # Add the logger to the simulation executive log manager and save data at 10 seconds

    # Startup simulation
    exc.startup()

    # Initialize the position and velocity of CustomSpacecraft using dispersed orbit elements
    elements = disperseOrbitParams(sc._exc, ALTITUDE_RANGE, INCLINATION_RANGE)
    sc.initializeState(elements[0], elements[1], elements[2], elements[3], elements[4], elements[5])
    # Initialize an arbitrary tumble
    sc.body().ang_vel_f_p__f(CartesianVector3([0.001, 0.002, 0.003]))

    # Run the simulation
    exc.step(Time(0))
    while not exc.isTerminated():
        # Compute the total power generated from each solar panel
        total_power_generated = 0
        for i in range(len(sc.panels)):
            total_power_generated += sc.panels[i].outputs.power()
        # Pass the power generated to the battery model
        sc.battery.inputs.power_generation_in(total_power_generated)

        # Check if downlink is possible and determine power draw
        if (allow_downlink and not sc.ground_stations[idx].outputs.masked()):
            power_draw = base_power_draw + POWER_DRAW_FROM_TRANSMIT
        else:
            power_draw = base_power_draw
        # Pass the power draw to the battery model
        sc.battery.inputs.power_draw_out(power_draw * (1.0+noise.outputs.output_val()))

        # Check if nadir pointing is active and determine attitude
        if nadir_point:
            sc.body().rootRelQuaternion(guidance.outputs.quat_body_ref())

        # Step simulation
        exc.step()
