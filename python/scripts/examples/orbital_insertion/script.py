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
Single-stage-to-orbit ascent, closed-loop guided, with a Monte Carlo dispersion sweep
====================================================================================

WHAT THIS EXAMPLE IS
--------------------
A notional single-stage-to-orbit (SSTO) launch vehicle is flown from a pad at
Kennedy Space Center into a ~200 km circular parking orbit and its payload is
released. The whole flight is closed-loop:

  * the plant is a ``LaunchVehicle`` (body + J2/J3 gravity + NRLMSISE-00
    atmosphere + a gimballed main engine + a propellant tank + rocket
    aerodynamics), released from a ``LaunchPadModel`` hold-down;

  * navigation is a ``StochasticNavigation`` model -- the true 6-DOF state is
    corrupted with GPS/INS-grade white noise and a random-walk bias, and *that*
    estimate, not truth, is what the guidance and control see;

  * exo-atmospheric guidance is the ``UnifiedPoweredFlightGuidance`` (UPFG) app
    -- the Space Shuttle "Powered Explicit Guidance" predictor-corrector -- which
    produces a commanded inertial thrust direction, a throttle, and a
    time-to-go; and

  * attitude control is the ``SingleAxisPointingControl`` app, a sliding-mode
    law that slews the vehicle's +X (thrust) axis onto the commanded direction
    and trims the thrust-vector-misalignment disturbance. Its pitch/yaw torque
    is flown by the real main-engine gimbal (a lateral thrust component at the
    engine station makes the body moment); roll, which a single gimballed engine
    cannot make, is trimmed by a small reaction-control node.

The GN&C stack is deliberately NOT a mirror of the plant (see "MODEL ERROR"
below), and every run draws a fresh set of vehicle / environment / pad
dispersions from the executive's Monte Carlo dispersion engine, so no two runs
fly the same trajectory. Run 0 is the undispersed reference.

FLIGHT SEQUENCE (all sequenced by this script; the vehicle sequences nothing)
---------------------------------------------------------------------------
    t = IGNITION_TIME_S      main engine lights; vehicle still on the hold-down
    hold-down release        pad releases the vehicle once it has thrust to move
    + VERTICAL_RISE_S        vertical rise to clear the pad
    pitch program            open-loop inertial pitch-over (a stored pitch table,
                             the way a real vehicle flies the first ~2 minutes)
    UPFG handoff             above UPFG_HANDOFF_ALT_M and below UPFG_HANDOFF_Q_PA,
                             guidance goes closed-loop: UPFG steers the rest of
                             the ascent and commands the throttle
    terminal flatten         over the last TERMINAL_FLATTEN_MPS of speed-to-go the
                             steering eases off UPFG onto the exact in-plane
                             prograde horizontal, holding the flight-path angle
                             flat into cutoff
    MECO                     main-engine cutoff when the vehicle's TRUE orbital
                             energy (plus the thrust still in the valve pipeline)
                             reaches the circular-orbit value -- see "TERMINAL
                             GUIDANCE & CUTOFF"
    + SEP_COAST_S            short settling coast, then payload separation
                             (see "PAYLOAD SEPARATION" -- currently a stub)

The switch to closed-loop guidance is an abrupt mode change: UPFG's converged
command points where the *end* of the ascent wants the thrust, ~50-60 deg off
the open-loop pitch attitude. The commanded turn rate is limited (TARGET_SLEW_DPS)
so that reorientation is spread over a few seconds at falling dynamic pressure,
but there is still a real guidance-initiate transient -- a brief attitude-tracking
excursion and a large-but-inconsequential angle of attack at q < 2 kPa. A flight
design would either hand off higher or fair the pitch program into the guidance
command; it is left visible here because it is characteristic of an open-loop ->
closed-loop handover and the Monte Carlo report quantifies it.

MODEL ERROR (why the GN&C disagrees with reality)
-------------------------------------------------
Two independent sources, both always on:

  1. Navigation error. ``StochasticNavigation`` feeds UPFG and the autopilot a
     noisy, slowly-drifting state instead of truth.

  2. Guidance model error. UPFG's engine deck (thrust and Isp) carries a small
     fixed bias (``GNC_THRUST_BIAS_FRAC`` / ``GNC_ISP_BIAS_FRAC``) -- the flight
     computer's model is never exactly the engine that flies -- and on a
     dispersed run the true engine is also off its own nominal, so UPFG's
     predictor is wrong in two ways at once and its corrector has to fly it out.
     UPFG *is* fed the true vehicle mass (a real flight computer integrates the
     tank gauge and knows its mass to a few kg); a drifting mass estimate mostly
     just makes UPFG's near-cutoff time-to-go stall and the insertion go
     elliptical, which is not the effect this example is about. The vehicle also
     carries a dispersed thrust-vector misalignment that the autopilot must
     trim.

TERMINAL GUIDANCE & CUTOFF (how the insertion is held near-circular)
-------------------------------------------------------------------
The insertion orbit is a sensitive amplifier of the MECO state: eccentricity is
roughly ``sin(flight-path angle)``, and at 200 km a cutoff speed error of a few
m/s is ~10 km of apoapsis. UPFG on its own leaves tens of km of apoapsis and
e ~ 0.02-0.04 here -- its predictor-corrector degrades over a long single-stage
constant-acceleration burn, its time-to-go stalls in the last couple of seconds,
and its converged cutoff still sits ~15-25 m/s short because of the engine-deck
bias above. Three script-level terminal refinements (all in PHASE 3) take that
out. They are DEMONSTRATOR shortcuts, valid because this target is a circular
orbit -- they are NOT things UPFG itself is missing:

  * over the last TERMINAL_FLATTEN_MPS of speed-to-go the commanded direction is
    eased off UPFG's ``i_f`` onto the exact in-plane prograde horizontal, so the
    flight-path angle is driven to zero at cutoff (e ~ sin(gamma) ~ 0). UPFG
    already targets the flight-path angle (``gamma_cutoff``; Block 5's near-cutoff
    freeze steers ``unit(V_go)``, which for gamma = 0 IS prograde-horizontal) --
    this only substitutes the clean geometric direction for a ``V_go`` that has
    gone noisy in the last ~2 s. It is correct ONLY for a horizontal cutoff;
    for any gamma_cutoff != 0 it would steer away from the target;

  * MECO is taken on the vehicle's TRUE specific orbital energy reaching the
    circular value ``-mu / 2 r_target`` -- not on UPFG's internal latch -- which
    closes the engine-deck residual directly; and

  * that energy check LEADS the cutoff by the engine latency. The throttle
    commands already in the valve pipeline (the last ENGINE_LATENCY_MS of them)
    keep firing after the cutoff command; the script sums that pending impulse
    and cuts early by exactly it, so an ~80 ms / ~15 m/s thrust tail lands the
    burn ON the target instead of ~50 km of apoapsis past it. This is the same
    intent as UPFG's own ``meco_tgo_lead`` (paper 4.9), but pipeline-exact rather
    than a fixed time-lead, and applied to our energy cut rather than its t_go.

With those in, a 64-case Monte Carlo holds periapsis 195-200 km, apoapsis
200-210 km and e < 0.0011 on every run. UPFG still flies the whole ascent and
the entire terminal turn; these only shape the final ~150 m/s and pick the
cutoff instant.

MONTE CARLO
-----------
Every dispersion is registered with ``exc.dispersions()`` so it lands in
``<out-dir>/dispersions.adoc`` for traceability. Each run also writes
``<out-dir>/summary.json`` (insertion accuracy, margins, peak loads, the
dispersion draw) which ``analysis.py`` aggregates into an HTML report.

    # one reference run
    python3 script.py --run=0 --out-dir=results/run_0

    # a 200-case sweep (multirun.sh fans it out, one process per run)
    ./multirun.sh -f script.py -n 200

    # then build the report
    python3 analysis.py

