"""
Power Beaming Analysis
----------------------
Standalone analysis for the GEO power-beaming scenario:
  1. Receiving spacecraft operates nominally on its solar array
  2. At t = SOLAR_ARRAY_DROPOUT_TIME, the array fails — generation drops to 0
  3. The battery discharges as the load continues to draw power
  4. At t = POWER_BEAM_START_TIME, the beaming spacecraft begins delivering
     ~3 kW of power via the power link, restoring positive power
  5. The receiving spacecraft recovers — battery starts charging back up

This script reads <out_dir>/states.h5 (written by the sim) and produces a
styled HTML report telling that story with annotated plots.

Usage:
  python3 power_beaming_analysis.py [<out_dir>]

Default out_dir is "results" (same as the sim's default).
"""

import os
import sys
import subprocess
import argparse

import numpy as np
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from warptwinutils.AutoDocPy import AutoDocPy


# ── Scenario constants (must match the sim) ─────────────────────────────────
SOLAR_ARRAY_DROPOUT_TIME = 1000.0      # s
POWER_BEAM_START_TIME    = 3500.0      # s
BEAM_POWER_KW            = 10.0         # kW
BATTERY_CAPACITY_WH      = 7000.0
PEAK_VOLTAGE_V           = 50.0
NOMINAL_PANEL_AREA_M2    = 40.0
NOMINAL_LOAD_W           = 7000.0


# ── WarpWare-aligned plot style ─────────────────────────────────────────────
WARP        = "#bc00c9"
BG          = "#06040e"
BG_PANEL    = "#0f0a1c"
TEXT        = "#f0ecff"
TEXT_DIM    = "#a89fc8"
GRID        = "#2a1f3d"
PALETTE     = ["#bc00c9", "#00d4ff", "#ffb800", "#39ff14",
               "#ff5577", "#9d6bff", "#ff8c42", "#52e1c4"]

plt.rcParams.update({
    "figure.facecolor":   BG,
    "axes.facecolor":     BG_PANEL,
    "axes.edgecolor":     GRID,
    "axes.labelcolor":    TEXT,
    "axes.titlecolor":    TEXT,
    "axes.titlesize":     12,
    "axes.labelsize":     10,
    "axes.grid":          True,
    "grid.color":         GRID,
    "grid.linestyle":     "-",
    "grid.alpha":         0.6,
    "xtick.color":        TEXT,
    "ytick.color":        TEXT,
    "xtick.labelsize":    9,
    "ytick.labelsize":    9,
    "text.color":         TEXT,
    "legend.facecolor":   BG_PANEL,
    "legend.edgecolor":   GRID,
    "legend.fontsize":    9,
    "legend.labelcolor":  TEXT,
    "font.family":        "sans-serif",
    "font.sans-serif":    ["Lato", "DejaVu Sans", "Arial"],
    "savefig.facecolor":  BG,
    "savefig.dpi":        140,
    "savefig.bbox":       "tight",
})


# ── Args / paths ────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Power beaming scenario analysis")
parser.add_argument("out_dir", nargs="?", default="results",
                    help="Directory containing states.h5 (default: 'results')")
args = parser.parse_args()

out_path     = os.path.abspath(args.out_dir)
results_dir  = os.path.join(out_path, "results")
os.makedirs(results_dir, exist_ok=True)
h5_path      = os.path.join(out_path, "states.h5")
if not os.path.exists(h5_path):
    print(f"ERROR: expected {h5_path}, found nothing.", file=sys.stderr)
    sys.exit(1)


# ── Load HDF5 ───────────────────────────────────────────────────────────────
with h5py.File(h5_path, "r") as f:
    sim_time     = np.asarray(f["time"][:]).flatten()
    beam_pos     = np.asarray(f["beam_eci_pos"][:])
    beam_vel     = np.asarray(f["beam_eci_vel"][:])
    receive_pos  = np.asarray(f["receive_eci_pos"][:])
    receive_vel  = np.asarray(f["receive_eci_vel"][:])
    power_gen_w  = np.asarray(f["power_generation_w"][:]).flatten()
    power_draw_w = np.asarray(f["power_draw_w"][:]).flatten()
    dod          = np.asarray(f["depth_of_discharge"][:]).flatten()
    sys_voltage  = np.asarray(f["system_voltage"][:]).flatten()

