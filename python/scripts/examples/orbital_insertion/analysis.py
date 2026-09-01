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
Monte Carlo analysis / report for the SSTO orbital-insertion example
===================================================================
Reads every ``<results>/run_*/summary.json`` written by ``script.py`` (and,
where present, the matching ``ascent.csv`` trajectory), and produces an HTML
report covering:

  * mission outcome breakdown and insertion success rate
  * insertion-accuracy statistics (periapsis / apoapsis / inclination / cutoff
    speed, radius and flight-path-angle errors) with 2-sigma bounds
  * distributions (histogram + PDF/CDF) of the quantities that matter for a
    launch: insertion box, propellant margin, Max-Q, angle of attack through
    Max-Q, peak attitude-tracking error, peak navigation error
  * a periapsis / apoapsis insertion scatter against the target box
  * dispersion-sensitivity scatters -- insertion periapsis vs each input
    dispersion -- so the drivers of the insertion spread are visible
  * Monte Carlo trajectory overlays (altitude, dynamic pressure, Mach, UPFG
    time-to-go, throttle and attitude error vs time), reference run in bold

Usage:
    python3 analysis.py [results_dir]      # default: ./results

Author: James Tabony <james.tabony@warpware.co>
"""

import base64
import glob
import io
import json
import math
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS_DIR = sys.argv[1] if len(sys.argv) > 1 else "results"
DOC_NAME = "orbital_insertion_mc_report.adoc"
FIG_DIR = os.path.join(RESULTS_DIR, "figures")

TARGET_ALT_KM = 200.0
R_EARTH_KM = 6378.137

# quantities to profile as distributions: (summary key, label, unit, target line)
DISTRIBUTIONS = [
    ("periapsis_km", "Insertion periapsis", "km", TARGET_ALT_KM),
    ("apoapsis_km", "Insertion apoapsis", "km", TARGET_ALT_KM),
    ("inclination_deg", "Insertion inclination", "deg", None),
    ("cutoff_speed_err_mps", "Cutoff speed error", "m/s", 0.0),
    ("cutoff_radius_err_m", "Cutoff radius error", "m", 0.0),
    ("cutoff_fpa_deg", "Cutoff flight-path angle", "deg", 0.0),
    ("burn_time_s", "Main-engine burn time", "s", None),
    ("propellant_remaining_kg", "Propellant margin at MECO", "kg", 0.0),
    ("max_q_pa", "Max dynamic pressure", "Pa", None),
    ("max_aoa_deg", "Max angle of attack through Max-Q", "deg", None),
    ("max_pointing_err_deg", "Peak attitude-tracking error", "deg", None),
    ("peak_nav_pos_err_m", "Peak navigation position error", "m", None),
]

# dispersion inputs to test insertion sensitivity against
DISPERSION_KEYS = [
    ("thrust_n", "Engine thrust", "N"),
    ("isp_s", "Engine Isp", "s"),
    ("dry_mass_kg", "Dry mass", "kg"),
    ("propellant_mass_kg", "Propellant load", "kg"),
    ("aero_axial_scale", "Axial-drag scale", "-"),
    ("thrust_misalign_pitch_deg", "Thrust misalign (pitch)", "deg"),
    ("rail_azimuth_deg", "Pad azimuth", "deg"),
    ("pitch_rate_scale", "Pitch-rate scale", "-"),
]


# ---------------------------------------------------------------------------
def load_summaries(path):
    rows = []
    for f in sorted(glob.glob(os.path.join(path, "run_*", "summary.json")),
                    key=lambda p: int(p.split("run_")[1].split(os.sep)[0])):
        with open(f) as fh:
            s = json.load(fh)
        flat = {k: v for k, v in s.items() if k != "dispersions"}
        for k, v in s.get("dispersions", {}).items():
            flat["disp_" + k] = v
        rows.append(flat)
    if not rows:
        raise SystemExit("No run_*/summary.json found under %r -- run the Monte "
                         "Carlo first (./multirun.sh -f script.py -n 200)." % path)
    return pd.DataFrame(rows).sort_values("run").reset_index(drop=True)


def load_trajectories(path, max_runs=120):
    dfs = []
    files = sorted(glob.glob(os.path.join(path, "run_*", "ascent.csv")),
                   key=lambda p: int(p.split("run_")[1].split(os.sep)[0]))
    for f in files[:max_runs]:
        try:
            dfs.append((int(f.split("run_")[1].split(os.sep)[0]), pd.read_csv(f)))
        except Exception as exc:            # noqa: BLE001 -- a bad CSV is skippable
            print("  (skipped %s: %r)" % (f, exc))
    return dfs


def _columns(rows):
    """AutoDocPy.addTable() takes the table column-major (one list per column,
    matching the header list); our tables are built row-major, so transpose."""
    return [list(col) for col in zip(*rows)] if rows else []


def stat_table(df, keys):
    """min / mean / 2-sigma / max for a list of summary keys, row-major."""
    rows = []
    for key, label, unit, _ in keys:
        v = pd.to_numeric(df[key], errors="coerce").dropna().to_numpy()
        if v.size == 0:
            continue
        mu, sd = float(np.mean(v)), float(np.std(v))
        rows.append([label + (" [%s]" % unit if unit else ""),
                     "%.3g" % v.min(), "%.3g" % mu, "%.3g" % sd,
                     "%.3g" % (mu - 2 * sd), "%.3g" % (mu + 2 * sd), "%.3g" % v.max()])
    return rows


def hist_pdf_cdf(values, label, unit, target=None):
    """Histogram + smoothed PDF and empirical CDF on a twin axis."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    if v.size == 0:
        ax.text(0.5, 0.5, "no data", ha="center")
        return fig
    ax.hist(v, bins="auto", density=True, alpha=0.35, color="C0", label="samples")
    if v.std() > 0 and v.size > 4:
        xs = np.linspace(v.min(), v.max(), 200)
        try:
            from scipy.stats import gaussian_kde
            ax.plot(xs, gaussian_kde(v)(xs), "C0", lw=1.6, label="PDF")
        except Exception:                   # noqa: BLE001 -- scipy optional
            pdf = np.exp(-0.5 * ((xs - v.mean()) / v.std()) ** 2) / (v.std() * math.sqrt(2 * math.pi))
            ax.plot(xs, pdf, "C0", lw=1.6, label="normal fit")
    mu, sd = v.mean(), v.std()
    for k, ls in ((mu, "-"), (mu - 2 * sd, "--"), (mu + 2 * sd, "--")):
        ax.axvline(k, color="C3", ls=ls, lw=1.0)
    if target is not None:
        ax.axvline(target, color="k", ls=":", lw=1.4, label="target")
    ax.set_xlabel("%s (%s)" % (label, unit))
    ax.set_ylabel("probability density", color="C0")
    ax2 = ax.twinx()
    sv = np.sort(v)
    ax2.step(sv, np.arange(1, sv.size + 1) / sv.size, where="post", color="C1", lw=1.2)
    ax2.set_ylabel("cumulative fraction", color="C1")
    ax2.set_ylim(0, 1)
    ax.set_title("%s   (mean %.4g, 2-sigma +/- %.4g, n=%d)" % (label, mu, 2 * sd, v.size))
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    return fig