Author: James Tabony <james.tabony@warpware.co>
"""

import json
import math
import os
import sys

import numpy as np

from warptwin.WarpTwinPy import (
    SimulationExecutive,
    CartesianVector3,
    CartesianVector4,
    Matrix3,
    Node,
    Time,
    CsvLogger,
    connectSignals,
    START_STEP,
    END_STEP,
    LOG_INFO,
)
from warptwin.SpicePlanet import SpicePlanet
from warptwin.LaunchPadModel import LaunchPadModel
from warptwin.LaunchVehicle import LaunchVehicle
from warptwin.StochasticNavigation import StochasticNavigation
from warptwin.SingleAxisPointingControl import SingleAxisPointingControl
from warptwin.UnifiedPoweredFlightGuidance import (
    UnifiedPoweredFlightGuidance,
    thrust_mode_e_CONSTANT_ACCEL,
    upfg_mode_e_STANDARD_ASCENT,
)

# ===========================================================================
#  SECTION 1 -- physical constants
#  MU / R_EARTH match warpos::earth_wgs84 (the values UPFG uses internally), so
#  the guidance target and the analysis orbit maths are on the same ellipsoid.
# ===========================================================================
MU = 3.986004418e14         # Earth gravitational parameter, m^3/s^2
G0 = 9.80665                # standard gravity (the Isp reference), m/s^2
R_EARTH = 6378137.0         # WGS-84 equatorial radius, m
DEG = math.pi / 180.0

# ===========================================================================
#  SECTION 2 -- launch site and hold-down
#  Kennedy Space Center, LC-39A. Due-east azimuth -> minimum-inclination
#  (~28.6 deg) launch. Elevation is a degree off vertical so the vehicle leaves
#  the pad with a small downrange lean, the way a real launch mount is canted.
# ===========================================================================
LAUNCH_LAT_DEG = 28.608
LAUNCH_LON_DEG = -80.604
LAUNCH_ALT_WGS84_M = 3.0
RAIL_AZIMUTH_DEG = 90.0     # 0 = North, 90 = East, 180 = South, 270 = West
RAIL_ELEVATION_DEG = 89.0   # 90 = vertical
RAIL_LENGTH_M = 8.0         # hold-down / launch-mount travel before release

# ===========================================================================
#  SECTION 3 -- the vehicle (a notional advanced SSTO)
#
#  SSTO is a demanding point in the trade space: the vehicle carries every
#  kilogram of propellant the whole way up, so it needs a very high propellant
#  mass fraction and a high-performance engine. The numbers below describe a
#  ~665 t hydrolox/aerospike-class vehicle -- an aggressive but internally
#  consistent design, not a specific real one.
#
#      ideal delta-V  = Isp * g0 * ln(GLOW / dry) ~ 11.9 km/s
#      gravity+drag+steering losses over the flown trajectory ~ 2.3 km/s
#      Earth-rotation assist (due east from 28.6 N) ~ 0.41 km/s
#  which leaves margin over the ~9.4 km/s needed to reach the parking orbit;
#  MECO is commanded by guidance, with propellant to spare.
# ===========================================================================
DRY_MASS_KG = 47000.0           # airframe + engine + residuals + the payload stack
PAYLOAD_MASS_KG = 4200.0        # the satellite launchSat() will release (part of dry)
PROPELLANT_MASS_KG = 618000.0   # loaded at liftoff, burned down by the main engine
GLOW_KG = DRY_MASS_KG + PROPELLANT_MASS_KG

ENGINE_THRUST_N = 10.8e6        # vacuum thrust at full throttle (T/W ~ 1.68 off the pad)
ENGINE_ISP_S = 460.0            # vacuum specific impulse
ENGINE_MDOT_KG_S = ENGINE_THRUST_N / (ENGINE_ISP_S * G0)
ENGINE_STATION_M = -32.0        # nozzle position on body X, aft of the CG
ENGINE_MAX_GIMBAL_DEG = 6.0     # gimbal cone half-angle
ENGINE_LATENCY_MS = 80          # throttle-command -> engine-response delay
ACCEL_LIMIT_G = 6.0             # structural accel limit UPFG throttles the engine to hold

# Inertia for a ~60 m x 8 m diameter vehicle about its CG. Modelled as a uniform
# slender body: I = (per-kg tensor) x mass. The LaunchVehicle is given the dry and
# fuelled tensors as params and interpolates between them by propellant fraction
# (see SECTION 12). A real vehicle's mass-properties model would supply measured
# tensors -- the dry structure is relatively end-heavy (tank domes, engine).
BODY_LENGTH_M = 60.0
BODY_RADIUS_M = 4.0
IYY_PER_KG = BODY_LENGTH_M ** 2 / 12.0 + BODY_RADIUS_M ** 2 / 4.0   # pitch / yaw
IXX_PER_KG = 0.5 * BODY_RADIUS_M ** 2                               # roll
NOSE_TIP_STATION_M = 34.0       # nose tip on body X, forward of the CG

# ===========================================================================
#  SECTION 4 -- aerodynamics
#  reference_area is the 8 m diameter cross-section. The axial-force coefficient
#  and the centre-of-pressure station are strong functions of Mach, so they are
#  scheduled every step against outputs.aero_mach by the helpers below. The CP
#  sits aft of the CG (positive static margin) -- the vehicle is weathercock
#  stable and flies the pitch program at near-zero angle of attack.
# ===========================================================================
AERO_REFERENCE_AREA_M2 = math.pi * BODY_RADIUS_M ** 2
AERO_CN_ALPHA = 3.0                 # normal-force slope, per rad (slender body + fins)
CA0_SUBSONIC = 0.30                 # axial-force coefficient below the drag rise
CA_TRANSONIC = 0.60                 # axial-force coefficient through Mach 1
CA_SUPERSONIC_FLOOR = 0.26
CP_FROM_NOSE_SUBSONIC_M = 38.0      # CP aft of the nose tip -> 4 m aft of the CG (stable)
CP_FROM_NOSE_SUPERSONIC_M = 33.0    # CP migrates forward through the transonic region


def axial_coefficient(mach):
    """Transonic axial-force rise: flat below Mach 0.8, ramping to the transonic
    value through Mach 1, then easing back off supersonic. Stand-in for a real
    ca-vs-Mach table."""
    if mach < 0.8:
        return CA0_SUBSONIC
    if mach < 1.2:
        frac = (mach - 0.8) / 0.4
        return CA0_SUBSONIC + frac * (CA_TRANSONIC - CA0_SUBSONIC)
    return max(CA_TRANSONIC - 0.10 * (mach - 1.2), CA_SUPERSONIC_FLOOR)


def cp_from_nose(mach):
    """Centre of pressure as a distance aft of the nose tip; it migrates forward
    (toward the nose, smaller number) through the transonic region."""
    if mach < 0.8:
        return CP_FROM_NOSE_SUBSONIC_M
    if mach > 1.2:
        return CP_FROM_NOSE_SUPERSONIC_M
    frac = (mach - 0.8) / 0.4
    return CP_FROM_NOSE_SUBSONIC_M + frac * (CP_FROM_NOSE_SUPERSONIC_M - CP_FROM_NOSE_SUBSONIC_M)


# ===========================================================================
#  SECTION 5 -- ascent profile / mission sequence
# ===========================================================================
STEP_S = 0.01                   # 100 Hz -- resolves the hold-down phase, Max-Q and the autopilot
END_TIME_S = 900.0              # generous; the run stops itself at payload separation

IGNITION_TIME_S = 3.0           # sit on the pad a moment, then light the engine
VERTICAL_RISE_S = 9.0           # vertical rise after hold-down release
PITCH_RATE_DPS = 0.58           # open-loop pitch-over rate about the pad vertical, deg/s
PITCH_MAX_DEG = 50.0            # total open-loop pitch angle from the pad vertical

TARGET_ALT_M = 200.0e3          # circular parking-orbit altitude
UPFG_HANDOFF_ALT_M = 42.0e3     # go closed-loop above this altitude ...
UPFG_HANDOFF_Q_PA = 6000.0      # ... and below this dynamic pressure (Max-Q is past)

GUIDANCE_PERIOD_S = 0.5         # UPFG re-plans at 2 Hz; its command is held between updates
IF_LPF_TAU_S = 0.8              # first-order smoothing of UPFG's steering command
# The commanded attitude vector is rate-limited to a real vehicle pitch rate, so
# the big one-time reorientation at UPFG handoff is spread over several seconds
# (at ever-lower dynamic pressure) instead of stepped.
TARGET_SLEW_DPS = 15.0          # cap on the commanded turn rate during handoff, deg/s
HANDOFF_SLEW_S = 6.0            # ... for this long after handoff
# Terminal phase. The insertion orbit is a sensitive amplifier of the MECO state:
# eccentricity ~ sin(gamma_cutoff), and a few m/s of cutoff speed error is ~10 km
# of apoapsis. Three things tighten it: over the last TERMINAL_FLATTEN_MPS of speed
# the steering eases onto the exact in-plane prograde horizontal so gamma is held
# flat into cutoff; MECO is taken when the vehicle's TRUE orbital energy reaches
# the circular value rather than on UPFG's own latch (which stops ~15-25 m/s short
# because its engine deck is biased); and the energy check LEADS the cutoff by the
# throttle commands still in the valve pipeline (the last ENGINE_LATENCY_MS of
# them), which keep firing after the cutoff command and would otherwise carry the
# burn tens of km past the target -- an 80 ms full-thrust tail is ~15 m/s, and
# ~15 m/s here is ~50 km of apoapsis. A real flight computer leads its cutoff by
# the known valve lag the same way. TGO_FREEZE_S just arms a far predicted-time
# backstop.
TGO_FREEZE_S = 2.5
TERMINAL_FLATTEN_MPS = 150.0
SEP_COAST_S = 5.0               # settle after MECO before releasing the payload

# ===========================================================================
#  SECTION 6 -- GN&C configuration (deliberately NOT the plant)
# ===========================================================================
# Flight-computer engine deck vs the real engine. Even on run 0 (undispersed
# vehicle) the guidance predictor is off by this much; UPFG's V_go corrector
# absorbs it.
GNC_THRUST_BIAS_FRAC = 0.004    # engine deck reads 0.4 % high on thrust
GNC_ISP_BIAS_FRAC = -0.0025     # ... and 0.25 % low on Isp
# UPFG aims a hair below local horizontal at cutoff so the terminal command-hold
# (see TGO_FREEZE_S) lands the flight-path angle near zero rather than climbing.
GNC_GAMMA_CUTOFF_DEG = -0.05

# SingleAxisPointingControl gains (sliding-mode pointing law). lambda/eta sets the
# closed-loop frequency, gamma/eta the reaching rate. Fixed for the whole flight;
# the mass/inertia the loop is told about is its own estimate, not truth.
CTRL_LAMBDA = 0.9
CTRL_ETA = 1.6
CTRL_GAMMA = 3.5
CTRL_LPF_ALPHA = 0.5

# ===========================================================================
#  SECTION 7 -- navigation sensor model (StochasticNavigation)
#  GPS/INS-blended grade. *_NOISE are per-axis 1-sigma white-noise standard
#  deviations (drawn fresh each cycle); *_WALK are the per-axis random-walk bias
#  standard deviations. Attitude terms are small -- a good star-tracker / IMU.
# ===========================================================================
NAV_POS_NOISE_M = 6.0
NAV_VEL_NOISE_MPS = 0.06
NAV_ATT_NOISE = 2.0e-4          # per quaternion component
NAV_RATE_NOISE_RPS = 3.0e-4
NAV_POS_WALK_M = 0.4
NAV_VEL_WALK_MPS = 0.004
NAV_ATT_WALK = 2.0e-5
NAV_RATE_WALK_RPS = 2.0e-5

# ===========================================================================
#  SECTION 8 -- Monte Carlo dispersion 1-sigmas
# ===========================================================================
DISP_DRY_MASS_FRAC = 0.015          # structural / residuals mass knowledge
DISP_PROP_MASS_FRAC = 0.004         # propellant load gauging
DISP_THRUST_FRAC = 0.015            # engine thrust (build + run-to-run)
DISP_ISP_FRAC = 0.007               # engine Isp
DISP_THRUST_MISALIGN_DEG = 0.12     # fixed thrust-vector misalignment, per axis
DISP_AERO_AXIAL_FRAC = 0.10         # axial-force-coefficient schedule scale
DISP_AERO_CP_SHIFT_M = 0.4          # centre-of-pressure station (static margin)
DISP_AZIMUTH_DEG = 0.30             # commanded pad azimuth (setpoint / survey)
DISP_ELEVATION_DEG = 0.20           # commanded pad elevation
DISP_PITCH_RATE_FRAC = 0.04         # open-loop pitch-program rate (trajectory shaping)
RAIL_FLEX_1SIGMA_DEG = 0.8          # structural hold-down misalignment (pad's own model)

# ---------------------------------------------------------------------------
#  small vector helpers (numpy under the hood; CartesianVector3 at the boundary)
# ---------------------------------------------------------------------------
def _u(v):
    n = np.linalg.norm(v)
    return v / n if n > 0.0 else v


def _cv(v):
    return CartesianVector3([float(v[0]), float(v[1]), float(v[2])])


def _v3(cv):
    return np.array([cv.get(0), cv.get(1), cv.get(2)])


def _rot(vec, axis, angle):
    """Rodrigues rotation of ``vec`` about unit ``axis`` by ``angle`` rad."""
    axis = _u(np.asarray(axis, dtype=float))
    c, s = math.cos(angle), math.sin(angle)
    return vec * c + np.cross(axis, vec) * s + axis * np.dot(axis, vec) * (1.0 - c)


def _mission_time(t_sec):
    s = int(math.floor(t_sec))
    return Time(s, int(round((t_sec - s) * 1e9)))


def _inertia_tensor(mass):
    return Matrix3([[IXX_PER_KG * mass, 0.0, 0.0],
                    [0.0, IYY_PER_KG * mass, 0.0],
                    [0.0, 0.0, IYY_PER_KG * mass]])


def _orbital_elements(r_vec, v_vec):
    """Classical elements from an inertial state. Returns a dict in km / deg."""
    r = np.linalg.norm(r_vec)
    v = np.linalg.norm(v_vec)
    h_vec = np.cross(r_vec, v_vec)
    h = np.linalg.norm(h_vec)
    energy = 0.5 * v * v - MU / r
    a = -MU / (2.0 * energy)
    e_vec = np.cross(v_vec, h_vec) / MU - r_vec / r
    e = float(np.linalg.norm(e_vec))
    inc = math.degrees(math.acos(np.clip(h_vec[2] / h, -1.0, 1.0)))
    n_vec = np.array([-h_vec[1], h_vec[0], 0.0])
    n = np.linalg.norm(n_vec)
    raan = math.degrees(math.atan2(n_vec[1], n_vec[0])) % 360.0 if n > 0.0 else 0.0
    ra = a * (1.0 + e) - R_EARTH
    rp = a * (1.0 - e) - R_EARTH
    return dict(sma_km=a / 1e3, ecc=e, inc_deg=inc, raan_deg=raan,
                apoapsis_km=ra / 1e3, periapsis_km=rp / 1e3,
                fpa_deg=math.degrees(math.asin(np.clip(np.dot(_u(r_vec), _u(v_vec)), -1.0, 1.0))))


# flight phases
PH_PRELAUNCH, PH_VERTICAL, PH_PITCH, PH_UPFG, PH_POST_MECO = range(5)
PHASE_NAMES = ["prelaunch", "vertical_rise", "pitch_program", "upfg_closed_loop", "post_meco"]


def main():
    # -----------------------------------------------------------------------
    #  SECTION 9 -- executive
    #  parseArgs() reads --run / --out-dir / --end and seeds the dispersion
    #  engine from --run, so every dispersion created below immediately returns
    #  this run's value (run 0 returns the undispersed default).
    # -----------------------------------------------------------------------
    exc = SimulationExecutive()
    exc.args().addDefaultArgument("end", END_TIME_S)
    exc.parseArgs(sys.argv)
    exc.setRateSec(STEP_S)
    exc.setTime("2026 August 28, 12:00:00 UTC")
    exc.logLevel(LOG_INFO)

    run_number = exc.runNumber()
    out_dir = exc.logManager().outDir() or "results/"
    os.makedirs(out_dir, exist_ok=True)

    # -----------------------------------------------------------------------
    #  SECTION 10 -- Monte Carlo dispersions
    #  createNormalInputDispersion(name, default, mean, stdev, description).
    #  Call the returned handle twice: disp() -> the value object (loggable),
    #  disp()() -> this run's number.
    # -----------------------------------------------------------------------
    d = exc.dispersions()

    def _normal(name, nominal, frac_or_abs, description, absolute=False):
        sd = frac_or_abs if absolute else nominal * frac_or_abs
        return d.createNormalInputDispersion(name, nominal, nominal, sd, description)

    dry_disp = _normal("dry_mass_kg", DRY_MASS_KG, DISP_DRY_MASS_FRAC,
                       "Vehicle dry mass incl. payload stack [kg]")
    prop_disp = _normal("propellant_mass_kg", PROPELLANT_MASS_KG, DISP_PROP_MASS_FRAC,
                        "Main-engine propellant load at liftoff [kg]")
    thrust_disp = _normal("thrust_n", ENGINE_THRUST_N, DISP_THRUST_FRAC,
                          "Main-engine vacuum thrust at full throttle [N]")
    isp_disp = _normal("isp_s", ENGINE_ISP_S, DISP_ISP_FRAC,
                       "Main-engine vacuum specific impulse [s]")
    mis_pitch_disp = _normal("thrust_misalign_pitch_deg", 0.0, DISP_THRUST_MISALIGN_DEG,
                             "Fixed thrust-vector misalignment, body pitch [deg]", absolute=True)
    mis_yaw_disp = _normal("thrust_misalign_yaw_deg", 0.0, DISP_THRUST_MISALIGN_DEG,
                           "Fixed thrust-vector misalignment, body yaw [deg]", absolute=True)
    aero_axial_disp = _normal("aero_axial_scale", 1.0, DISP_AERO_AXIAL_FRAC,
                              "Scale on the axial-force-coefficient schedule [-]", absolute=True)
    aero_cp_disp = _normal("aero_cp_shift_m", 0.0, DISP_AERO_CP_SHIFT_M,
                           "Centre-of-pressure station shift [m]", absolute=True)
    az_disp = _normal("rail_azimuth_deg", RAIL_AZIMUTH_DEG, DISP_AZIMUTH_DEG,
                      "Commanded pad azimuth incl. setpoint/survey error [deg]", absolute=True)
    el_disp = _normal("rail_elevation_deg", RAIL_ELEVATION_DEG, DISP_ELEVATION_DEG,
                      "Commanded pad elevation incl. setpoint/survey error [deg]", absolute=True)
    pitch_rate_disp = _normal("pitch_rate_scale", 1.0, DISP_PITCH_RATE_FRAC,
                              "Scale on the open-loop pitch-program rate [-]", absolute=True)

    dry_mass = dry_disp()()
    prop_mass = prop_disp()()
    glow = dry_mass + prop_mass
    thrust_n = thrust_disp()()
    isp_s = isp_disp()()
    aero_axial_scale = aero_axial_disp()()
    aero_cp_shift = aero_cp_disp()()
    pitch_rate_dps = PITCH_RATE_DPS * pitch_rate_disp()()
    # fixed body-frame thrust direction: +X rotated by the (dispersed) misalignment
    thrust_dir_body = _rot(_rot(np.array([1.0, 0.0, 0.0]),
                                [0.0, 1.0, 0.0], mis_pitch_disp()() * DEG),
                           [0.0, 0.0, 1.0], mis_yaw_disp()() * DEG)

    # -----------------------------------------------------------------------
    #  SECTION 11 -- planet
    #  SpicePlanet wires up the inertial (J2000) and rotating (ECEF) frames the
    #  launch vehicle and pad reference. Earth is required: the atmosphere is
    #  NRLMSISE-00, which LaunchVehicle deactivates anywhere else.
    # -----------------------------------------------------------------------
    earth = SpicePlanet(exc, "earth")

    # -----------------------------------------------------------------------
    #  SECTION 12 -- the launch vehicle (the truth plant, dispersed)
    # -----------------------------------------------------------------------
    rocket = LaunchVehicle(exc, "rocket")
    rocket.params.planet_ptr(earth.outputs.self_id())
    rocket.params.mass(dry_mass)                       # DRY mass; the tank adds propellant on top
    rocket.params.propellant_mass_init(prop_mass)
    rocket.params.main_engine_thrust(thrust_n)
    rocket.params.main_engine_mdot(thrust_n / (isp_s * G0))
    rocket.params.main_engine_location__body(CartesianVector3([ENGINE_STATION_M, 0.0, 0.0]))
    rocket.params.main_engine_max_gimbal(ENGINE_MAX_GIMBAL_DEG * DEG)
    rocket.params.main_engine_latency(ENGINE_LATENCY_MS)
    rocket.params.aero_reference_area(AERO_REFERENCE_AREA_M2)
    rocket.params.aero_cn_alpha(AERO_CN_ALPHA)
    rocket.params.aero_nose_tip__body(CartesianVector3([NOSE_TIP_STATION_M, 0.0, 0.0]))
    # Dry and fuelled inertia tensors. The LaunchVehicle interpolates between them
    # by propellant fraction every step -- the script sets them once and the model
    # owns the variation with mass depletion.
    rocket.params.inertia_full__body(_inertia_tensor(glow))
    rocket.params.inertia_dry__body(_inertia_tensor(dry_mass))

    # -----------------------------------------------------------------------
    #  SECTION 13 -- navigation (StochasticNavigation)
    #  Truth 6-DOF state in, noisy estimate out. NOTE the angular-velocity feed:
    #  LaunchVehicle.outputs.ang_vel_sc_pci__body is expressed in PLANET-INERTIAL
    #  coordinates (the internal sensor has no body output frame), which the
    #  body-frame autopilot cannot use directly. body().ang_vel_f_p__f is the
    #  body-frame rate the controller expects.
    # -----------------------------------------------------------------------
    nav = StochasticNavigation(exc, END_STEP, "nav")
    nav.params.rate_hz(1.0 / STEP_S)
    nav.params.seed_value(run_number)      # a distinct, reproducible noise draw per run
    nav.params.pos_bias_random_walk_std(CartesianVector3([NAV_POS_WALK_M] * 3))
    nav.params.vel_bias_random_walk_std(CartesianVector3([NAV_VEL_WALK_MPS] * 3))
    nav.params.quat_bias_random_walk_std(CartesianVector4([NAV_ATT_WALK] * 4))
    nav.params.angvel_bias_random_walk_std(CartesianVector3([NAV_RATE_WALK_RPS] * 3))
    nav.inputs.pos_gaussian_noise_std(CartesianVector3([NAV_POS_NOISE_M] * 3))
    nav.inputs.vel_gaussian_noise_std(CartesianVector3([NAV_VEL_NOISE_MPS] * 3))
    nav.inputs.quat_gaussian_noise_std(CartesianVector4([NAV_ATT_NOISE] * 4))
    nav.inputs.angvel_gaussian_noise_std(CartesianVector3([NAV_RATE_NOISE_RPS] * 3))
    connectSignals(rocket.outputs.pos_sc_pci, nav.inputs.pos_perf)
    connectSignals(rocket.outputs.vel_sc_pci, nav.inputs.vel_perf)
    connectSignals(rocket.outputs.quat_sc_pci, nav.inputs.quat_perf)
    connectSignals(rocket.body().ang_vel_f_p__f, nav.inputs.angvel_perf)

    # -----------------------------------------------------------------------
    #  SECTION 14 -- attitude control (SingleAxisPointingControl)
    #  A 3-axis sliding-mode law: it produces the body torque that slews the
    #  vehicle +X (thrust) axis onto the commanded inertial direction and holds
    #  zero roll rate. Registered with the executive so it runs every step; its
    #  inputs are set from the NAV estimate each step, before exc.step().
    #
    #  HOW THE TORQUE IS FLOWN (see the loop): the PITCH/YAW part is realised by
    #  the real main-engine gimbal -- a lateral thrust component at the engine
    #  station (ENGINE_STATION_M aft of the CG) makes the body moment r x F, and
    #  LaunchVehicle clamps it to the gimbal cone. Roll a single gimballed engine
    #  cannot make, so the ROLL part is trimmed by a small reaction-control node.
    #  The saturation limit is set to the moment the gimbal can actually deliver,
    #  so the loop never asks for more than the actuator has.
    # -----------------------------------------------------------------------
    att = SingleAxisPointingControl(exc, "att_ctrl")
    exc.registerApp(att, START_STEP)
    att.params.pointing_vec__body(CartesianVector3([1.0, 0.0, 0.0]))   # point +X (thrust axis)
    att.params.omega_des(0.0)
    att.params.saturation(ENGINE_THRUST_N * abs(ENGINE_STATION_M) * math.sin(ENGINE_MAX_GIMBAL_DEG * DEG))
    att.params.lpf_alpha(CTRL_LPF_ALPHA)
    att.params.lambda_gain(CTRL_LAMBDA)
    att.params.eta_gain(CTRL_ETA)
    att.params.gamma_gain(CTRL_GAMMA)
    att.inputs.inertia(_inertia_tensor(glow))

    # Roll-axis reaction control. Single gimballed engine -> no roll authority
    # from the TVC, so this node carries only the commanded roll moment.
    rcs_roll_node = Node("rcs_roll", rocket.body())
    rcs_roll_node.moment_frame(rocket.body())

    # -----------------------------------------------------------------------
    #  SECTION 15 -- exo-atmospheric guidance (UnifiedPoweredFlightGuidance)
    #  Configured with the NOMINAL vehicle plus the fixed GNC bias -- NOT the
    #  dispersed truth. Driven by hand from the loop at GUIDANCE_PERIOD_S (it is
    #  NOT registered with the executive). A single CONSTANT_THRUST phase: the
    #  engine runs full-open to MECO. That gives UPFG a burn-time model that
    #  matches the plant (a CONSTANT_ACCEL / g-limit phase whose limit sits above
    #  the ignition thrust-to-weight does not), at the cost of a high -- ~20 g --
    #  terminal acceleration a real crewed or reusable stage would throttle out.
    # -----------------------------------------------------------------------
    gnc_thrust = ENGINE_THRUST_N * (1.0 + GNC_THRUST_BIAS_FRAC)
    gnc_isp = ENGINE_ISP_S * (1.0 + GNC_ISP_BIAS_FRAC)
    gnc_ve = gnc_isp * G0
    gnc_mdot = gnc_thrust / gnc_ve
    gnc_max_burn = (gnc_ve / (ACCEL_LIMIT_G * G0)) * math.log(GLOW_KG / (GLOW_KG - PROPELLANT_MASS_KG))
    r_target = R_EARTH + TARGET_ALT_M
    v_target = math.sqrt(MU / r_target)

    upfg = UnifiedPoweredFlightGuidance(exc, "upfg")
    upfg.setOperationMode(upfg_mode_e_STANDARD_ASCENT)
    rc = upfg.configureStage(0, True, thrust_mode_e_CONSTANT_ACCEL,
                             GLOW_KG, gnc_thrust, gnc_isp, gnc_max_burn, ACCEL_LIMIT_G)
    assert rc == 0, "UPFG configureStage returned %d" % rc
    upfg.params.radius_cutoff(r_target)
    upfg.params.speed_cutoff(v_target)
    upfg.params.gamma_cutoff(GNC_GAMMA_CUTOFF_DEG * DEG)
    upfg.params.time_ignition(Time(0, 0))      # we are past ignition whenever t > 0
    upfg.params.delta_t0(0.0)
    upfg.params.conv_criterion(0.1)
    upfg.params.max_prethrust_iterations(60)
    upfg.params.throttle_max(1.0)
    upfg.params.throttle_min(0.30)             # deepest the engine will throttle
    # meco_tgo_lead is UPFG's OWN engine-shutdown lead (paper 4.9): it latches
    # outputs.meco() once its internal t_go drops to this, to cover the shutdown
    # transient. Set it to the real command-to-thrust-off lag. It is not the
    # operative cutoff here -- UPFG's terminal |V_go| condition (Block 9) latches
    # meco() with ~20-30 m/s still to gain, and this example takes MECO on true
    # orbital energy with its own latency lead (PHASE 3) -- but it should still
    # carry the right number.
    upfg.params.meco_tgo_lead(ENGINE_LATENCY_MS / 1000.0)
    # plane_normal is set at handoff, from the launch-azimuth geometry.

    # -----------------------------------------------------------------------
    #  SECTION 16 -- hold-down / launch mount (built AFTER the rocket)
    #  The pad mounts the body in its start(); whatever is constructed last wins,
    #  so it must come after the vehicle. It reparents the body onto a rail frame
    #  (rotational joint locked, translation free along the rail axis) and
    #  releases it into free flight once it has slid rail_length_m.
    # -----------------------------------------------------------------------
    pad = LaunchPadModel(exc, "launch_pad")
    pad.params.rocket_body_ptr(rocket.outputs.body())
    pad.params.planet_ptr(earth)
    pad.params.launch_lat_deg(LAUNCH_LAT_DEG)
    pad.params.launch_lon_deg(LAUNCH_LON_DEG)
    pad.params.launch_alt_wgs84_m(LAUNCH_ALT_WGS84_M)
    pad.params.azimuth_deg(az_disp()())
    pad.params.elevation_deg(el_disp()())
    pad.params.rail_length_m(RAIL_LENGTH_M)
    pad.params.rail_disp_deg(0.0 if run_number == 0 else RAIL_FLEX_1SIGMA_DEG)
    pad.params.rail_disp_seed(run_number)

    # -----------------------------------------------------------------------
    #  SECTION 17 -- telemetry
    #  A CSV of the signal telemetry at 20 Hz (analysis.py overlays these across
    #  runs); the per-run scalar summary is assembled in the loop and written to
    #  summary.json at the end.
    # -----------------------------------------------------------------------
    log = CsvLogger(exc, "ascent.csv")
    log.addParameter(exc.time().base_time, "time_s")
    log.addParameter(rocket.outputs.altitude_detic, "altitude_m")
    log.addParameter(rocket.outputs.latitude_detic, "latitude_rad")
    log.addParameter(rocket.outputs.longitude, "longitude_rad")
    log.addParameter(rocket.outputs.pos_sc_pci, "pos_eci_m")
    log.addParameter(rocket.outputs.vel_sc_pci, "vel_eci_mps")
    log.addParameter(rocket.outputs.total_mass, "total_mass_kg")
    log.addParameter(rocket.outputs.propellant_mass, "propellant_mass_kg")
    log.addParameter(rocket.outputs.aero_mach, "mach")
    log.addParameter(rocket.outputs.aero_dynamic_pressure, "q_pa")
    log.addParameter(rocket.outputs.aero_angle_of_attack, "aoa_rad")
    log.addParameter(rocket.outputs.aero_sideslip_angle, "sideslip_rad")
    log.addParameter(rocket.outputs.thrust_applied__body, "thrust_cmd_n")
    log.addParameter(nav.outputs.pos_stoch, "nav_pos_eci_m")
    log.addParameter(nav.outputs.vel_stoch, "nav_vel_eci_mps")
    log.addParameter(upfg.outputs.i_f_cmd, "upfg_i_f_cmd")
    log.addParameter(upfg.outputs.t_go, "upfg_t_go_s")
    log.addParameter(upfg.outputs.v_go_mag, "upfg_v_go_mps")
    log.addParameter(upfg.outputs.throttle_cmd, "upfg_throttle")
    log.addParameter(upfg.outputs.converged, "upfg_converged")
    log.addParameter(upfg.outputs.meco, "upfg_meco")
    log.addParameter(att.outputs.pointing_error, "point_err_rad")
    log.addParameter(att.outputs.torque__body, "ctrl_torque_nm")
    log.addParameter(pad.outputs.vehicle_connected, "on_hold_down")
    exc.logManager().addLog(log, Time(0, 50000000))   # 20 Hz

    # -----------------------------------------------------------------------
    #  SECTION 18 -- start up, then fly
    # -----------------------------------------------------------------------
    if exc.startup():
        print("startup failed")
        sys.exit(1)
    att.activate()

    phase = PH_PRELAUNCH
    liftoff_t = None
    handoff_t = None
    meco_t = None
    sep_t = None
    cutoff_r_err_m = cutoff_v_err_mps = None
    cutoff_el = None
    # Throttle commands in flight down the engine-latency pipeline (one slot per
    # step over ENGINE_LATENCY_MS). The terminal energy cut sums these to know how
    # much thrust still lands after it commands zero -- see PHASE 3.
    n_pipe = max(1, int(round(ENGINE_LATENCY_MS / 1000.0 / STEP_S)))
    throttle_pipe = [0.0] * n_pipe
    rhat0 = pitch_axis0 = plane_h_hat = None
    next_guid_t = 0.0
    meco_pred_t = None

    i_f_raw = np.array([0.0, 0.0, 1.0])
    i_f_track = np.array([0.0, 0.0, 1.0])
    gtdir = np.array([0.0, 0.0, 1.0])
    target_cmd = None               # the rate-limited attitude command actually flown
    upfg_tgo = None
    upfg_vgo = 0.0
    upfg_throttle = 1.0
    upfg_converged = False
    gnc_mass = GLOW_KG               # the flight computer's own mass estimate

    # running trackers for the summary
    maxq_pa = maxq_t = maxq_alt = maxq_mach = 0.0
    max_aoa_deg = max_ssa_deg = 0.0        # through the structural-load region (q > 5 kPa)
    handoff_aoa_peak_deg = 0.0             # the brief guidance-init transient (low q)
    max_point_err_deg = 0.0
    max_ctrl_torque_nm = 0.0
    peak_nav_pos_err_m = peak_nav_vel_err_mps = 0.0
    upfg_converged_ever = False
    lpf_a = STEP_S / IF_LPF_TAU_S

    while not exc.isTerminated():
        t = exc.time().base_time().asFloatingPoint()

        # --- navigation estimate (produced at the previous END_STEP) --------
        r_nav = _v3(nav.outputs.pos_stoch())
        v_nav = _v3(nav.outputs.vel_stoch())
        q_nav = nav.outputs.quat_stoch()
        w_nav = _v3(nav.outputs.angvel_stoch())
        r_true = _v3(rocket.outputs.pos_sc_pci())
        v_true = _v3(rocket.outputs.vel_sc_pci())
        r_hat = _u(r_nav) if np.linalg.norm(r_nav) > 1.0e3 else (
            rhat0 if rhat0 is not None else np.array([0.0, 0.0, 1.0]))
        speed_true = np.linalg.norm(v_true)

        # --- aerodynamics scheduled against Mach (truth) -------------------
        mach = rocket.outputs.aero_mach()
        rocket.inputs.aero_ca(aero_axial_scale * axial_coefficient(mach))
        rocket.inputs.aero_pos_cp__nose(
            CartesianVector3([cp_from_nose(mach) + aero_cp_shift, 0.0, 0.0]))

        # --- mass properties -------------------------------------------------
        # The LaunchVehicle owns the truth inertia -- it interpolates dry <-> full
        # by propellant fraction from the two params set at setup. The autopilot is
        # only told the GN&C's own mass estimate, for gain scheduling.
        att.inputs.inertia(_inertia_tensor(gnc_mass))

        throttle_frac = 0.0
        target_dir = r_hat

        # =================================================================
        #  PHASE 0 -- PRELAUNCH: on the hold-down, engine off
        # =================================================================
        if phase == PH_PRELAUNCH:
            target_dir = r_hat
            if t >= IGNITION_TIME_S:
                phase = PH_VERTICAL

        # =================================================================
        #  PHASE 1 -- VERTICAL RISE: full thrust straight up until the pad
        #  releases and the vehicle has climbed clear
        # =================================================================
        if phase == PH_VERTICAL:
            throttle_frac = 1.0
            target_dir = r_hat
            if (not pad.outputs.vehicle_connected()) and liftoff_t is None:
                liftoff_t = t
                # freeze a launch-site basis for the open-loop pitch program
                rhat0 = _u(r_nav)
                east0 = _u(np.cross([0.0, 0.0, 1.0], rhat0))
                # right-hand rotation of rhat0 about pitch_axis0 tilts it downrange
                pitch_axis0 = _u(np.cross(east0, rhat0))
                print("Liftoff at t = %.2f s (hold-down release)" % t)
            if liftoff_t is not None and t - liftoff_t >= VERTICAL_RISE_S:
                phase = PH_PITCH

        # =================================================================
        #  PHASE 2 -- OPEN-LOOP PITCH PROGRAM: a stored inertial pitch table
        #  about the pad vertical, ramped at pitch_rate_dps to PITCH_MAX_DEG.
        #  This flies the vehicle through Max-Q at near-zero angle of attack.
        # =================================================================
        if phase == PH_PITCH:
            throttle_frac = 1.0
            elapsed = t - liftoff_t - VERTICAL_RISE_S
            theta = min(PITCH_MAX_DEG, pitch_rate_dps * elapsed) * DEG
            gtdir = _rot(rhat0, pitch_axis0, theta)
            target_dir = gtdir
            alt = rocket.outputs.altitude_detic()
            q_pa = rocket.outputs.aero_dynamic_pressure()
            if alt >= UPFG_HANDOFF_ALT_M and q_pa <= UPFG_HANDOFF_Q_PA:
                # ----- hand off to closed-loop guidance -------------------
                # Target orbit plane from the launch-azimuth geometry, NOT from
                # r x v -- the velocity is still near-radial here, so r x v is
                # ill-conditioned in direction. UPFG then holds this plane and
                # nulls whatever out-of-plane velocity the dispersed ascent
                # built up.
                east = _u(np.cross([0.0, 0.0, 1.0], r_hat))
                north = np.cross(r_hat, east)
                az = az_disp()() * DEG
                downrange = math.cos(az) * north + math.sin(az) * east
                plane_h_hat = _u(np.cross(r_hat, downrange))
                upfg.params.plane_normal(_cv(-plane_h_hat))   # UPFG: i_y = -h_hat
                upfg.inputs.pos__eci(_cv(r_nav))
                upfg.inputs.vel__eci(_cv(v_nav))
                upfg.inputs.mass(rocket.outputs.total_mass())
                upfg.inputs.time(_mission_time(t))
                rc = upfg.startup()                            # run the prethrust converge
                i_f_raw = _u(_v3(upfg.outputs.i_f_cmd()))
                i_f_track = gtdir.copy()
                upfg_tgo = float(upfg.outputs.t_go())
                upfg_vgo = float(upfg.outputs.v_go_mag())
                upfg_throttle = float(upfg.outputs.throttle_cmd())
                upfg_converged = bool(upfg.outputs.converged())
                upfg_converged_ever = upfg_converged_ever or upfg_converged
                phase = PH_UPFG
                handoff_t = t
                next_guid_t = t
                meco_pred_t = None
                fpa_air = math.degrees(math.asin(np.clip(
                    np.dot(r_hat, _u(v_nav)), -1.0, 1.0)))
                print("UPFG handoff at t = %.1f s: alt %.1f km, speed %.0f m/s, "
                      "gamma %.1f deg, q %.0f Pa, t_go %.0f s (startup rc %d)"
                      % (t, alt / 1e3, np.linalg.norm(v_nav), fpa_air, q_pa,
                         upfg_tgo, rc))

        # =================================================================
        #  PHASE 3 -- CLOSED-LOOP UPFG: guidance steers the rest of the ascent
        # =================================================================
        if phase == PH_UPFG:
            # Re-plan every cycle. UPFG is fed the NAV position and velocity (with
            # the noise) but the TRUE mass -- a flight computer tracks propellant
            # well from the tank gauge, and a drifting mass estimate is what makes
            # UPFG's near-cutoff t_go stall and the insertion go elliptical. Its
            # engine deck is still off (GNC_*_BIAS), which its V_go corrector
            # mostly absorbs; the small residual is closed by the energy cut below.
            if not upfg.outputs.meco() and t >= next_guid_t:
                next_guid_t = t + GUIDANCE_PERIOD_S
                upfg.inputs.pos__eci(_cv(r_nav))
                upfg.inputs.vel__eci(_cv(v_nav))
                upfg.inputs.mass(rocket.outputs.total_mass())
                upfg.inputs.time(_mission_time(t))
                if upfg.step() != 0:
                    print("UPFG faulted at t = %.1f s; holding last command" % t)
                    upfg_tgo = 0.0
                else:
                    i_f_raw = _u(_v3(upfg.outputs.i_f_cmd()))
                    upfg_tgo = float(upfg.outputs.t_go())
                    upfg_vgo = float(upfg.outputs.v_go_mag())
                    upfg_throttle = float(upfg.outputs.throttle_cmd())
                    upfg_converged = bool(upfg.outputs.converged())
                    upfg_converged_ever = upfg_converged_ever or upfg_converged
                    if upfg_tgo < TGO_FREEZE_S and meco_pred_t is None:
                        meco_pred_t = t + max(upfg_tgo, 0.0) + 8.0   # far backstop only

            # smooth UPFG's command; ease it onto the in-plane prograde horizontal
            # over the last ~150 m/s so the flight-path angle is held flat into
            # cutoff (eccentricity ~ sin(gamma_cutoff)).
            i_f_track = _u((1.0 - lpf_a) * i_f_track + lpf_a * i_f_raw)
            v_to_go = v_target - speed_true
            if plane_h_hat is not None and v_to_go < TERMINAL_FLATTEN_MPS:
                prograde = _u(np.cross(plane_h_hat, _u(r_true)))
                blend = min(1.0, max(0.0, 1.0 - v_to_go / TERMINAL_FLATTEN_MPS))
                target_dir = _u((1.0 - blend) * i_f_track + blend * prograde)
            else:
                target_dir = i_f_track

            # Fly UPFG's commanded throttle (it goes to full once UPFG latches its
            # own MECO), but take the cutoff HERE, when the vehicle's true specific
            # orbital energy reaches the circular value -- not on UPFG's latch,
            # which sits ~15-25 m/s short because of the engine-deck bias.
            #
            # The cut LEADS by the engine latency. Once the command goes to zero the
            # throttle commands already in the valve pipeline (the last
            # ENGINE_LATENCY_MS of them, held in throttle_pipe) still fire. The
            # flight computer knows exactly what it queued, so it sums that pending
            # tail and cuts when "energy after the tail" reaches circular -- landing
            # the burn on the target instead of tens of km past it (an 80 ms
            # full-thrust tail is ~15 m/s, and ~15 m/s here is ~50 km of apoapsis).
            r_now = np.linalg.norm(r_true)
            energy = 0.5 * speed_true ** 2 - MU / r_now
            energy_target = -MU / (2.0 * r_target)
            throttle_frac = 1.0 if upfg.outputs.meco() else upfg_throttle
            accel_per_frac = thrust_n / max(rocket.outputs.total_mass(), 1.0)
            tail_dv = sum(throttle_pipe) * STEP_S * accel_per_frac
            energy_next = energy + speed_true * tail_dv

            reached_meco = (energy_next >= energy_target
                            or (meco_pred_t is not None and t >= meco_pred_t))
            if reached_meco:
                meco_t = t
                phase = PH_POST_MECO
                el = _orbital_elements(r_true, v_true)
                print("MECO command at t = %.1f s (burn %.1f s): alt %.1f km, speed "
                      "%.1f m/s (target %.1f), gamma %+.2f deg -- %.0f kg propellant "
                      "remaining" % (
                          t, t - liftoff_t, (np.linalg.norm(r_true) - R_EARTH) / 1e3,
                          speed_true, v_target, el["fpa_deg"],
                          rocket.outputs.propellant_mass()))

        # =================================================================
        #  PHASE 4 -- POST-MECO COAST and PAYLOAD SEPARATION
        # =================================================================
        if phase == PH_POST_MECO:
            throttle_frac = 0.0
            target_dir = i_f_track          # hold the cutoff attitude
            # Latch the burnout orbit once the latency pipeline has flushed -- this
            # is the real insertion state, after the thrust tail, and is what the
            # "cutoff_*" fields in the summary report. The settling coast that
            # follows is ballistic and does not move it.
            if cutoff_el is None and t - meco_t >= n_pipe * STEP_S:
                cutoff_r_err_m = float(np.linalg.norm(r_true) - r_target)
                cutoff_v_err_mps = float(speed_true - v_target)
                cutoff_el = _orbital_elements(r_true, v_true)
                print("    burnout orbit: %.1f x %.1f km, incl %.2f deg, ecc %.5f"
                      % (cutoff_el["periapsis_km"], cutoff_el["apoapsis_km"],
                         cutoff_el["inc_deg"], cutoff_el["ecc"]))
            if sep_t is None and t - meco_t >= SEP_COAST_S:
                sep_t = t
                # ===========================================================
                #  PAYLOAD SEPARATION  --  rocket.launchSat()   [STUB: NOT YET
                #  IMPLEMENTED ON THE MODEL]
                #
                #  When LaunchVehicle grows a launchSat() method, replace the
                #  print below with:
                #
                #      payload = rocket.launchSat(
                #          "payload", PAYLOAD_MASS_KG, sep_delta_v_mps=0.6)
                #
                #  The method is expected to:
                #    * construct a Spacecraft ("payload") parented to the same
                #      planet-inertial frame the LaunchVehicle integrates against;
                #    * initialise its state from the LaunchVehicle's CURRENT
                #      inertial position / velocity / attitude
                #      (rocket.outputs.pos_sc_pci / vel_sc_pci / quat_sc_pci) at
                #      the instant of the call;
                #    * split a small separation delta-V (pusher springs) between
                #      the payload and the spent stage by mass ratio, along body
                #      +X;
                #    * debit PAYLOAD_MASS_KG from the LaunchVehicle so the spent
                #      stage carries only its residual mass afterwards;
                #    * return the new Spacecraft handle for downstream logging.
                #
                #  Everything past separation -- payload checkout, the spent-
                #  stage disposal burn, phasing to an operational orbit -- is
                #  out of scope for this example and would be wired in here.
                # ===========================================================
                el = _orbital_elements(r_true, v_true)
                print("Payload separation (stub) at t = %.1f s, %.1f x %.1f km orbit"
                      % (t, el["periapsis_km"], el["apoapsis_km"]))

        # --- rate-limit the attitude command through the handoff transition --
        # UPFG's converged command points where the *end* of the ascent wants the
        # thrust; without a limiter the vehicle would snap ~60 deg the instant
        # guidance goes closed-loop. Capping the command's turn rate to a real
        # vehicle pitch rate for the first HANDOFF_SLEW_S seconds spreads that
        # reorientation out (at falling dynamic pressure). Outside that window the
        # limiter is inactive -- UPFG's own turn rate is well within it.
        limit_slew = (phase == PH_UPFG and handoff_t is not None
                      and t - handoff_t < HANDOFF_SLEW_S)
        if target_cmd is None or not limit_slew:
            target_cmd = np.asarray(target_dir, dtype=float)
        else:
            gap = math.acos(float(np.clip(
                np.dot(_u(target_cmd), _u(target_dir)), -1.0, 1.0)))
            max_step = TARGET_SLEW_DPS * DEG * STEP_S
            axis = np.cross(target_cmd, target_dir)
            if gap > max_step and np.linalg.norm(axis) > 1e-12:
                target_cmd = _rot(_u(target_cmd), axis, max_step)
            else:
                target_cmd = np.asarray(target_dir, dtype=float)

        # --- command the autopilot --------------------------------------
        att.inputs.target_vec__inertial(_cv(target_cmd))
        att.inputs.quat_body_inertial(q_nav)
        att.inputs.omega_body_inertial__body(_cv(w_nav))

        # --- flow the commanded torque to the actuators ----------------
        # att runs inside exc.step(), so torque__body here is last step's
        # command (a 10 ms actuator lag). Pitch/yaw ride the engine gimbal:
        # a lateral thrust F at station L makes the body moment r x F =
        # (0, -L*Fz, L*Fy), so Fy = Mz/L and Fz = -My/L; LaunchVehicle then
        # clamps the vector to the gimbal cone. Roll rides the RCS node.
        # During the post-MECO coast there is no thrust, so the RCS holds
        # all three axes.
        m_cmd = _v3(att.outputs.torque__body())
        if throttle_frac > 0.0:
            axial = throttle_frac * thrust_n * thrust_dir_body   # carries the fixed misalignment
            gimbal = np.array([0.0, m_cmd[2] / ENGINE_STATION_M, -m_cmd[1] / ENGINE_STATION_M])
            rocket.inputs.thrust_command__body(_cv(axial + gimbal))
            rcs_roll_node.moment(_cv([m_cmd[0], 0.0, 0.0]))
        else:
            rocket.inputs.thrust_command__body(CartesianVector3([0.0, 0.0, 0.0]))
            rcs_roll_node.moment(_cv(m_cmd))

        # advance the latency pipeline: this step's throttle command is now the
        # newest thing in flight, the oldest reaches the engine on this step
        throttle_pipe.append(throttle_frac)
        del throttle_pipe[0]

        if exc.step():
            print("step error at t = %.2f s" % t)
            break

        # --- post-step bookkeeping --------------------------------------
        if throttle_frac > 0.0:
            gnc_mass -= throttle_frac * gnc_mdot * STEP_S   # flight-computer mass estimate

        q_pa = rocket.outputs.aero_dynamic_pressure()
        if q_pa > maxq_pa:
            maxq_pa, maxq_t = q_pa, t
            maxq_alt = rocket.outputs.altitude_detic()
            maxq_mach = rocket.outputs.aero_mach()
        # Angle of attack only loads the structure where there is real dynamic
        # pressure. Track the peak through the q > 5 kPa region (ascent + Max-Q,
        # where the pitch program holds it near zero) separately from the brief
        # large-AoA swing at the guidance-init handoff, which happens at
        # q < 2 kPa and is inconsequential for loads.
        aoa_deg = abs(rocket.outputs.aero_angle_of_attack()) / DEG
        if q_pa > 5000.0:
            max_aoa_deg = max(max_aoa_deg, aoa_deg)
            max_ssa_deg = max(max_ssa_deg, abs(rocket.outputs.aero_sideslip_angle()) / DEG)
        if handoff_t is not None and t - handoff_t < 20.0:
            handoff_aoa_peak_deg = max(handoff_aoa_peak_deg, aoa_deg)
        if phase in (PH_PITCH, PH_UPFG):
            max_point_err_deg = max(max_point_err_deg, att.outputs.pointing_error() / DEG)
            max_ctrl_torque_nm = max(max_ctrl_torque_nm,
                                     float(np.linalg.norm(_v3(att.outputs.torque__body()))))
        peak_nav_pos_err_m = max(peak_nav_pos_err_m,
                                 float(np.linalg.norm(_v3(nav.outputs.pos_stoch()) - _v3(rocket.outputs.pos_sc_pci()))))
        peak_nav_vel_err_mps = max(peak_nav_vel_err_mps,
                                   float(np.linalg.norm(_v3(nav.outputs.vel_stoch()) - _v3(rocket.outputs.vel_sc_pci()))))

        # stop shortly after separation (or if the vehicle came back down)
        if sep_t is not None and t - sep_t >= 2.0:
            break
        if liftoff_t is not None and rocket.outputs.altitude_detic() < -200.0:
            print("Vehicle returned to the surface at t = %.1f s -- ascent failed" % t)
            break

    # -----------------------------------------------------------------------
    #  SECTION 19 -- per-run summary + dispersion file
    # -----------------------------------------------------------------------
    # The DELIVERED orbit -- state at end of run (after the latency tail and the
    # settling coast), i.e. what the payload is actually left in.
    r_f = _v3(rocket.outputs.pos_sc_pci())
    v_f = _v3(rocket.outputs.vel_sc_pci())
    el = _orbital_elements(r_f, v_f)
    prop_rem = rocket.outputs.propellant_mass()
    reached_meco = meco_t is not None
    # Cutoff errors are the latched burnout values (state once the latency pipeline
    # flushed); only if that never latched do they fall back to the end state.
    if reached_meco and cutoff_el is not None:
        cutoff_radius = r_target + cutoff_r_err_m
        cutoff_r_err = cutoff_r_err_m
        cutoff_v_err = cutoff_v_err_mps
        cutoff_fpa = cutoff_el["fpa_deg"]
    else:
        cutoff_radius = float(np.linalg.norm(r_f))
        cutoff_r_err = float(np.linalg.norm(r_f) - r_target)
        cutoff_v_err = float(np.linalg.norm(v_f) - v_target)
        cutoff_fpa = el["fpa_deg"]
    # "reached a usable parking orbit": periapsis clear of the atmosphere and the
    # orbit within a small circularization burn of the target. Anything else that
    # made MECO is "marginal" (safe but eccentric enough to need a real trim).
    orbit_ok = bool(reached_meco and el["periapsis_km"] > 150.0
                    and abs(el["apoapsis_km"] - TARGET_ALT_M / 1e3) < 90.0)
    if not reached_meco:
        outcome = "no_meco"
    elif prop_rem <= 0.0:
        outcome = "propellant_depleted"
    elif orbit_ok:
        outcome = "orbit"
    else:
        outcome = "marginal"

    summary = dict(
        run=run_number,
        outcome=outcome,
        orbit_ok=orbit_ok,
        reached_meco=reached_meco,
        liftoff_time_s=liftoff_t,
        handoff_time_s=handoff_t,
        meco_time_s=meco_t,
        burn_time_s=(meco_t - liftoff_t) if (reached_meco and liftoff_t is not None) else None,
        separation_time_s=sep_t,
        propellant_remaining_kg=prop_rem,
        propellant_margin_frac=prop_rem / prop_mass,
        cutoff_radius_m=cutoff_radius,
        cutoff_radius_err_m=cutoff_r_err,
        cutoff_speed_mps=(v_target + cutoff_v_err),
        cutoff_speed_err_mps=cutoff_v_err,
        cutoff_fpa_deg=cutoff_fpa,
        apoapsis_km=el["apoapsis_km"],
        periapsis_km=el["periapsis_km"],
        sma_km=el["sma_km"],
        ecc=el["ecc"],
        inclination_deg=el["inc_deg"],
        raan_deg=el["raan_deg"],
        apoapsis_err_km=el["apoapsis_km"] - TARGET_ALT_M / 1e3,
        periapsis_err_km=el["periapsis_km"] - TARGET_ALT_M / 1e3,
        max_q_pa=maxq_pa,
        max_q_time_s=maxq_t,
        max_q_alt_km=maxq_alt / 1e3,
        max_q_mach=maxq_mach,
        max_aoa_deg=max_aoa_deg,                    # through q > 5 kPa (structural region)
        max_sideslip_deg=max_ssa_deg,
        handoff_aoa_peak_deg=handoff_aoa_peak_deg,  # guidance-init transient (low q)
        max_pointing_err_deg=max_point_err_deg,
        max_ctrl_torque_nm=max_ctrl_torque_nm,
        peak_nav_pos_err_m=peak_nav_pos_err_m,
        peak_nav_vel_err_mps=peak_nav_vel_err_mps,
        guidance_converged=upfg_converged_ever,
        dispersions=dict(
            dry_mass_kg=dry_mass,
            propellant_mass_kg=prop_mass,
            thrust_n=thrust_n,
            isp_s=isp_s,
            thrust_misalign_pitch_deg=mis_pitch_disp()(),
            thrust_misalign_yaw_deg=mis_yaw_disp()(),
            aero_axial_scale=aero_axial_scale,
            aero_cp_shift_m=aero_cp_shift,
            rail_azimuth_deg=az_disp()(),
            rail_elevation_deg=el_disp()(),
            pitch_rate_scale=pitch_rate_disp()(),
            rail_flex_seed=run_number,
        ),
    )
    with open(os.path.join(out_dir, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    exc.writeDispersionFile(os.path.join(out_dir, "dispersions.adoc"))

    print("Run %d: %s -- %.1f x %.1f km, incl %.2f deg, %.0f kg propellant margin"
          % (run_number, outcome, el["periapsis_km"], el["apoapsis_km"],
             el["inc_deg"], prop_rem))

    # Flush the CSV, then exit hard. Tearing this graph (SpicePlanet + the
    # launch-pad sub-models) down through the interpreter's GC trips a SWIG
    # proxy double-free that aborts with a non-zero code -- which would make
    # multirun.sh flag every run as failed even though the output is complete.
    # close() writes the buffered rows first. Same workaround as sounding_rocket.
    log.close()
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
