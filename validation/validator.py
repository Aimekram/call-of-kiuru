"""
Validation: Compare SI-x model predictions against reference (observed) phenology data.
Computes RMSE and bias per (event, species) and writes the public validation log.

Each reference row names an event ("leaf" or "bloom") and a species. Leaf
references are compared with the SI-x leaf index, bloom references with the
SI-x bloom index. Both the published SI-x index (average of three plants) and
the lilac sub-model are recorded, since lilac is the closest match to the
European lilac observations.
"""

from datetime import datetime

import numpy as np
import pandas as pd

from .config import DATA_DIR, VALIDATION_LOG_FILE

_MODEL_COLUMNS = {
    "leaf": ("leaf_out_doy", "lilac_doy"),
    "bloom": ("bloom_doy", "lilac_bloom_doy"),
}


class ValidationEntry:
    """A single comparison: model prediction vs. reference observation."""

    def __init__(self, location, climate_zone, year, event, species,
                 model_doy, model_lilac_doy, observed_doy, n_obs, source, notes=""):
        self.location = location
        self.climate_zone = climate_zone
        self.year = year
        self.event = event
        self.species = species
        self.model_doy = model_doy
        self.model_lilac_doy = model_lilac_doy
        self.observed_doy = observed_doy
        self.n_obs = n_obs
        self.source = source
        self.notes = notes
        self.checked_date = datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def _diff(model, observed):
        if pd.isna(model) or pd.isna(observed):
            return None
        return model - observed

    def to_dict(self):
        return {
            "location": self.location,
            "climate_zone": self.climate_zone,
            "year": self.year,
            "event": self.event,
            "species": self.species,
            "model_doy": self.model_doy,
            "model_lilac_doy": self.model_lilac_doy,
            "observed_doy": self.observed_doy,
            "error_days": self._diff(self.model_doy, self.observed_doy),
            "lilac_error_days": self._diff(self.model_lilac_doy, self.observed_doy),
            "n_obs": self.n_obs,
            "source": self.source,
            "notes": self.notes,
            "checked_date": self.checked_date,
        }


def _error_stats(errors):
    errors = pd.Series(errors, dtype=float).dropna()
    if errors.empty:
        return None
    return {
        "count": len(errors),
        "rmse": float(np.sqrt((errors ** 2).mean())),
        "bias": float(errors.mean()),
    }


class ValidationLog:
    """The validation log for the current comparison run (CSV + markdown)."""

    def __init__(self, log_file=None):
        self.log_file = log_file or DATA_DIR / "validation_entries.csv"
        self.entries = []

    def add_entry(self, entry: ValidationEntry):
        self.entries.append(entry.to_dict())

    def save(self):
        pd.DataFrame(self.entries).to_csv(self.log_file, index=False)
        print(f"✓ Saved {len(self.entries)} validation entries to {self.log_file}")

    def compute_statistics(self):
        """RMSE/bias per (event, species), for the SI-x index and the lilac sub-model."""
        if not self.entries:
            return {}
        df = pd.DataFrame(self.entries)
        stats = {}
        for (event, species), group in df.groupby(["event", "species"]):
            stats[(event, species)] = {
                "index": _error_stats(group["error_days"]),
                "lilac": _error_stats(group["lilac_error_days"]),
            }
        return stats

    def write_markdown_summary(self, output_file=None):
        output_file = output_file or VALIDATION_LOG_FILE
        stats = self.compute_statistics()
        if not stats:
            print("No validation data to summarize yet.")
            return

        def fmt(s):
            return f"{s['rmse']:.1f} days RMSE, bias {s['bias']:+.1f} (n={s['count']})" if s else "—"

        def doy(value):
            # The index averages three plants, so it can be fractional.
            if pd.isna(value):
                return "—"
            return f"{value:.1f}".removesuffix(".0")

        lines = [
            "# Call of Kiuru — Validation Log",
            "",
            "Model predictions (USA-NPN Extended Spring Indices, SI-x) compared against",
            "observed phenology from national open-data networks. Positive error = model late.",
            "",
            "## Summary",
            "",
            "| Event | Reference species | SI-x index (3-plant average) | SI-x lilac sub-model |",
            "|---|---|---|---|",
        ]
        for (event, species), s in sorted(stats.items()):
            lines.append(f"| {event} | {species} | {fmt(s['index'])} | {fmt(s['lilac'])} |")

        lines += [
            "",
            "## Entries",
            "",
            "| Location | Year | Event | Species | Model (index) | Model (lilac) | Observed | Error (index) | n obs | Source |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for e in sorted(self.entries, key=lambda e: (e["event"], e["species"], e["location"])):
            err = "—" if e["error_days"] is None else f"{e['error_days']:+.1f}"
            lines.append(
                f"| {e['location']} | {e['year']} | {e['event']} | {e['species']} | "
                f"{doy(e['model_doy'])} | {doy(e['model_lilac_doy'])} | {doy(e['observed_doy'])} | {err} | "
                f"{e['n_obs']} | {e['source']} |"
            )

        with open(output_file, "w") as f:
            f.write("\n".join(lines) + "\n")
        print(f"✓ Wrote validation summary to {output_file}")


def validate_against_reference(model_results_csv, reference_data_csv):
    """
    Compare model predictions against reference observations.

    Args:
        model_results_csv: model predictions (location, year, leaf_out_doy,
            lilac_doy, bloom_doy, lilac_bloom_doy, climate_zone, ...)
        reference_data_csv: reference observations (location, year, event,
            species, doy, n_obs, source, notes)
    """
    model_df = pd.read_csv(model_results_csv)
    ref_df = pd.read_csv(reference_data_csv, comment="#")
    merged = pd.merge(model_df, ref_df, on=["location", "year"])

    log = ValidationLog()
    for _, row in merged.iterrows():
        index_col, lilac_col = _MODEL_COLUMNS[row["event"]]
        log.add_entry(ValidationEntry(
            location=row["location"],
            climate_zone=row.get("climate_zone", ""),
            year=row["year"],
            event=row["event"],
            species=row["species"],
            model_doy=row[index_col],
            model_lilac_doy=row[lilac_col],
            observed_doy=row["doy"],
            n_obs=row["n_obs"],
            source=row["source"],
            notes=row.get("notes", ""),
        ))
    return log