def insertion_scatter(df):
    fig, ax = plt.subplots(figsize=(7.6, 6.2))
    good = df["outcome"] == "orbit"
    ax.scatter(df.loc[good, "apoapsis_km"], df.loc[good, "periapsis_km"],
               s=26, color="C0", label="orbit", zorder=3)
    ax.scatter(df.loc[~good, "apoapsis_km"], df.loc[~good, "periapsis_km"],
               s=42, color="C3", marker="x", label="marginal / failed", zorder=4)
    if (df["run"] == 0).any():
        r0 = df[df["run"] == 0].iloc[0]
        ax.scatter([r0["apoapsis_km"]], [r0["periapsis_km"]], s=90,
                   facecolors="none", edgecolors="k", lw=1.6, label="reference (run 0)", zorder=5)
    ax.axvline(TARGET_ALT_KM, color="k", ls=":", lw=1.0)
    ax.axhline(TARGET_ALT_KM, color="k", ls=":", lw=1.0)
    ax.axhline(150.0, color="C3", ls="--", lw=0.8)
    ax.plot([100, 500], [100, 500], color="0.7", lw=0.8, zorder=1)   # circular locus
    ax.text(TARGET_ALT_KM + 3, TARGET_ALT_KM + 3, "circular\n%d km target" % TARGET_ALT_KM, fontsize=8)
    ax.set_xlabel("apoapsis altitude (km)")
    ax.set_ylabel("periapsis altitude (km)")
    ax.set_title("Insertion dispersion: periapsis vs apoapsis")
    ax.legend(fontsize=8)
    ax.set_ylim(min(120, df["periapsis_km"].min() - 10), df["periapsis_km"].max() + 15)
    ax.set_xlim(df["apoapsis_km"].min() - 10, df["apoapsis_km"].max() + 15)
    fig.tight_layout()
    return fig