# Make sure the position arrays are 2D (N, 3)
if beam_pos.ndim == 3:
    beam_pos = beam_pos.reshape(beam_pos.shape[0], 3)
if receive_pos.ndim == 3:
    receive_pos = receive_pos.reshape(receive_pos.shape[0], 3)
if beam_vel.ndim == 3:
    beam_vel = beam_vel.reshape(beam_vel.shape[0], 3)
if receive_vel.ndim == 3:
    receive_vel = receive_vel.reshape(receive_vel.shape[0], 3)

t_s         = sim_time - float(sim_time[0])
sim_dur_s   = float(t_s[-1]) if t_s.size else 0.0
sample_dt_s = float(np.median(np.diff(t_s))) if t_s.size >= 2 else 1.0

# Derived series
soc         = 1.0 - dod                         # state of charge in [0, 1]
net_power_w = power_gen_w - power_draw_w
separation  = np.linalg.norm(beam_pos - receive_pos, axis=1)


# ── Phase boundaries (sample indices) ──────────────────────────────────────
i_dropout  = int(np.searchsorted(t_s, SOLAR_ARRAY_DROPOUT_TIME))
i_beam_on  = int(np.searchsorted(t_s, POWER_BEAM_START_TIME))
i_dropout  = min(i_dropout, len(t_s) - 1)
i_beam_on  = min(i_beam_on, len(t_s) - 1)

# Phase slices: [start_idx, end_idx) — half-open intervals
phase_nominal  = slice(0,         i_dropout)
phase_decline  = slice(i_dropout, i_beam_on)
phase_recovery = slice(i_beam_on, len(t_s))


def _phase_stats(label, idx_slice):
    """Compute summary stats for a phase. Returns dict for the report."""
    if t_s[idx_slice].size == 0:
        return None
    seg_t   = t_s[idx_slice]
    seg_gen = power_gen_w[idx_slice]
    seg_drw = power_draw_w[idx_slice]
    seg_net = net_power_w[idx_slice]
    seg_soc = soc[idx_slice]
    return {
        "label":          label,
        "duration_s":     float(seg_t[-1] - seg_t[0]) + sample_dt_s,
        "mean_gen_w":     float(np.mean(seg_gen)),
        "mean_draw_w":    float(np.mean(seg_drw)),
        "mean_net_w":     float(np.mean(seg_net)),
        "soc_start_pct":  float(seg_soc[0]  * 100.0),
        "soc_end_pct":    float(seg_soc[-1] * 100.0),
        "soc_min_pct":    float(np.min(seg_soc) * 100.0),
        "energy_in_wh":   float(np.sum(seg_gen) * sample_dt_s / 3600.0),
        "energy_out_wh":  float(np.sum(seg_drw) * sample_dt_s / 3600.0),
    }


stats_nominal  = _phase_stats("Nominal (solar)",   phase_nominal)
stats_decline  = _phase_stats("Decline (no power)", phase_decline)
stats_recovery = _phase_stats("Recovery (beamed)", phase_recovery)

# Mission-wide critical-event metrics
soc_min_idx = int(np.argmin(soc))
soc_min_pct = float(soc[soc_min_idx] * 100.0)
soc_min_t   = float(t_s[soc_min_idx])

# Time from dropout to minimum SoC (how long the battery decline lasted)
decline_time = soc_min_t - SOLAR_ARRAY_DROPOUT_TIME
# Margin: how much SoC was left at the worst moment
soc_margin = soc_min_pct  # already a margin from 0%

# Verdict
if soc_min_pct < 5.0:
    verdict = ("CRITICAL — battery reached <5% SoC before recovery. "
               "Real mission would have suffered safe-mode entry or "
               "permanent battery damage. Beaming arrived too late.")
elif soc_min_pct < 20.0:
    verdict = ("MARGINAL — battery dipped below 20% SoC, the typical "
               "Li-ion safe-discharge floor. Mission survived but with "
               "no margin for delays in beam initiation.")
