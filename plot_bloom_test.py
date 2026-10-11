#!/usr/bin/env python3
"""
Chart of the multi-year bloom test: modelled vs observed bloom anomalies.

Reads data/bloom_multiyear.csv (written by run_bloom_test.py) and draws one
panel per city, south to north. Anomalies are computed as in
run_bloom_test.py: each city's mean is removed from model and observations
separately.

Usage:
    python plot_bloom_test.py journal/screenshots/YYYY-MM-DD-bloom-anomaly-chart.png
"""

import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from validation.config import DATA_DIR, VALIDATION_LOCATIONS

RESULTS_FILE = DATA_DIR / "bloom_multiyear.csv"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
OBSERVED_COLOR = "#2a78d6"
MODEL_COLOR = "#eb6834"


def load_anomalies():
    df = pd.read_csv(RESULTS_FILE)
    grouped = df.groupby("location")
    df["model_anom"] = df["model"] - grouped["model"].transform("mean")
    df["obs_anom"] = df["observed"] - grouped["observed"].transform("mean")
    return df


def draw_panel(ax, city, years):
    full = city.set_index("year").reindex(years)
    ax.axhline(0, color=BASELINE, linewidth=1, zorder=1)
    for column, color in (("obs_anom", OBSERVED_COLOR), ("model_anom", MODEL_COLOR)):
        ax.plot(full.index, full[column], color=color, linewidth=2,
                solid_capstyle="round", solid_joinstyle="round", zorder=3)

    r = np.corrcoef(city["model_anom"], city["obs_anom"])[0, 1]
    name = city["location"].iloc[0].split(", ")[0]
    ax.set_title(name, loc="left", fontsize=12, fontweight="bold", color=INK, pad=6)
    ax.set_title(f"r = {r:.2f}", loc="right", fontsize=10.5, color=INK_SECONDARY, pad=6)

    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0, labelsize=10, labelcolor=INK_MUTED)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("output", help="PNG file to write")
    args = parser.parse_args()

    plt.rcParams["font.family"] = ["Arial", "DejaVu Sans"]

    df = load_anomalies()
    years = range(df["year"].min(), df["year"].max() + 1)
    latitude = {name: lat for name, lat, _lon, _zone in VALIDATION_LOCATIONS}
    cities = sorted(df["location"].unique(), key=latitude.get)
    overall_r = np.corrcoef(df["model_anom"], df["obs_anom"])[0, 1]

    fig, axes = plt.subplots(2, 4, figsize=(13, 8), sharex=True, sharey=True,
                             facecolor=SURFACE)
    fig.subplots_adjust(left=0.065, right=0.98, top=0.76, bottom=0.115,
                        wspace=0.12, hspace=0.3)
    for ax, location in zip(axes.flat, cities):
        draw_panel(ax, df[df["location"] == location], years)

    limit = 5 * np.ceil(df[["model_anom", "obs_anom"]].abs().max().max() / 5)
    axes[0, 0].set_ylim(-limit, limit)
    axes[0, 0].set_yticks([-20, -10, 0, 10, 20])
    axes[0, 0].set_yticklabels(["−20", "−10", "0", "+10", "+20"])
    axes[0, 0].set_xticks([years[0], years[len(years) // 2], years[-1]])
    fig.supylabel("Days later (+) or earlier (−) than the city's average",
                  x=0.012, fontsize=10.5, color=INK_SECONDARY)

    fig.text(0.065, 0.955, "A US lilac model tracks early and late springs "
             f"in {len(cities)} European cities",
             fontsize=18, fontweight="bold", color=INK, va="top")
    fig.text(0.065, 0.905,
             f"First lilac bloom each year, {years[0]}–{years[-1]}, against each city's "
             f"own average. Unmodified SI-x bloom index, nothing fitted.\n"
             f"Correlation r = {overall_r:.2f} across {len(df)} city-years. "
             "Cities ordered south to north.",
             fontsize=11.5, color=INK_SECONDARY, va="top", linespacing=1.45)
    fig.legend(
        handles=[Line2D([], [], color=OBSERVED_COLOR, linewidth=2, label="Observed bloom"),
                 Line2D([], [], color=MODEL_COLOR, linewidth=2, label="SI-x model")],
        loc="upper left", bbox_to_anchor=(0.058, 0.835), ncol=2, frameon=False,
        fontsize=11, labelcolor=INK_SECONDARY, handlelength=1.6, columnspacing=1.8)
    fig.text(0.065, 0.03,
             "Observations: DWD (CC BY 4.0) and SLU Naturens Kalender (CC0), median of "
             "stations near each city. Temperature: ERA5, contains modified Copernicus "
             "Climate Change Service information.",
             fontsize=9, color=INK_MUTED, va="bottom")

    fig.savefig(args.output, dpi=160, facecolor=SURFACE)
    print(f"✓ Wrote {args.output}")


if __name__ == "__main__":
    main()
