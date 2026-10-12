#!/usr/bin/env python3
"""
Charts of the multi-year bloom test, drawn from data/bloom_multiyear.csv
(written by run_bloom_test.py).

- anomalies: modelled vs observed bloom anomalies, one panel per city,
  south to north.
- uncertainty: the anomaly result with 95% intervals, per country, and with
  each city left out (statistics from validation/bloom_stats.py).

Anomalies are computed as in run_bloom_test.py: each city's mean is removed
from model and observations separately.

Usage:
    python plot_bloom_test.py journal/screenshots/YYYY-MM-DD-name.png [--chart uncertainty]
"""

import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from validation import bloom_stats
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
ESTIMATE_COLOR = "#2a78d6"
BENCHMARK_COLOR = "#898781"

LEFT = 0.065
SOURCES = ("Observations: DWD (CC BY 4.0) and SLU Naturens Kalender (CC0), median of "
           "stations near each city. Temperature: ERA5, contains modified Copernicus "
           "Climate Change Service information.")


def load_anomalies():
    df = pd.read_csv(RESULTS_FILE)
    grouped = df.groupby("location")
    df["model_anom"] = df["model"] - grouped["model"].transform("mean")
    df["obs_anom"] = df["observed"] - grouped["observed"].transform("mean")
    return df


def south_to_north(df):
    latitude = {name: lat for name, lat, _lon, _zone in VALIDATION_LOCATIONS}
    return sorted(df["location"].unique(), key=latitude.get)


def style_axes(ax, grid_axis):
    ax.set_facecolor(SURFACE)
    ax.grid(axis=grid_axis, color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0, labelsize=10, labelcolor=INK_MUTED)


def add_text(fig, title, subtitle, left=LEFT):
    fig.text(left, 0.955, title, fontsize=18, fontweight="bold", color=INK, va="top")
    fig.text(left, 0.905, subtitle, fontsize=11.5, color=INK_SECONDARY, va="top",
             linespacing=1.45)
    fig.text(left, 0.03, SOURCES, fontsize=9, color=INK_MUTED, va="bottom")


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
    style_axes(ax, "y")