elif soc_min_pct < 50.0:
    verdict = ("ACCEPTABLE — battery cycled deeply but stayed above the "
               "20% safe floor. Beam-rescue strategy works for this "
               "configuration with reasonable margin.")
else:
    verdict = ("ROBUST — battery stayed above 50% throughout the dropout. "
               "Beam-rescue strategy has substantial margin and could "
               "tolerate longer dropouts before becoming critical.")


# ── Plot helpers ───────────────────────────────────────────────────────────
def annotate_events(ax, label_y_frac=0.92):
    """Draw vertical lines for the two scenario events, with labels."""
    ymin, ymax = ax.get_ylim()
    y_label = ymin + (ymax - ymin) * label_y_frac
    ax.axvline(SOLAR_ARRAY_DROPOUT_TIME, color=PALETTE[4], linewidth=1.4,
               linestyle="--", alpha=0.85, zorder=3)
    ax.axvline(POWER_BEAM_START_TIME, color=PALETTE[3], linewidth=1.4,
               linestyle="--", alpha=0.85, zorder=3)
    ax.text(SOLAR_ARRAY_DROPOUT_TIME + sim_dur_s * 0.005, y_label,
            "Solar array dropout",
            color=PALETTE[4], fontsize=8, va="center",
            bbox=dict(facecolor=BG_PANEL, edgecolor=PALETTE[4],
                      boxstyle="round,pad=0.3", alpha=0.9))
    ax.text(POWER_BEAM_START_TIME + sim_dur_s * 0.005, y_label,
            "Beam start",
            color=PALETTE[3], fontsize=8, va="center",
            bbox=dict(facecolor=BG_PANEL, edgecolor=PALETTE[3],
                      boxstyle="round,pad=0.3", alpha=0.9))


def shade_phases(ax):
    """Shade the three phases lightly."""
    ax.axvspan(0, SOLAR_ARRAY_DROPOUT_TIME,
               color=PALETTE[1], alpha=0.06, zorder=0)
    ax.axvspan(SOLAR_ARRAY_DROPOUT_TIME, POWER_BEAM_START_TIME,
               color=PALETTE[4], alpha=0.10, zorder=0)
    ax.axvspan(POWER_BEAM_START_TIME, sim_dur_s,
               color=PALETTE[3], alpha=0.06, zorder=0)


def save(name):
    fname = f"{name}.png"
    plt.savefig(os.path.join(results_dir, fname))
    plt.close()
    return fname


figpaths = {}

# ── Plot 1: Power generation vs draw, with event markers ────────────────────
fig, ax = plt.subplots(figsize=(11, 5.5))
shade_phases(ax)
ax.plot(t_s, power_gen_w,  color=PALETTE[1], linewidth=1.5,
        label="Generation")
ax.plot(t_s, power_draw_w, color=PALETTE[2], linewidth=1.5,
        label="Draw", alpha=0.95)
annotate_events(ax)
ax.set_xlabel("Time since sim start (s)")
ax.set_ylabel("Power (W)")
ax.set_title("Power generation vs draw — scenario timeline")
ax.legend(loc="center right")
ax.set_xlim(0, sim_dur_s)
figpaths["power_gen_vs_draw"] = save("power_gen_vs_draw")

# ── Plot 2: Net power ───────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(11, 4.5))
shade_phases(ax)
ax.fill_between(t_s, 0, net_power_w, where=(net_power_w >= 0),
                color=PALETTE[3], alpha=0.55, linewidth=0,
                label="Net positive (charging)")
ax.fill_between(t_s, 0, net_power_w, where=(net_power_w < 0),
                color=PALETTE[4], alpha=0.55, linewidth=0,
                label="Net negative (discharging)")
ax.plot(t_s, net_power_w, color=TEXT, linewidth=0.8)
ax.axhline(0, color=TEXT_DIM, linewidth=1)
annotate_events(ax)
ax.set_xlabel("Time since sim start (s)")
ax.set_ylabel("Net power (W)")
ax.set_title("Net power margin")
ax.legend(loc="lower right")
ax.set_xlim(0, sim_dur_s)
figpaths["net_power"] = save("net_power")

