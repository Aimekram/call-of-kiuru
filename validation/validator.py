"""
Validation: Compare SI-x model predictions against reference (observed) phenology data.
Computes RMSE, bias, and tracks validation entries for the public log.
"""

import csv
import pandas as pd
from pathlib import Path
from datetime import datetime
from .config import DATA_DIR, VALIDATION_LOG_FILE


class ValidationEntry:
    """
    A single validation comparison: model prediction vs. reference observation.
    """
    
    def __init__(self, location, climate_zone, year, model_doy, observed_doy, 
                 source, notes=""):
        self.location = location
        self.climate_zone = climate_zone
        self.year = year
        self.model_doy = model_doy
        self.observed_doy = observed_doy
        self.source = source
        self.notes = notes
        self.checked_date = datetime.now().strftime("%Y-%m-%d")
    
    def error_days(self):
        """Return prediction error in days (negative = model too early)."""
        if self.model_doy is None or self.observed_doy is None:
            return None
        return self.model_doy - self.observed_doy
    
    def to_dict(self):
        return {
            "location": self.location,
            "climate_zone": self.climate_zone,
            "year": self.year,
            "model_doy": self.model_doy,
            "observed_doy": self.observed_doy,
            "error_days": self.error_days(),
            "source": self.source,
            "notes": self.notes,
            "checked_date": self.checked_date,
        }


class ValidationLog:
    """
    Manages the running validation log (CSV + markdown documentation).
    """
    
    def __init__(self, log_file=None):
        self.log_file = log_file or DATA_DIR / "validation_entries.csv"
        self.entries = []
        self.load_existing()
    
    def load_existing(self):
        """Load any previously logged entries."""
        if self.log_file.exists():
            df = pd.read_csv(self.log_file)
            self.entries = df.to_dict('records')
    
    def add_entry(self, entry: ValidationEntry):
        """Add a new validation entry."""
        self.entries.append(entry.to_dict())
    
    def save(self):
        """Write all entries to CSV."""
        df = pd.DataFrame(self.entries)
        df.to_csv(self.log_file, index=False)
        print(f"✓ Saved {len(self.entries)} validation entries to {self.log_file}")
    
    def compute_statistics(self):
        """
        Compute overall validation statistics.
        
        Returns:
            {
                "count": int,
                "rmse": float,
                "bias": float,
                "std_dev": float,
                "by_climate_zone": dict of zone -> stats,
            }
        """
        if not self.entries:
            return None
        
        df = pd.DataFrame(self.entries)
        errors = df['error_days'].dropna()
        
        if len(errors) == 0:
            return None
        
        stats = {
            "count": len(errors),
            "rmse": float(np.sqrt((errors ** 2).mean())),
            "bias": float(errors.mean()),
            "std_dev": float(errors.std()),
        }
        
        # Break down by climate zone
        stats["by_climate_zone"] = {}
        for zone in df['climate_zone'].unique():
            zone_errors = df[df['climate_zone'] == zone]['error_days'].dropna()
            if len(zone_errors) > 0:
                stats["by_climate_zone"][zone] = {
                    "count": len(zone_errors),
                    "rmse": float(np.sqrt((zone_errors ** 2).mean())),
                    "bias": float(zone_errors.mean()),
                }
        
        return stats
    
    def write_markdown_summary(self, output_file=None):
        """
        Write validation statistics to a markdown file (for the public methodology page).
        
        Args:
            output_file: Path to write (default: VALIDATION_LOG_FILE in config)
        """
        output_file = output_file or VALIDATION_LOG_FILE
        stats = self.compute_statistics()
        
        if not stats:
            print("No validation data to summarize yet.")
            return
        
        lines = [
            "# Call of Kiuru — Validation Log",
            "",
            "This page documents how we validated the SI-x phenology model before launch.",
            "Each entry represents a model prediction compared against published reference data.",
            "",
            "## Overall Statistics",
            f"- **Comparisons:** {stats['count']} (location, year) pairs",
            f"- **RMSE:** {stats['rmse']:.1f} days",
            f"- **Bias:** {stats['bias']:.1f} days (negative = model predicts too early)",
            f"- **Std Dev:** {stats['std_dev']:.1f} days",
            "",
        ]
        
        if stats.get("by_climate_zone"):
            lines.extend([
                "## By Climate Zone",
                "",
            ])
            for zone, zone_stats in stats["by_climate_zone"].items():
                lines.extend([
                    f"### {zone.title()}",
                    f"- Comparisons: {zone_stats['count']}",
                    f"- RMSE: {zone_stats['rmse']:.1f} days",
                    f"- Bias: {zone_stats['bias']:.1f} days",
                    "",
                ])
        
        lines.extend([
            "## Validation Entries",
            "",
            "| Location | Climate Zone | Year | Model DOY | Observed DOY | Error (days) | Source | Notes |",
            "|----------|--------------|------|-----------|--------------|--------------|--------|-------|",
        ])
        
        for entry in sorted(self.entries, key=lambda e: (e['location'], e['year'])):
            error_str = f"{entry['error_days']:.1f}" if entry['error_days'] is not None else "—"
            model_str = str(entry['model_doy']) if entry['model_doy'] is not None else "—"
            obs_str = str(entry['observed_doy']) if entry['observed_doy'] is not None else "—"
            
            lines.append(
                f"| {entry['location']} | {entry['climate_zone']} | {entry['year']} | "
                f"{model_str} | {obs_str} | {error_str} | {entry['source']} | {entry['notes']} |"
            )
        
        with open(output_file, 'w') as f:
            f.write('\n'.join(lines))
        
        print(f"✓ Wrote validation summary to {output_file}")


# Utility functions for common validation scenarios

def validate_against_dwd_phenology(model_results_df, dwd_data_csv):
    """
    Compare model predictions against DWD phenology data.
    
    Args:
        model_results_df: DataFrame with columns: location, year, leaf_out_doy
        dwd_data_csv: Path to DWD reference data (with columns: location, year, leaf_out_doy)
    
    Returns:
        List of ValidationEntry objects
    """
    model_df = pd.read_csv(model_results_df)
    ref_df = pd.read_csv(dwd_data_csv)
    
    validation_log = ValidationLog()
    
    merged = pd.merge(
        model_df, ref_df,
        on=['location', 'year'],
        suffixes=('_model', '_observed')
    )
    
    for _, row in merged.iterrows():
        entry = ValidationEntry(
            location=row['location'],
            climate_zone=row.get('climate_zone', ''),
            year=row['year'],
            model_doy=row['leaf_out_doy_model'],
            observed_doy=row['leaf_out_doy_observed'],
            source="DWD (German Weather Service)",
        )
        validation_log.add_entry(entry)
    
    return validation_log


if __name__ == "__main__":
    # Example usage (will fill in once we have reference data)
    import numpy as np
    
    log = ValidationLog()
    
    # Dummy entries for demonstration
    log.add_entry(ValidationEntry(
        "Berlin, Germany", "continental", 2023,
        model_doy=114, observed_doy=118,
        source="DWD"
    ))
    log.add_entry(ValidationEntry(
        "Berlin, Germany", "continental", 2022,
        model_doy=110, observed_doy=108,
        source="DWD"
    ))
    
    log.save()
    log.write_markdown_summary()
