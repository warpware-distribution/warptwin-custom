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
Single-stage sounding rocket with parachute recovery
----------------------------------------------------
This script flies a 14 inch single-stage sounding rocket off a near-vertical
rail, coasts it to an apogee around 80 km, and recovers it under a two-canopy
parachute system: a drogue at apogee to hold the fall through the mid atmosphere,
and a main canopy low down for a landing at about 7 m/s.

The vehicle is a LaunchVehicle, which brings its own body, gravity, planet
relative states (lat/lon/alt), atmosphere, a gimballed main engine, a propellant
tank the engine drains as it burns, an axisymmetric aerodynamics model, and both
parachutes. It is flown by writing a thrust vector to inputs.thrust_command__body
and firing each canopy's deploy input; the vehicle cuts the engine off on its own
once the tank runs dry.

Flight sequence, all of it flown from this script (the vehicle sequences nothing
on its own):

    t = IGNITION_TIME_S     light the engine, ride the rail, fly straight up
    tank dry                MECO; the vehicle cuts the engine off itself
    apogee                  deploy the drogue (altitude stops increasing)
    MAIN_DEPLOY_AGL_M       deploy the main canopy on the way down
    pad altitude            impact; the run stops

Not modeled here: staging, and any guidance or attitude control. The engine gimbal
is configured and limited but never commanded off axis.

Run it:
    python3 script.py