# ── Plot 3: Battery state of charge ─────────────────────────────────────────
fig, ax = plt.subplots(figsize=(11, 5))
shade_phases(ax)
ax.plot(t_s, soc * 100.0, color=WARP, linewidth=1.8)
ax.scatter([soc_min_t], [soc_min_pct], s=80, color=PALETTE[4],
           zorder=5, edgecolor="white", linewidth=1.4,
           label=f"Min SoC: {soc_min_pct:.1f}% @ t={soc_min_t:.0f}s")
ax.axhline(soc_min_pct, color=PALETTE[4], linestyle=":", linewidth=0.8,
           alpha=0.6)
ax.axhline(20.0, color=PALETTE[2], linestyle="--", linewidth=0.8,
           alpha=0.7, label="20% floor (typical Li-ion safe)")
annotate_events(ax)
ax.set_xlabel("Time since sim start (s)")
ax.set_ylabel("State of charge (%)")
ax.set_title("Battery state of charge — closest approach to mission failure")
ax.set_ylim(0, 105)
ax.legend(loc="center right")
ax.set_xlim(0, sim_dur_s)
figpaths["battery_soc"] = save("battery_soc")

# ── Plot 4: System voltage ──────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(11, 4))
shade_phases(ax)
ax.plot(t_s, sys_voltage, color=PALETTE[5], linewidth=1.4)
ax.axhline(PEAK_VOLTAGE_V, color=PALETTE[2], linestyle="--", linewidth=0.8,
           alpha=0.7, label=f"Peak ({PEAK_VOLTAGE_V:.1f} V)")
annotate_events(ax)
ax.set_xlabel("Time since sim start (s)")
ax.set_ylabel("Bus voltage (V)")
ax.set_title("System voltage")
ax.legend(loc="lower right")
ax.set_xlim(0, sim_dur_s)
figpaths["system_voltage"] = save("system_voltage")

# ── Plot 5: Spacecraft separation ───────────────────────────────────────────
fig, ax = plt.subplots(figsize=(11, 4.5))
shade_phases(ax)
ax.plot(t_s, separation / 1000.0, color=PALETTE[7], linewidth=1.6)
annotate_events(ax)
ax.set_xlabel("Time since sim start (s)")
ax.set_ylabel("Separation (km)")
ax.set_title("Beaming sat ↔ receiving sat distance")
ax.set_xlim(0, sim_dur_s)
figpaths["separation"] = save("separation")

# ── Plot 6: Both orbits in 3D ───────────────────────────────────────────────
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
fig = plt.figure(figsize=(9, 8))
ax = fig.add_subplot(111, projection="3d")
ax.set_facecolor(BG_PANEL)
fig.patch.set_facecolor(BG)

# Earth wireframe (in km)
R_EARTH_KM = 6378.137
u_grid = np.linspace(0, 2 * np.pi, 30)
v_grid = np.linspace(0, np.pi, 20)
xs = R_EARTH_KM * np.outer(np.cos(u_grid), np.sin(v_grid))
ys = R_EARTH_KM * np.outer(np.sin(u_grid), np.sin(v_grid))
zs = R_EARTH_KM * np.outer(np.ones_like(u_grid), np.cos(v_grid))
ax.plot_wireframe(xs, ys, zs, color="#3b6ea5", alpha=0.25, linewidth=0.4)

beam_km    = beam_pos    / 1000.0
receive_km = receive_pos / 1000.0
ax.plot(beam_km[:, 0], beam_km[:, 1], beam_km[:, 2],
        color=PALETTE[1], linewidth=1.4, label="Beaming sat")
ax.plot(receive_km[:, 0], receive_km[:, 1], receive_km[:, 2],
        color=WARP, linewidth=1.4, label="Receiving sat")

# Mark beam-on event positions
ax.scatter([beam_km[i_beam_on, 0]], [beam_km[i_beam_on, 1]],
           [beam_km[i_beam_on, 2]], s=80, color=PALETTE[3],
           edgecolor="white", linewidth=1.2, label="Beaming sat at beam-on",
           zorder=5)
ax.scatter([receive_km[i_beam_on, 0]], [receive_km[i_beam_on, 1]],
           [receive_km[i_beam_on, 2]], s=80, color=PALETTE[3],
           edgecolor="white", linewidth=1.2, marker="^",
           label="Receiving sat at beam-on", zorder=5)