def sensitivity_grid(df):
    keys = [k for k in DISPERSION_KEYS if ("disp_" + k[0]) in df.columns]
    n = len(keys)
    ncol = 4
    nrow = int(math.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.4 * ncol, 3.0 * nrow))
    axes = np.atleast_1d(axes).ravel()
    good = df["outcome"] == "orbit"
    for ax, (key, label, unit) in zip(axes, keys):
        x = pd.to_numeric(df["disp_" + key], errors="coerce")
        y = pd.to_numeric(df["periapsis_km"], errors="coerce")
        ax.scatter(x[good], y[good], s=16, color="C0")
        ax.scatter(x[~good], y[~good], s=24, color="C3", marker="x")
        m = np.isfinite(x) & np.isfinite(y)
        if m.sum() > 3 and x[m].std() > 0:
            b, a = np.polyfit(x[m], y[m], 1)
            xs = np.linspace(x[m].min(), x[m].max(), 20)
            ax.plot(xs, a + b * xs, "C1", lw=1.2)
            r = np.corrcoef(x[m], y[m])[0, 1]
            ax.set_title("%s  (r=%.2f)" % (label, r), fontsize=9)
        else:
            ax.set_title(label, fontsize=9)
        ax.set_xlabel("%s (%s)" % (label, unit), fontsize=8)
        ax.set_ylabel("periapsis (km)", fontsize=8)
        ax.tick_params(labelsize=7)
    for ax in axes[n:]:
        ax.set_visible(False)
    fig.suptitle("Insertion periapsis sensitivity to input dispersions")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    return fig