Author: Alex Reynolds <alex.reynolds@warpware.co>
"""
import os
import sys

from warptwin.WarpTwinPy import (
    SimulationExecutive,
    CartesianVector3,
    Matrix3,
    CsvLogger,
    Time,
    DEGREES_TO_RADIANS,
    LOG_INFO,
)
from warptwin.SpicePlanet import SpicePlanet
from warptwin.LaunchPadModel import LaunchPadModel
from warptwin.LaunchVehicle import LaunchVehicle

# ---------------------------------------------------------------------------
# Launch site + rail geometry. White Sands Missile Range, near vertical so the
# vehicle comes back down close enough to the pad to be worth recovering.
# ---------------------------------------------------------------------------
LAUNCH_LAT_DEG     = 32.9903        # WGS-84 geodetic latitude
LAUNCH_LON_DEG     = -106.9749      # WGS-84 longitude
LAUNCH_ALT_WGS84_M = 1401.0         # height above the WGS-84 ellipsoid
RAIL_AZIMUTH_DEG   = 90.0           # 0 = North, 90 = East, 180 = South, 270 = West
RAIL_ELEVATION_DEG = 88.0           # 90 = vertical, 0 = horizontal
RAIL_LENGTH_M      = 12.0           # guided travel before the pad releases the vehicle

# ---------------------------------------------------------------------------
# Vehicle -- a 14 inch (0.356 m) single-stage sounding rocket, 5.5 m long,
# carrying a small instrument payload. Body X runs from the nose tip 3.2 m
# forward of the CG to the nozzle 2.3 m aft of it.
#
# Thrust and mass flow together fix the specific impulse the engine flies at:
# Isp = thrust / (g * mdot), about 235 s here, typical of a solid motor. Thrust
# to weight off the pad is about 7.1, and the load holds a burn of roughly 19 s.
# ---------------------------------------------------------------------------
DRY_MASS_KG           = 190.0       # airframe, motor case, payload and recovery
                                    # system; also the mass that comes down under
                                    # the canopies
PROPELLANT_MASS_KG    = 243.0       # loaded at liftoff, burned to nothing
ENGINE_THRUST_N       = 30000.0     # full thrust
ENGINE_MDOT_KG_S      = 13.0        # mass flow at full thrust
ENGINE_STATION_M      = -2.3        # nozzle position along body X, aft of the CG
ENGINE_MAX_GIMBAL_DEG = 3.0         # how far the engine can be deflected off axis
ENGINE_LATENCY_MS     = 50          # delay from throttle command to the engine acting

# Inertia about the CG for the 5.5 m by 0.356 m airframe: 0.5*m*r^2 in roll,
# (1/12)*m*L^2 in pitch and yaw. The LaunchVehicle interpolates between the DRY
# tensor (at burnout -- the configuration that flies under canopy, where this
# matters most) and the FULLY-LOADED tensor (at liftoff, with the solid grain
# still in the motor) by propellant fraction, so it is right at both ends.
ROLL_INERTIA_DRY_KG_M2   = 3.0
ROLL_INERTIA_FULL_KG_M2  = 6.0
PITCH_INERTIA_DRY_KG_M2  = 480.0
PITCH_INERTIA_FULL_KG_M2 = 1100.0

# ---------------------------------------------------------------------------
# Aerodynamics -- a slender finned body. reference_area is the 0.356 m diameter
# cross-section. ca and the CP station are scheduled against Mach in the loop.
# ---------------------------------------------------------------------------
AERO_REFERENCE_AREA_M2 = 0.0995     # pi * (0.178 m)^2
AERO_CN_ALPHA          = 2.4        # normal-force slope, per rad (slender body + fins)
NOSE_TIP_STATION_M     = 3.2        # nose tip on body X, forward of the CG
CA0_SUBSONIC           = 0.30       # axial force coefficient below the drag rise
CA_TRANSONIC           = 0.55       # axial force coefficient through Mach 1
CP_FROM_NOSE_SUBSONIC_M   = 4.0     # CP aft of the nose tip -> 0.8 m aft of the CG,
                                    # a bit over two calibers of static margin
CP_FROM_NOSE_SUPERSONIC_M = 3.7     # CP migrates forward through the transonic region

# ---------------------------------------------------------------------------
# Recovery system. Areas are the FULLY-OPEN canopy areas; both default to zero on
# the vehicle, so setting them here is what fits the chutes at all.
#
# The untangle time is the lines and canopy paying out, before anything catches
# air. The fill time is the canopy inflating over that: effective area ramps
# 0 -> full over it on a smoothstep, so the opening shock is spread rather than
# landing in a single step. The main gets the longer fill of the two, as a big
# canopy popped instantly is exactly the load case a real one is reefed to avoid.
# ---------------------------------------------------------------------------
DROGUE_AREA_M2       = 2.5          # ~1.8 m canopy; holds descent near 30 m/s low down
DROGUE_CD            = 1.6
DROGUE_UNTANGLE_S    = 0.5
DROGUE_FILL_S        = 1.0
MAIN_AREA_M2         = 32.0         # ~6.4 m canopy; ~7 m/s at the pad
MAIN_CD              = 2.2
MAIN_UNTANGLE_S      = 1.0
MAIN_FILL_S          = 3.0

# Cord lengths -- CG to canopy, out the nose. This is the moment arm the canopy drag
# pulls on, so it is what sets the weathercocking stiffness: the restoring moment is
# cord * drag * sin(angle off tail first). The nose is 3.2 m ahead of the CG on this
# airframe, so these put each canopy a riser length beyond it.
DROGUE_CORD_M        = 4.0
MAIN_CORD_M          = 10.0

# ---------------------------------------------------------------------------
# Flight sequence
# ---------------------------------------------------------------------------
IGNITION_TIME_S    = 1.0            # sit on the pad a moment, then light it
LIFTOFF_ALT_M      = 100.0          # climb above the pad by this much before
                                    # apogee and impact detection are armed
MAIN_DEPLOY_AGL_M  = 1000.0         # fire the main this far above the pad

# These two functions defined just to give a semi-realistic set of values. 
# In a full scenario these come from a database or similar.
def axialCoefficient(mach):
    """Simple transonic axial-force rise: flat below Mach 0.8, ramping to the
    transonic value through Mach 1, then easing back off supersonic."""
    if mach < 0.8:
        return CA0_SUBSONIC
    if mach < 1.2:
        frac = (mach - 0.8) / 0.4
        return CA0_SUBSONIC + frac * (CA_TRANSONIC - CA0_SUBSONIC)
    return max(CA_TRANSONIC - 0.10 * (mach - 1.2), 0.35)
def cpFromNose(mach):
    """Centre of pressure as a distance aft of the nose tip. It migrates forward
    (toward the nose, smaller distance) through the transonic region"""
    if mach < 0.8:
        return CP_FROM_NOSE_SUBSONIC_M
    if mach > 1.2:
        return CP_FROM_NOSE_SUPERSONIC_M
    frac = (mach - 0.8) / 0.4
    return CP_FROM_NOSE_SUBSONIC_M + frac * (CP_FROM_NOSE_SUPERSONIC_M - CP_FROM_NOSE_SUBSONIC_M)

if __name__ == "__main__":
    # -----------------------------------------------------------------------
    # Executive. The whole flight -- boost, a long coast to 80 km, and a longer
    # descent under canopy -- fits inside the default end time below.
    # -----------------------------------------------------------------------
    exc = SimulationExecutive()
    exc.args().addDefaultArgument("end", 1500.0)
    exc.parseArgs(sys.argv)
    # 100 Hz. Fast enough to resolve the second the vehicle spends on the rail
    # and the canopies filling, and a whole number of steps in the engine
    # command latency above.
    step_size = 0.01
    exc.setRateSec(step_size)
    exc.setTime("2026 August 28, 12:00:00 MDT")
    exc.logLevel(LOG_INFO)

    # -----------------------------------------------------------------------
    # Planet -- provides the inertial frame and the rotating (ECEF) frame the
    # pad is anchored to. SpicePlanet wires up both frames in its constructor.
    # The aerodynamics and the chutes need it to be Earth: the atmosphere the
    # vehicle flies through is NRLMSISE-00, which LaunchVehicle deactivates
    # anywhere else.
    # -----------------------------------------------------------------------
    earth = SpicePlanet(exc, "earth")

    # -----------------------------------------------------------------------
    # Rocket. LaunchVehicle brings the body, gravity, planet relative states,
    # the atmosphere, the main engine, the propellant tank, the aerodynamics and
    # both chutes; all this script does is size them and fly the sequence.
    # -----------------------------------------------------------------------
    rocket = LaunchVehicle(exc, "rocket")
    rocket.params.planet_ptr(earth.outputs.self_id())
    # params.mass is the DRY vehicle; the propellant rides on top in the
    # LaunchVehicle's own tank, drained by the main engine.
    rocket.params.mass(DRY_MASS_KG)
    rocket.params.propellant_mass_init(PROPELLANT_MASS_KG)

    rocket.params.main_engine_thrust(ENGINE_THRUST_N)
    rocket.params.main_engine_mdot(ENGINE_MDOT_KG_S)
    rocket.params.main_engine_location__body(
        CartesianVector3([ENGINE_STATION_M, 0.0, 0.0]))
    rocket.params.main_engine_max_gimbal(ENGINE_MAX_GIMBAL_DEG*DEGREES_TO_RADIANS)
    rocket.params.main_engine_latency(ENGINE_LATENCY_MS)
    rocket.params.inertia_dry__body(
        Matrix3([[ROLL_INERTIA_DRY_KG_M2, 0.0,                     0.0],
                 [0.0,                    PITCH_INERTIA_DRY_KG_M2, 0.0],
                 [0.0,                    0.0,                     PITCH_INERTIA_DRY_KG_M2]]))
    rocket.params.inertia_full__body(
        Matrix3([[ROLL_INERTIA_FULL_KG_M2, 0.0,                      0.0],
                 [0.0,                     PITCH_INERTIA_FULL_KG_M2, 0.0],
                 [0.0,                     0.0,                      PITCH_INERTIA_FULL_KG_M2]]))

    # Aero geometry. ca and the CP station are scheduled against Mach in the loop.
    rocket.params.aero_reference_area(AERO_REFERENCE_AREA_M2)
    rocket.params.aero_cn_alpha(AERO_CN_ALPHA)
    rocket.params.aero_nose_tip__body(CartesianVector3([NOSE_TIP_STATION_M, 0.0, 0.0]))

    # Fit the chutes.
    rocket.params.drogue_area(DROGUE_AREA_M2)
    rocket.params.drogue_cd(DROGUE_CD)
    rocket.params.drogue_untangle_time_s(DROGUE_UNTANGLE_S)
    rocket.params.drogue_fill_time_s(DROGUE_FILL_S)
    rocket.params.drogue_cord_length(DROGUE_CORD_M)

    rocket.params.main_chute_area(MAIN_AREA_M2)
    rocket.params.main_chute_cd(MAIN_CD)
    rocket.params.main_chute_untangle_time_s(MAIN_UNTANGLE_S)
    rocket.params.main_chute_fill_time_s(MAIN_FILL_S)
    rocket.params.main_chute_cord_length(MAIN_CORD_M)

    # -----------------------------------------------------------------------
    # Launch pad / rail. Built AFTER the rocket -- the pad mounts the body in
    # its start(), and whatever is built later wins. The pad takes the vehicle
    # body frame, whose +X is the nose axis it slides along.
    # -----------------------------------------------------------------------
    pad = LaunchPadModel(exc, "launch_pad")
    pad.params.rocket_body_ptr(rocket.outputs.body())
    # planet_ptr takes the whole planet object (SpicePlanet or CustomPlanet); the
    # pad reads its inertial/rotating frames and ellipsoid shape from it.
    pad.params.planet_ptr(earth)

    pad.params.launch_lat_deg(LAUNCH_LAT_DEG)
    pad.params.launch_lon_deg(LAUNCH_LON_DEG)
    pad.params.launch_alt_wgs84_m(LAUNCH_ALT_WGS84_M)

    pad.params.azimuth_deg(RAIL_AZIMUTH_DEG)
    pad.params.elevation_deg(RAIL_ELEVATION_DEG)
    pad.params.rail_length_m(RAIL_LENGTH_M)

    # -----------------------------------------------------------------------
    # Logging. percent_open next to the deploy flags is what shows the canopies
    # inflating over a second or two instead of snapping open.
    # -----------------------------------------------------------------------
    log = CsvLogger(exc, "sounding_rocket.csv")
    log.addParameter(exc.time().base_time,                   "time_s")
    log.addParameter(rocket.outputs.altitude_detic,          "altitude_m")
    log.addParameter(rocket.outputs.latitude_detic,          "latitude_rad")
    log.addParameter(rocket.outputs.longitude,               "longitude_rad")
    log.addParameter(rocket.outputs.vel_sc_pci,              "vel_pci_mps")
    log.addParameter(rocket.outputs.aero_mach,               "mach")
    log.addParameter(rocket.outputs.aero_dynamic_pressure,   "q_pa")
    log.addParameter(rocket.outputs.aero_angle_of_attack,    "aoa_rad")
    log.addParameter(rocket.outputs.aero_force__body,        "aero_force_N")
    log.addParameter(rocket.inputs.deploy_drogue,            "drogue_deployed")
    log.addParameter(rocket.inputs.deploy_main_chute,        "main_deployed")
    log.addParameter(rocket.outputs.drogue_percent_open,     "drogue_percent_open")
    log.addParameter(rocket.outputs.main_chute_percent_open, "main_percent_open")
    log.addParameter(rocket.outputs.drogue_force__pcr,       "drogue_force_N")
    log.addParameter(rocket.outputs.main_chute_force__pcr,   "main_force_N")
    log.addParameter(rocket.outputs.thrust_applied__body,    "thrust_cmd_N")
    log.addParameter(rocket.outputs.propellant_mass,         "propellant_kg")
    log.addParameter(rocket.outputs.total_mass,              "mass_kg")
    log.addParameter(rocket.outputs.quat_sc_pci,             "quat_pci")
    log.addParameter(rocket.outputs.ang_vel_sc_pci__body,    "body_rate_rps")
    log.addParameter(pad.outputs.vehicle_connected,          "on_rail")
    exc.logManager().addLog(log, Time(0, 200000000))   # 0.2 s -- fine enough to
                                                       # resolve the rail phase
                                                       # and the canopies filling

    # -----------------------------------------------------------------------
    # Run
    # -----------------------------------------------------------------------
    exc.startup()

    apogee_m = 0.0
    apogee_time_s = 0.0
    lifted_off = False
    meco_time_s = None
    drogue_time_s = None
    main_time_s = None
    prev_altitude_m = rocket.outputs.altitude_detic()

    while not exc.isTerminated():
        time_s = exc.time().base_time().asFloatingPoint()

        # Schedule the aerodynamics against Mach. outputs.aero_mach is the vehicle's
        # own freestream Mach (a step behind, which is immaterial at 100 Hz); the
        # helpers above turn it into the axial coefficient and the CP station.
        mach = rocket.outputs.aero_mach()
        rocket.inputs.aero_ca(axialCoefficient(mach))
        rocket.inputs.aero_pos_cp__nose(
            CartesianVector3([cpFromNose(mach), 0.0, 0.0]))

        # Fly the engine. The command is a thrust vector in the body frame, and
        # +X is straight out the nose, so this is full thrust along the vehicle
        # axis -- up the rail while the pad still holds it, and along the release
        # attitude after that. The vehicle burns its own propellant tank down and
        # cuts the engine off when it runs dry; the guard here just stops
        # commanding thrust at that point and marks MECO. outputs.propellant_mass
        # is a step behind the tank, which is immaterial at 100 Hz.
        if time_s >= IGNITION_TIME_S and rocket.outputs.propellant_mass() > 0.0:
            rocket.inputs.thrust_command__body(
                CartesianVector3([ENGINE_THRUST_N, 0.0, 0.0]))
        else:
            rocket.inputs.thrust_command__body(CartesianVector3([0.0, 0.0, 0.0]))
            if meco_time_s is None and time_s > IGNITION_TIME_S:
                meco_time_s = time_s
                print("MECO at t = %.2f s, altitude %.0f m, Mach %.1f, mass %.1f kg"
                      % (time_s, rocket.outputs.altitude_detic(), mach,
                         rocket.outputs.total_mass()))

        err = exc.step()
        if err:
            sys.exit(1)

        # Track the flight. Altitude is measured against the WGS-84 ellipsoid, so
        # the vehicle starts at pad altitude and is back on the ground when it
        # returns to it.
        altitude_m = rocket.outputs.altitude_detic()
        if altitude_m > apogee_m:
            apogee_m = altitude_m
            apogee_time_s = exc.time().base_time().asFloatingPoint()
        if altitude_m > LAUNCH_ALT_WGS84_M + LIFTOFF_ALT_M:
            lifted_off = True

        # Recovery sequence. Both deploy inputs latch inside the vehicle, but they
        # are held true here as well so the logged column reads as the state of the
        # event rather than a one-step pulse.
        #
        # Drogue at apogee: the vehicle has flown, and this step's altitude is no
        # higher than the last. Falling back on a timer would work here too, but
        # this rides through whatever the ascent actually did.
        if lifted_off and drogue_time_s is None and altitude_m <= prev_altitude_m:
            rocket.inputs.deploy_drogue(True)
            drogue_time_s = exc.time().base_time().asFloatingPoint()
            print("Drogue deploy at t = %.2f s, altitude %.0f m"
                  % (drogue_time_s, altitude_m))

        # Main on the way down, once low enough that its opening load and its long
        # descent are both acceptable. Fired on altitude above the pad, so it lands
        # where it belongs whatever the ascent and the drogue descent did.
        if (drogue_time_s is not None and main_time_s is None
                and altitude_m <= LAUNCH_ALT_WGS84_M + MAIN_DEPLOY_AGL_M):
            rocket.inputs.deploy_main_chute(True)
            main_time_s = exc.time().base_time().asFloatingPoint()
            print("Main chute deploy at t = %.2f s, altitude %.0f m AGL"
                  % (main_time_s, altitude_m - LAUNCH_ALT_WGS84_M))

        if lifted_off and altitude_m <= LAUNCH_ALT_WGS84_M:
            # Descent rate at touchdown, from the change over the last step --
            # this is what the main canopy sizing bought.
            touchdown_mps = (prev_altitude_m - altitude_m)/step_size
            print("Touchdown at t = %.2f s, descent rate %.1f m/s"
                  % (exc.time().base_time().asFloatingPoint(), touchdown_mps))
            break

        prev_altitude_m = altitude_m

    print("Apogee %.0f m above the ellipsoid (%.1f km above the pad) at t = %.2f s"
          % (apogee_m, (apogee_m - LAUNCH_ALT_WGS84_M)/1000.0, apogee_time_s))