ax.set_xlabel("X (km)", color=TEXT)
ax.set_ylabel("Y (km)", color=TEXT)
ax.set_zlabel("Z (km)", color=TEXT)
ax.set_title("GEO orbits — beaming and receiving spacecraft")
ax.tick_params(colors=TEXT)
ax.legend(loc="upper left")
max_range = max(np.max(np.abs(beam_km)), np.max(np.abs(receive_km)))
ax.set_xlim([-max_range, max_range])
ax.set_ylim([-max_range, max_range])
ax.set_zlim([-max_range, max_range])
figpaths["orbits_3d"] = save("orbits_3d")


# ── AsciiDoc helpers ───────────────────────────────────────────────────────
def _write_kv_table(doc, header, rows):
    """Tiny helper to emit an AsciiDoc table via AutoDocPy."""
    try:
        import pandas as pd
        df = pd.DataFrame(rows, columns=header)
        doc.addDataFrame(df)
        return
    except Exception:
        pass
    lines = ['[cols="' + ",".join(["1"] * len(header)) + '", options="header"]',
             "|==="]
    lines.append("| " + " | ".join(header))
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row))
    lines.append("|===")
    doc.addText("\n".join(lines))


# ── Build the document ─────────────────────────────────────────────────────
doc = AutoDocPy()
doc.title("Power Beaming Scenario Analysis")
doc.author("WarpTwin", "agent@warpware.co")
doc.file(os.path.join(out_path, "analysis.adoc"))

# ── Overview ────────────────────────────────────────────────────────────────
doc.addPrimaryHeader("Overview")
doc.addText(
    "This analysis evaluates a power-beaming rescue scenario between two "
    "GEO spacecraft. The receiving spacecraft suffers a solar-array "
    "failure mid-mission and depends on a companion spacecraft to "
    "deliver power via an inter-satellite link until the situation is "
    "resolved. The central question: did the rescue arrive in time, and "
    "with how much margin?"
)

doc.addSecondaryHeader("Verdict")
doc.addText(f"*{verdict}*")

doc.addSecondaryHeader("Scenario")
doc.addText(
    f"Two spacecraft in nearly co-located GEO positions (60° apart in "
    f"true anomaly) operate nominally for the first {SOLAR_ARRAY_DROPOUT_TIME:.0f} "
    f"seconds. At t = {SOLAR_ARRAY_DROPOUT_TIME:.0f} s the receiving "
    f"spacecraft's solar array fails — generation drops to zero while "
    f"its load continues drawing {NOMINAL_LOAD_W:.0f} W. The battery "
    f"begins discharging. At t = {POWER_BEAM_START_TIME:.0f} s the "
    f"beaming spacecraft initiates a {BEAM_POWER_KW:.1f} kW power link, "
    f"restoring positive net power and allowing the battery to recharge."
)

doc.addSecondaryHeader("Methodology")
doc.addText(
    f"State is logged every {sample_dt_s:.0f} simulated seconds. Power "
    "generation is computed by WarpTwin's SolarPanelModel from "
    "panel orientation, area, and Earth-occulted sun-spacecraft "
    "geometry. Battery state is tracked by SimpleBatterySystem with "
    "state of charge derived as (1 − depth_of_discharge). The power "
    "link between spacecraft is geometric only — visibility is computed "
    "but no link physics (atmospheric attenuation, beam steering "
    "accuracy, conversion efficiency) are modeled."
)

doc.addSecondaryHeader("Modeling Assumptions")
doc.addText(
    "Pure two-body orbit propagation (no J2/J3 in this scenario over "
    "this short duration). Spacecraft attitude is not simulated — both "
    "panels track the sun ideally. The beam delivery is instantaneous "
    "(no ramp-up) and lossless (3 kW transmitted = 3 kW received). "
    "Battery model uses a simple constant-efficiency assumption; "
    "temperature, cell imbalance, and cycle aging are not modeled. "
    "These approximations are appropriate for first-order feasibility "
    "studies of beaming concepts, not detailed flight design."
)