def trajectory_overlay(dfs, xcol, ycol, xlabel, ylabel, title, xscale=1.0, yscale=1.0):
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    for run, d in dfs:
        if xcol not in d.columns or ycol not in d.columns:
            continue
        ref = run == 0
        ax.plot(d[xcol] * xscale, d[ycol] * yscale,
                color="C0" if ref else "0.6",
                lw=1.8 if ref else 0.7, alpha=1.0 if ref else 0.45,
                zorder=5 if ref else 1, label="reference (run 0)" if ref else None)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if any(r == 0 for r, _ in dfs):
        ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def ground_track_overlay(dfs):
    """Altitude vs downrange (great-circle from the pad)."""
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    for run, d in dfs:
        if "latitude_rad" not in d.columns:
            continue
        lat = d["latitude_rad"].to_numpy()
        lon = d["longitude_rad"].to_numpy()
        lat0, lon0 = lat[0], lon[0]
        dsig = np.arccos(np.clip(np.sin(lat0) * np.sin(lat)
                                 + np.cos(lat0) * np.cos(lat) * np.cos(lon - lon0), -1, 1))
        downrange_km = R_EARTH_KM * dsig
        ref = run == 0
        ax.plot(downrange_km, d["altitude_m"].to_numpy() / 1e3,
                color="C0" if ref else "0.6", lw=1.8 if ref else 0.7,
                alpha=1.0 if ref else 0.45, zorder=5 if ref else 1,
                label="reference (run 0)" if ref else None)
    ax.set_xlabel("downrange distance (km)")
    ax.set_ylabel("altitude (km)")
    ax.set_title("Ascent trajectory: altitude vs downrange")
    if any(r == 0 for r, _ in dfs):
        ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    df = load_summaries(RESULTS_DIR)
    trajs = load_trajectories(RESULTS_DIR)
    n = len(df)
    print("Loaded %d runs (%d trajectories) from %s" % (n, len(trajs), RESULTS_DIR))

    outcomes = df["outcome"].value_counts().to_dict()
    n_orbit = int(outcomes.get("orbit", 0))
    print("Outcomes:", outcomes)

    figures = []      # (section, title, fig)

    # --- distributions ---
    for key, label, unit, target in DISTRIBUTIONS:
        if key not in df.columns:
            continue
        figures.append(("Distributions", label,
                        hist_pdf_cdf(df[key], label, unit, target)))

    # --- scatters ---
    figures.append(("Insertion", "Periapsis vs apoapsis", insertion_scatter(df)))
    figures.append(("Insertion", "Dispersion sensitivity", sensitivity_grid(df)))

    # --- trajectory overlays ---
    if trajs:
        figures.append(("Trajectories", "Altitude vs downrange", ground_track_overlay(trajs)))
        figures.append(("Trajectories", "Altitude vs time",
                        trajectory_overlay(trajs, "time_s", "altitude_m",
                                           "mission time (s)", "altitude (km)",
                                           "Altitude vs time", yscale=1e-3)))
        figures.append(("Trajectories", "Dynamic pressure vs time",
                        trajectory_overlay(trajs, "time_s", "q_pa",
                                           "mission time (s)", "dynamic pressure (kPa)",
                                           "Dynamic pressure vs time", yscale=1e-3)))
        figures.append(("Trajectories", "Mach vs time",
                        trajectory_overlay(trajs, "time_s", "mach",
                                           "mission time (s)", "Mach number", "Mach vs time")))
        figures.append(("Trajectories", "UPFG time-to-go vs time",
                        trajectory_overlay(trajs, "time_s", "upfg_t_go_s",
                                           "mission time (s)", "UPFG t_go (s)",
                                           "Guidance time-to-go vs time")))
        figures.append(("Trajectories", "Throttle command vs time",
                        trajectory_overlay(trajs, "time_s", "upfg_throttle",
                                           "mission time (s)", "throttle command",
                                           "Guidance throttle command vs time")))
        figures.append(("Trajectories", "Attitude-tracking error vs time",
                        trajectory_overlay(trajs, "time_s", "point_err_rad",
                                           "mission time (s)", "pointing error (deg)",
                                           "Attitude-tracking error vs time",
                                           yscale=180.0 / math.pi)))

    for _, title, fig in figures:
        png = os.path.join(FIG_DIR, title.lower().replace(" ", "_").replace("/", "_") + ".png")
        fig.savefig(png, dpi=105)
    print("Wrote %d figures to %s" % (len(figures), FIG_DIR))

    def _img_block(fig, alt):
        """A self-contained <img> for the report: the PNG base64'd straight into
        the HTML as a data URI, wrapped in an AsciiDoc passthrough block. Nothing
        in the report then points at a file on disk, so it renders the same from
        file://, a local web server, or after the results dir is moved -- unlike
        AutoDocPy.addMatPlotLib, which references figures by absolute path."""
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=105)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return ('\n\n++++\n<img alt="%s" style="max-width:100%%"'
                ' src="data:image/png;base64,%s">\n++++\n\n' % (alt, b64))

    # --- assemble the document ---
    try:
        from warptwinutils.AutoDocPy import AutoDocPy
        doc = AutoDocPy()
        doc.title("SSTO Orbital Insertion -- Monte Carlo Analysis")
        doc.author("James Tabony", "james.tabony@warpware.co")
        doc.file(DOC_NAME)

        doc.addText(
            "Closed-loop single-stage-to-orbit ascent (LaunchVehicle plant + "
            "LaunchPadModel + StochasticNavigation + UnifiedPoweredFlightGuidance "
            "+ SingleAxisPointingControl), flown %d times with per-run vehicle, "
            "environment and pad dispersions and independent GN&C model error. "
            "Run 0 is the undispersed reference.\n\n" % n)

        doc.addPrimaryHeader("Mission outcome")
        rows = [[k, str(v), "%.1f%%" % (100.0 * v / n)] for k, v in
                sorted(outcomes.items(), key=lambda kv: -kv[1])]
        doc.addTable(_columns(rows), ["outcome", "runs", "fraction"], [], True)
        doc.addText(
            "\n'orbit' = periapsis > 150 km and apoapsis within 90 km of the "
            "%d km target -- a usable parking orbit. 'marginal' = MECO reached "
            "but outside that box (safe, but eccentric enough to need a real "
            "circularization burn). %d / %d runs (%.1f%%) reached a usable "
            "parking orbit.\n\n"
            % (TARGET_ALT_KM, n_orbit, n, 100.0 * n_orbit / n))

        doc.addPrimaryHeader("Insertion accuracy")
        doc.addTable(_columns(stat_table(df, DISTRIBUTIONS[:6])),
                     ["quantity", "min", "mean", "sigma", "-2s", "+2s", "max"], [], True)

        section = None
        for sec, title, fig in figures:
            if sec != section:
                doc.addPrimaryHeader(sec)
                section = sec
            doc.addText(title)
            doc.addText(_img_block(fig, title))

        try:
            doc.closeGenerateDoc()
            print("Wrote %s" % os.path.join(
                RESULTS_DIR, DOC_NAME.replace(".adoc", ".html")))
        except Exception:                   # noqa: BLE001 -- asciidoctor optional
            doc.closeFile()
            print("Wrote %s (install asciidoctor for the HTML render)"
                  % os.path.join(RESULTS_DIR, DOC_NAME))
    except Exception as exc:                # noqa: BLE001 -- the PNGs are the deliverable
        print("AutoDocPy step skipped (%r); figures are in %s" % (exc, FIG_DIR))

    for _, _, fig in figures:
        plt.close(fig)


if __name__ == "__main__":
    main()