def anomalies_chart(df, output):
    years = range(df["year"].min(), df["year"].max() + 1)
    cities = south_to_north(df)
    overall_r = np.corrcoef(df["model_anom"], df["obs_anom"])[0, 1]

    fig, axes = plt.subplots(2, 4, figsize=(13, 8), sharex=True, sharey=True,
                             facecolor=SURFACE)
    fig.subplots_adjust(left=LEFT, right=0.98, top=0.76, bottom=0.115,
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

    add_text(fig,
             f"A US lilac model tracks early and late springs in {len(cities)} European cities",
             f"First lilac bloom each year, {years[0]}–{years[-1]}, against each city's "
             f"own average. Unmodified SI-x bloom index, nothing fitted.\n"
             f"Correlation r = {overall_r:.2f} across {len(df)} city-years. "
             "Cities ordered south to north.")
    fig.legend(
        handles=[Line2D([], [], color=OBSERVED_COLOR, linewidth=2, label="Observed bloom"),
                 Line2D([], [], color=MODEL_COLOR, linewidth=2, label="SI-x model")],
        loc="upper left", bbox_to_anchor=(0.058, 0.835), ncol=2, frameon=False,
        fontsize=11, labelcolor=INK_SECONDARY, handlelength=1.6, columnspacing=1.8)
    fig.savefig(output, dpi=160, facecolor=SURFACE)


def uncertainty_rows(df):
    """Rows of the uncertainty chart, top to bottom; None is a gap."""
    pooled = bloom_stats.overall(df)
    rows = [{"label": f"All {df['location'].nunique()} cities", **pooled["estimate"],
             "interval": pooled["by_year"]}]
    for c in bloom_stats.by_country(df):
        rows.append({"label": f"{c['country']} ({c['cities']} cities)", **c})
    rows.append(None)
    left_out = {r["without"]: r for r in bloom_stats.leave_one_city_out(df)}
    for location in south_to_north(df):
        rows.append({"label": f"Without {location.split(', ')[0]}", **left_out[location]})
    return rows


def draw_estimates(ax, rows, key, benchmark_key=None):
    for y, row in enumerate(rows):
        if row is None:
            continue
        if benchmark_key:
            ax.plot(row[benchmark_key], y, "o", color=BENCHMARK_COLOR, markersize=9,
                    markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
        if "interval" in row:
            ax.plot(row["interval"][key], [y, y], color=ESTIMATE_COLOR, linewidth=2,
                    solid_capstyle="round", zorder=4)
        ax.plot(row[key], y, "o", color=ESTIMATE_COLOR, markersize=9,
                markeredgecolor=SURFACE, markeredgewidth=2, zorder=5)
    style_axes(ax, "x")


def uncertainty_chart(df, output):
    rows = uncertainty_rows(df)
    pooled = rows[0]
    years = df["year"].nunique()

    fig, (left, right) = plt.subplots(1, 2, figsize=(13, 8), sharey=True, facecolor=SURFACE)
    fig.subplots_adjust(left=0.2, right=0.97, top=0.71, bottom=0.13, wspace=0.1)

    draw_estimates(left, rows, "anomaly_r")
    lowest = min(r["interval"]["anomaly_r"][0] if "interval" in r else r["anomaly_r"]
                 for r in rows if r)
    left.set_xlim(np.floor(lowest * 10 - 0.5) / 10, 1.0)
    left.set_title("Correlation with observed early or late", loc="left", fontsize=12,
                   fontweight="bold", color=INK, pad=22)
    left.text(0, 1.025, "1 = perfect", transform=left.transAxes, fontsize=10.5,
              color=INK_SECONDARY)
    left.annotate(f"{pooled['anomaly_r']:.2f}", (pooled["interval"]["anomaly_r"][1], 0),
                  xytext=(8, 0), textcoords="offset points", va="center", fontsize=10.5,
                  color=INK)

    draw_estimates(right, rows, "anomaly_rmse", benchmark_key="normal_year_rmse")
    right.set_xlim(0, np.ceil(max(r["normal_year_rmse"] for r in rows if r)) + 0.5)
    right.set_title("Error on early or late, in days", loc="left", fontsize=12,
                    fontweight="bold", color=INK, pad=22)
    right.text(0, 1.025, "Lower is better", transform=right.transAxes, fontsize=10.5,
               color=INK_SECONDARY)
    right.annotate(f"{pooled['anomaly_rmse']:.1f}", (pooled["interval"]["anomaly_rmse"][0], 0),
                   xytext=(-8, 0), textcoords="offset points", va="center", ha="right",
                   fontsize=10.5, color=INK)
    right.annotate(f"{pooled['normal_year_rmse']:.1f}", (pooled["normal_year_rmse"], 0),
                   xytext=(9, 0), textcoords="offset points", va="center", fontsize=10.5,
                   color=INK)

    left.set_ylim(len(rows) - 0.4, -0.6)
    left.set_yticks([y for y, row in enumerate(rows) if row])
    left.set_yticklabels([row["label"] for row in rows if row])
    left.tick_params(axis="y", labelsize=11, labelcolor=INK_SECONDARY, pad=10)

    low, high = pooled["interval"]["anomaly_r"]
    add_text(fig, "How sure is the bloom result?",
             f"Modelled vs observed bloom anomalies, {df['year'].min()}–{df['year'].max()}: "
             f"correlation {pooled['anomaly_r']:.2f}, 95% interval {low:.2f} to {high:.2f}.\n"
             f"Cities share each year's weather, so this is closer to {years} independent "
             f"springs than to {pooled['n']} tests. Intervals resample whole years.",
             left=0.035)
    fig.legend(
        handles=[Line2D([], [], color=ESTIMATE_COLOR, marker="o", markersize=8, linewidth=2,
                        label="SI-x model, line = 95% interval"),
                 Line2D([], [], color=BENCHMARK_COLOR, marker="o", markersize=8, linewidth=0,
                        label="Always predicting a normal year")],
        loc="upper left", bbox_to_anchor=(0.028, 0.815), ncol=2, frameon=False,
        fontsize=11, labelcolor=INK_SECONDARY, handlelength=1.6, columnspacing=1.8)
    fig.savefig(output, dpi=160, facecolor=SURFACE)


CHARTS = {"anomalies": anomalies_chart, "uncertainty": uncertainty_chart}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("output", help="PNG file to write")
    parser.add_argument("--chart", choices=CHARTS, default="anomalies")
    args = parser.parse_args()

    plt.rcParams["font.family"] = ["Arial", "DejaVu Sans"]
    CHARTS[args.chart](load_anomalies(), args.output)
    print(f"✓ Wrote {args.output}")


if __name__ == "__main__":
    main()