# ── Configuration ──────────────────────────────────────────────────────────
doc.addPrimaryHeader("Configuration")

config_rows = [
    ["Sim duration",                f"{sim_dur_s:.0f} s"],
    ["Sample interval",             f"{sample_dt_s:.0f} s"],
    ["Solar array dropout time",    f"{SOLAR_ARRAY_DROPOUT_TIME:.0f} s"],
    ["Beam initiation time",        f"{POWER_BEAM_START_TIME:.0f} s"],
    ["Beam power",                  f"{BEAM_POWER_KW:.1f} kW"],
    ["Solar panel area (nominal)",  f"{NOMINAL_PANEL_AREA_M2:.1f} m²"],
    ["Receiving sat load",          f"{NOMINAL_LOAD_W:.0f} W"],
    ["Battery capacity",            f"{BATTERY_CAPACITY_WH:.0f} Wh"],
    ["Peak bus voltage",            f"{PEAK_VOLTAGE_V:.1f} V"],
    ["Initial separation",
     f"{separation[0]/1000:.1f} km (60° true anomaly offset in GEO)"],
]
_write_kv_table(doc, ["Parameter", "Value"], config_rows)

# ── Critical events ───────────────────────────────────────────────────────
doc.addPrimaryHeader("Critical-Event Summary")
doc.addText(
    "The headline numbers from this scenario — the closest approach to "
    "mission failure, and the timing of the beam-rescue."
)

dropout_to_min  = soc_min_t - SOLAR_ARRAY_DROPOUT_TIME
beam_to_min     = soc_min_t - POWER_BEAM_START_TIME
soc_at_dropout  = float(soc[i_dropout] * 100.0)
soc_at_beam_on  = float(soc[i_beam_on] * 100.0)

events_rows = [
    ["SoC at dropout",
     f"{soc_at_dropout:.1f}% (battery state when array failed)"],
    ["SoC at beam initiation",
     f"{soc_at_beam_on:.1f}% (battery state when rescue began)"],
    ["Minimum SoC reached",
     f"{soc_min_pct:.1f}% @ t = {soc_min_t:.0f} s"],
    ["Time from dropout to min SoC",
     f"{dropout_to_min:.0f} s"],
    ["Time from beam-start to min SoC",
     f"{beam_to_min:+.0f} s "
     f"({'before' if beam_to_min < 0 else 'after'} beam initiation)"],
    ["Margin above 0% SoC",
     f"{soc_margin:.1f} percentage points"],
    ["Margin above 20% (Li-ion safe floor)",
     f"{soc_margin - 20.0:+.1f} percentage points"],
]
_write_kv_table(doc, ["Metric", "Value"], events_rows)

# ── Phase analysis ────────────────────────────────────────────────────────
doc.addPrimaryHeader("Phase-by-Phase Analysis")
doc.addText(
    "The scenario divides naturally into three phases. Aggregate "
    "behavior in each is summarized below."
)

phase_table = [["Phase", "Duration (s)", "Mean gen (W)",
                "Mean draw (W)", "Mean net (W)",
                "SoC start → end (%)", "Energy in (Wh)", "Energy out (Wh)"]]
for ps in (stats_nominal, stats_decline, stats_recovery):
    if ps is None:
        continue
    phase_table.append([
        ps["label"],
        f"{ps['duration_s']:.0f}",
        f"{ps['mean_gen_w']:.0f}",
        f"{ps['mean_draw_w']:.0f}",
        f"{ps['mean_net_w']:+.0f}",
        f"{ps['soc_start_pct']:.1f} → {ps['soc_end_pct']:.1f}",
        f"{ps['energy_in_wh']:.1f}",
        f"{ps['energy_out_wh']:.1f}",
    ])
_write_kv_table(doc, phase_table[0], phase_table[1:])

doc.addSecondaryHeader("Phase 1: Nominal operation")
if stats_nominal:
    doc.addText(
        f"For the first {stats_nominal['duration_s']:.0f} seconds, the "
        f"receiving spacecraft generates {stats_nominal['mean_gen_w']:.0f} W "
        f"on average from its solar array against a "
        f"{stats_nominal['mean_draw_w']:.0f} W load. Net power averages "
        f"{stats_nominal['mean_net_w']:+.0f} W — the battery is "
        f"{'topping off' if stats_nominal['mean_net_w'] > 0 else 'slowly discharging'}. "
        f"This is the baseline state from which the dropout occurs."
    )

