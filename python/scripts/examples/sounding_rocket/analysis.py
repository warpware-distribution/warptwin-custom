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
Sounding rocket flight analysis
-------------------------------
Reads results/sounding_rocket.csv, written by script.py, and builds a short
report of the flight: where the vehicle went, what the flight events were, the
forces that produced them, and how the mass and the recovery system behaved.

Everything here is derived from the log -- the events are found in the data
rather than assumed -- so it still reads correctly if the vehicle, the rail or
the recovery sequence in script.py is changed.

Numpy and matplotlib are the only dependencies, on purpose: a CsvLogger file is
a plain rectangular CSV, so pulling in pandas to read one buys nothing.

Run script.py first, then:
    python3 analysis.py

Author: Alex Reynolds <alex.reynolds@warpware.co>
"""
import base64
import io

import numpy as np
import matplotlib.pyplot as plt

from warptwinutils.AutoDocPy import AutoDocPy

RESULTS_DIR    = "results"
LOG_FILE       = RESULTS_DIR + "/sounding_rocket.csv"
EARTH_RADIUS_M = 6378137.0          # WGS-84 equatorial radius, for downrange
GRAVITY_M_S2   = 9.80665
LABEL_SPACING  = 0.02               # min gap between event labels, fraction of flight


def loadCsv(path):
    """Read a CsvLogger file into a dict of column name -> numpy array."""
    with open(path) as csv_file:
        names = csv_file.readline().strip().split(",")
    values = np.loadtxt(path, delimiter=",", skiprows=1)
    return {name: values[:, i] for i, name in enumerate(names)}


log = loadCsv(LOG_FILE)
time_s = log["time_s"]
altitude_m = log["altitude_m"]


def mag(name):
    """Magnitude of a logged 3-vector column set, e.g. mag('thrust_cmd_N')."""
    return np.linalg.norm([log["%s_%d" % (name, i)] for i in range(3)], axis=0)


def timeOf(mask):
    """Time of the first sample satisfying mask; NaN if it never does."""
    idx = np.flatnonzero(mask)
    return float(time_s[idx[0]]) if idx.size else float("nan")


# ---------------------------------------------------------------------------
# Derived quantities. Altitude is against the WGS-84 ellipsoid, so the pad sits
# at the first sample's altitude and the vehicle is down when it returns to it.
# Downrange is a flat-earth ground distance from the pad, good to well under a
# metre over the ~13 km this flight covers.
# ---------------------------------------------------------------------------
altitude_agl_m = altitude_m - altitude_m[0]
latitude_deg = np.degrees(log["latitude_rad"])
longitude_deg = np.degrees(log["longitude_rad"])
north_m = np.radians(latitude_deg - latitude_deg[0]) * EARTH_RADIUS_M
east_m = (np.radians(longitude_deg - longitude_deg[0]) * EARTH_RADIUS_M
          * np.cos(np.radians(latitude_deg[0])))
downrange_m = np.hypot(north_m, east_m)
vertical_speed_m_s = np.gradient(altitude_m, time_s)

thrust_N = mag("thrust_cmd_N")
drag_N = mag("aero_force_N")            # axial-dominated on an unguided body
chute_force_N = mag("drogue_force_N") + mag("main_force_N")

# Flight events, all recovered from the log
apogee_index = int(np.argmax(altitude_m))
EVENTS = [
    ("Ignition",       timeOf(thrust_N > 0.0)),
    ("Rail departure", timeOf(log["on_rail"] == 0)),
    ("MECO",           timeOf(log["propellant_kg"] <= 0.0)),
    ("Apogee",         float(time_s[apogee_index])),
    ("Drogue deploy",  timeOf(log["drogue_deployed"] > 0)),
    ("Main deploy",    timeOf(log["main_deployed"] > 0)),
    ("Touchdown",      float(time_s[-1])),
]
# Burn window used to zoom the mass plot; the whole flight if there was no burn
meco_s = dict(EVENTS)["MECO"]
boost_end_s = 2.0 * meco_s if np.isfinite(meco_s) else time_s[-1]


def markEvents(ax, window=None):
    """Drop a labelled vertical line on ax at each flight event inside window,
    which defaults to the whole flight -- an axes zoomed to part of the flight
    must pass its own, or it picks up lines and labels for events off the end of
    it and tight_layout cannot fit them. Every event in the window is drawn, but
    a label within LABEL_SPACING of the window of the last one is dropped rather
    than printed on top of it; the events table has the times of all of them."""
    t_start, t_end = window if window is not None else (time_s[0], time_s[-1])
    last_labeled_s = -np.inf
    for label, t_event in EVENTS:
        if not np.isfinite(t_event) or not t_start <= t_event <= t_end:
            continue
        ax.axvline(t_event, color="gray", linestyle="--", linewidth=0.8)
        if t_event - last_labeled_s < LABEL_SPACING * (t_end - t_start):
            continue
        ax.annotate(label, xy=(t_event, 0.98), xycoords=("data", "axes fraction"),
                    xytext=(3, 0), textcoords="offset points", rotation=90,
                    va="top", ha="left", fontsize=7, color="gray")
        last_labeled_s = t_event


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
plt.rcParams.update({"axes.grid": True, "grid.alpha": 0.3})

doc = AutoDocPy()
doc.title("Sounding Rocket Flight Analysis")
doc.author("Alex Reynolds", "alex.reynolds@warpware.co")
doc.file("sounding_rocket_analysis.adoc")
doc.addText("Single-stage 14 inch sounding rocket flown off a near-vertical rail "
            "and recovered under a drogue and main canopy. All values are taken "
            "from results/sounding_rocket.csv.\n\n")


def addTable(headers, rows):
    """Write a table to the doc from column headers and a list of row tuples."""
    doc.addTable([[str(row[i]) for row in rows] for i in range(len(headers))],
                 headers, [], True)


def addFigure(fig, name):
    """Save the figure to results/<name>.png AND embed it in the report as a
    base64 data URI. AutoDocPy.addMatPlotLib references figures by absolute path,
    which a browser reads as a root-relative URL and cannot load; a data URI
    makes the HTML self-contained -- it renders from file://, a web server, or
    after the results dir is moved."""
    fig.savefig("%s/%s.png" % (RESULTS_DIR, name), dpi=110)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    doc.addText('\n\n++++\n<img alt="%s" style="max-width:100%%" '
                'src="data:image/png;base64,%s">\n++++\n\n' % (name, b64))


doc.addPrimaryHeader("Flight Events")
addTable(["Event", "Time (s)", "Altitude AGL (km)"],
         [(label, round(t_event, 1),
           round(float(np.interp(t_event, time_s, altitude_agl_m)) / 1000.0, 2))
          for label, t_event in EVENTS])

doc.addPrimaryHeader("Flight Performance")
addTable(["Metric", "Value"], [
    ("Apogee AGL (km)", round(altitude_agl_m[apogee_index] / 1000.0, 2)),
    ("Downrange at landing (km)", round(downrange_m[-1] / 1000.0, 2)),
    ("Max Mach", round(float(log["mach"].max()), 2)),
    ("Max dynamic pressure (kPa)", round(float(log["q_pa"].max()) / 1000.0, 1)),
    ("Max drag (kN)", round(float(drag_N.max()) / 1000.0, 2)),
    ("Peak chute load (kN)", round(float(chute_force_N.max()) / 1000.0, 2)),
    ("Peak chute load (g, dry vehicle)",
     round(float(chute_force_N.max()) / (log["mass_kg"][-1] * GRAVITY_M_S2), 1)),
    ("Propellant burned (kg)", round(float(log["propellant_kg"].max()), 1)),
    ("Liftoff / burnout mass (kg)",
     "%.1f / %.1f" % (log["mass_kg"].max(), log["mass_kg"][-1])),
    ("Touchdown descent rate (m/s)", round(abs(float(vertical_speed_m_s[-1])), 1)),
])

# Trajectory: the profile in time, and the same flight as a range/altitude
# cross-section showing how far downrange the near-vertical rail puts it.
doc.addPrimaryHeader("Trajectory")
fig, (ax_alt, ax_prof) = plt.subplots(2, 1, figsize=(10, 8))
ax_alt.plot(time_s, altitude_agl_m / 1000.0, color="tab:blue")
markEvents(ax_alt)
ax_alt.set_xlabel("Time (s)")
ax_alt.set_ylabel("Altitude AGL (km)")
ax_alt.set_title("Altitude Profile")
ax_prof.plot(downrange_m / 1000.0, altitude_agl_m / 1000.0, color="tab:blue")
ax_prof.plot(downrange_m[-1] / 1000.0, 0.0, "rv", label="Landing")
ax_prof.set_xlabel("Downrange from pad (km)")
ax_prof.set_ylabel("Altitude AGL (km)")
ax_prof.set_title("Range / Altitude Cross-Section")
ax_prof.legend()
addFigure(fig, "trajectory")
plt.close(fig)

# Forces: the three that fly the vehicle. Thrust builds the trajectory, drag
# peaks going transonic and again on the way back down, and the canopies take
# over at apogee.
doc.addPrimaryHeader("Forces")
fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
for ax, (values, label, color) in zip(axes, [
        (thrust_N, "Thrust (kN)", "tab:red"),
        (drag_N, "Aerodynamic drag (kN)", "tab:orange"),
        (chute_force_N, "Chute force (kN)", "tab:green")]):
    ax.plot(time_s, values / 1000.0, color=color)
    ax.set_ylabel(label)
    markEvents(ax)
axes[-1].set_xlabel("Time (s)")
axes[0].set_title("Thrust, Drag and Recovery Loads")
addFigure(fig, "forces")
plt.close(fig)

# Mass and vertical speed: the burn drains the tank in one straight line, and
# the two canopies each show up as a step down in descent rate.
doc.addPrimaryHeader("Mass and Vertical Speed")
fig, (ax_mass, ax_vel) = plt.subplots(2, 1, figsize=(10, 8))
ax_mass.plot(time_s, log["mass_kg"], label="Total mass")
ax_mass.plot(time_s, log["propellant_kg"], label="Propellant")
ax_mass.set_xlim(0.0, min(boost_end_s, time_s[-1]))   # zoomed to the burn;
ax_mass.set_xlabel("Time (s)")                        # the rest is dry mass
ax_mass.set_ylabel("Mass (kg)")
ax_mass.set_title("Mass Through Boost, and Vertical Speed Over the Full Flight")
ax_mass.legend()
markEvents(ax_mass, (0.0, boost_end_s))
ax_vel.plot(time_s, vertical_speed_m_s, color="tab:purple")
ax_vel.axhline(0.0, color="gray", linewidth=0.8)
ax_vel.set_xlabel("Time (s)")
ax_vel.set_ylabel("Vertical speed (m/s)")
markEvents(ax_vel)
addFigure(fig, "mass_velocity")
plt.close(fig)

# Flight environment: Mach and dynamic pressure. Max q lands in the transonic
# region on the way up; the descent produces a second, much smaller peak as the
# vehicle falls back into thicker air.
doc.addPrimaryHeader("Flight Environment")
fig, ax_mach = plt.subplots(figsize=(10, 5))
ax_q = ax_mach.twinx()
traces = (ax_mach.plot(time_s, log["mach"], color="tab:blue", label="Mach")
          + ax_q.plot(time_s, log["q_pa"] / 1000.0, color="tab:orange",
                      label="Dynamic pressure"))
ax_mach.set_xlabel("Time (s)")
ax_mach.set_ylabel("Mach")
ax_mach.set_title("Mach and Dynamic Pressure")
ax_mach.legend(traces, [trace.get_label() for trace in traces], loc="upper right")
ax_q.set_ylabel("Dynamic pressure (kPa)")
ax_q.grid(False)
markEvents(ax_mach)
addFigure(fig, "environment")
plt.close(fig)

doc.closeGenerateDoc()
print("Report written to %s/sounding_rocket_analysis.html" % RESULTS_DIR)