doc.addSecondaryHeader("Phase 2: Solar array failure")
if stats_decline:
    doc.addText(
        f"At t = {SOLAR_ARRAY_DROPOUT_TIME:.0f} s the array fails. "
        f"Generation collapses to {stats_decline['mean_gen_w']:.0f} W "
        f"while load continues drawing {stats_decline['mean_draw_w']:.0f} W "
        f"— a steady {stats_decline['mean_net_w']:+.0f} W deficit. The "
        f"battery state of charge drops from "
        f"{stats_decline['soc_start_pct']:.1f}% to "
        f"{stats_decline['soc_end_pct']:.1f}% over "
        f"{stats_decline['duration_s']:.0f} seconds. Total energy drawn "
        f"from the battery during this phase: "
        f"{stats_decline['energy_out_wh']:.1f} Wh."
    )

doc.addSecondaryHeader("Phase 3: Beam-rescue and recovery")
if stats_recovery:
    doc.addText(
        f"At t = {POWER_BEAM_START_TIME:.0f} s the beaming spacecraft "
        f"initiates a {BEAM_POWER_KW:.1f} kW link. Generation jumps to "
        f"{stats_recovery['mean_gen_w']:.0f} W, exceeding the load — net "
        f"power becomes {stats_recovery['mean_net_w']:+.0f} W and the "
        f"battery starts charging. Over the remaining "
        f"{stats_recovery['duration_s']:.0f} seconds, SoC recovers from "
        f"{stats_recovery['soc_start_pct']:.1f}% to "
        f"{stats_recovery['soc_end_pct']:.1f}%."
    )

# ── Time-series plots ────────────────────────────────────────────────────
doc.addPrimaryHeader("Power Time Series")
doc.addText(
    "Generation and draw plotted with the two scenario events marked. "
    "The colored background bands distinguish the three phases: "
    "nominal (blue), decline (red), recovery (green)."
)
doc.addImage(figpaths["power_gen_vs_draw"], "Power generation vs draw")

doc.addText(
    "Net power. Negative regions show the battery supplying the bus; "
    "positive regions show the battery charging. The transition from "
    "negative to positive is the moment of rescue."
)
doc.addImage(figpaths["net_power"], "Net power margin")

# ── Battery ──────────────────────────────────────────────────────────────
doc.addPrimaryHeader("Battery State")
doc.addText(
    "Battery state of charge is the headline metric for this scenario. "
    "The minimum-SoC point shows how close the receiving spacecraft "
    "came to mission failure. The 20% reference line is the typical "
    "Li-ion safe-discharge floor — operating below it accelerates "
    "battery aging and risks safe-mode entry."
)
doc.addImage(figpaths["battery_soc"], "Battery state of charge")

doc.addText(
    "Bus voltage tracks state of charge — it's an alternative read on "
    "the same story. Sustained voltage drops below the load's minimum "
    "operating point would cause subsystem brownouts."
)
doc.addImage(figpaths["system_voltage"], "System voltage")

# ── Spacecraft geometry ──────────────────────────────────────────────────
doc.addPrimaryHeader("Spacecraft Geometry")
doc.addText(
    "Power beaming requires the two spacecraft to be in line-of-sight, "
    "and the link is more efficient when they're closer (inverse-square "
    "for any directional beam). Their relative geometry over the "
    "scenario:"
)
doc.addImage(figpaths["separation"], "Inter-satellite separation")

doc.addText(
    "Both spacecraft orbits in 3D, with positions at the moment of beam "
    "initiation marked. Both orbits are essentially identical (GEO at "
    "the same altitude and inclination); the spacecraft are simply "
    "phased apart by 60° in true anomaly, which puts them about "
    f"{separation[0]/1000:.0f} km apart."
)
doc.addImage(figpaths["orbits_3d"], "Orbits in 3D")

# ── Render ──────────────────────────────────────────────────────────────
doc.closeDisplayDoc()