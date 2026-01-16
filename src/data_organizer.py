"""
Data Organizer for MEA Analysis

Creates a master long-format DataFrame from multiple CSV files.
Expected downstream schema:
plate_id, time_point, well, condition, condition_color, metric, value, metric_type
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, List, Tuple, Optional, Dict, Any

import pandas as pd
import yaml


class DataOrganizer:
    """Organizes MEA data into a master long-format DataFrame."""

    def __init__(
        self,
        experiment_config_path: str | Path,
        config_handler=None,
        project_root: str | Path | None = None,
        drop_ignored_wells: bool = True,
    ):
        """
        Parameters
        ----------
        experiment_config_path : str or Path
            Path to experiment YAML configuration file (e.g., config/Plate_VPA.yaml)
        config_handler : ConfigHandler, optional
            Used to classify metrics (count/rate/duration/derived)
        project_root : str or Path, optional
            Root directory to resolve relative paths (defaults to config/..)
        drop_ignored_wells : bool
            If True (recommended), rows from ignore_wells are removed from master_df.
        """
        self.experiment_config_path = Path(experiment_config_path)
        self.config_handler = config_handler
        self.drop_ignored_wells = drop_ignored_wells

        # Load YAML config
        self.experiment_config = self._load_experiment_config()

        # Resolve project root
        if project_root is None:
            # assumes config lives in <project_root>/config/
            self.project_root = self.experiment_config_path.parent.parent
        else:
            self.project_root = Path(project_root)

        # Experiment info
        self.plate_id = self.experiment_config["experiment"]["plate_id"]

        # Data directory
        raw_data_dir = self.experiment_config["experiment"]["data_dir"]
        self.data_dir = (self.project_root / raw_data_dir).resolve()
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")

        # Conditions
        self.conditions: Dict[str, Dict[str, Any]] = self.experiment_config["conditions"]

        # Optional ignored wells
        self.ignore_wells: List[str] = [
            str(w).strip().upper()
            for w in self.experiment_config.get("ignore_wells", []) or []
        ]

        # Build mapping structures
        self.well_to_condition = self._create_well_mapping()
        self.condition_to_color = self._create_condition_color_mapping()

        # Storage
        self.master_df: Optional[pd.DataFrame] = None

    # -------------------------
    # Config + mappings
    # -------------------------
    def _load_experiment_config(self) -> dict:
        """Load experiment configuration from YAML."""
        if not self.experiment_config_path.exists():
            raise FileNotFoundError(f"Experiment config not found: {self.experiment_config_path}")

        with open(self.experiment_config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        print(f"✓ Loaded experiment config: {self.experiment_config_path.name}")
        return config

    def _create_well_mapping(self) -> Dict[str, str]:
        """
        Create mapping: {well_id: condition_name}
        Validates duplicate assignment.
        """
        mapping: Dict[str, str] = {}

        for condition_name, condition_info in self.conditions.items():
            wells = condition_info.get("wells", [])
            for well in wells:
                well_id = str(well).strip().upper()
                if well_id in mapping:
                    raise ValueError(f"Well {well_id} assigned to multiple conditions!")
                mapping[well_id] = condition_name

        print(f"✓ Created well mapping: {len(mapping)} wells across {len(self.conditions)} conditions")
        return mapping

    def _create_condition_color_mapping(self) -> Dict[str, str]:
        """
        Create mapping: {condition_name: color_hex}
        """
        out: Dict[str, str] = {}
        for condition_name, condition_info in self.conditions.items():
            out[condition_name] = condition_info.get("color", None)
        return out

    # -------------------------
    # CSV discovery
    # -------------------------
    def discover_csv_files(self) -> List[Tuple[int, Path]]:
        """
        Discover and order CSV files by numeric prefix: 0_..., 1_..., 2_...

        Returns
        -------
        list[(time_point:int, path:Path)]
        """
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")

        csv_files: List[Tuple[int, Path]] = []
        for file_path in self.data_dir.glob("*.csv"):
            match = re.match(r"^(\d+)_", file_path.name)
            if match:
                tp = int(match.group(1))
                csv_files.append((tp, file_path))

        csv_files.sort(key=lambda x: x[0])

        if not csv_files:
            raise ValueError(f"No CSV files with numeric prefix found in {self.data_dir}")

        print("\n" + "=" * 60)
        print("DISCOVERED CSV FILES")
        print("=" * 60)
        for tp, path in csv_files:
            print(f"  Time point {tp}: {path.name}")
        print("=" * 60 + "\n")

        return csv_files
    
    # -------------------------
    # Missing-value handling
    # -------------------------
    def apply_metric_missing_value_rules(self, df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
        """Apply metric-type-specific missing-value rules.

        Rules (from metrics_config.yaml via ConfigHandler):
          - count + rate metrics: missing values mean "no detected events" -> fill with 0
          - interval/duration + derived metrics: missing values are "undefined" -> keep as NaN

        Notes
        -----
        - This function only changes rows where df['value'] is NaN.
        - It requires self.config_handler to be set; otherwise it returns df unchanged.
        """
        if self.config_handler is None:
            return df

        if "metric" not in df.columns or "value" not in df.columns:
            raise ValueError("DataFrame must contain 'metric' and 'value' columns")

        out = df.copy()

        # Ensure numeric values (non-numeric become NaN)
        out["value"] = pd.to_numeric(out["value"], errors="coerce")

        # Ensure metric_type exists
        if "metric_type" not in out.columns:
            out["metric_type"] = out["metric"].apply(self.config_handler.get_metric_type)

        missing_mask = out["value"].isna()
        fill_zero_mask = missing_mask & out["metric_type"].isin(["count", "rate"])

        n_filled = int(fill_zero_mask.sum())

        if n_filled > 0:
            out.loc[fill_zero_mask, "value"] = 0

        if verbose:
            n_missing_after = int(out["value"].isna().sum())
            print(
                f"✓ Missing-value rules applied: filled {n_filled} NaNs with 0 "
                f"(count/rate metrics). Remaining NaNs: {n_missing_after} (duration/derived/unknown)."
            )

            # If any count/rate metrics are still NaN, they are probably not listed in metrics_config.yaml.
            remaining_count_rate = int((out["value"].isna() & out["metric_type"].isin(["count", "rate"])).sum())
            if remaining_count_rate > 0:
                print(
                    "⚠ Warning: Some count/rate rows are still NaN after filling. "
                    "This usually means those metrics are not listed in metrics_config.yaml."
                )

        return out

    # -------------------------
    # Master dataframe
    # -------------------------
    def create_master_dataframe(self, data_loader_func: Callable, verbose: bool = True) -> pd.DataFrame:
        """
        Create master long-format DataFrame from all discovered CSV files.

        Parameters
        ----------
        data_loader_func : callable
            Function(path) -> (df_wide, df_long)
            df_long must have columns: Metric, Well, Value (as in your loader)
        verbose : bool

        Returns
        -------
        pd.DataFrame
        """
        csv_files = self.discover_csv_files()
        all_data: List[pd.DataFrame] = []

        print("\n" + "=" * 60)
        print("LOADING AND ORGANIZING DATA")
        print("=" * 60)

        for time_point, csv_path in csv_files:
            if verbose:
                print(f"\nProcessing time point {time_point}: {csv_path.name}")

            try:
                df_wide, df_long = data_loader_func(csv_path)

                # Standardize column names from loader output
                df_long = df_long.rename(
                    columns={"Metric": "metric", "Well": "well", "Value": "value"}
                )

                # Clean well IDs
                df_long["well"] = df_long["well"].astype(str).str.strip().str.upper()

                # Add experiment metadata
                df_long["plate_id"] = self.plate_id
                df_long["time_point"] = time_point

                # Map condition (IMPORTANT: DO NOT fill missing with "Unused")
                df_long["condition"] = df_long["well"].map(self.well_to_condition)

                # Drop ignored wells if requested
                if self.drop_ignored_wells and self.ignore_wells:
                    df_long = df_long[~df_long["well"].isin(self.ignore_wells)].copy()

                # Add condition color (helps plotting consistency later)
                df_long["condition_color"] = df_long["condition"].map(self.condition_to_color)

                # Metric type classification (optional)
                if self.config_handler is not None:
                    df_long["metric_type"] = df_long["metric"].apply(self.config_handler.get_metric_type)
                else:
                    df_long["metric_type"] = "unknown"

                all_data.append(df_long)

                if verbose:
                    print(f"  ✓ Loaded {len(df_long)} rows")

            except Exception as e:
                print(f"  ✗ Error loading {csv_path.name}: {e}")

        if not all_data:
            raise ValueError("No data was successfully loaded.")

        master_df = pd.concat(all_data, ignore_index=True)
        
        # Apply missing-value rules centrally (count/rate -> 0, duration/derived -> NaN)
        master_df = self.apply_metric_missing_value_rules(master_df, verbose=verbose)

        # Reorder columns (stable schema for downstream)
        cols = [
            "plate_id",
            "time_point",
            "well",
            "condition",
            "condition_color",
            "metric",
            "value",
            "metric_type",
        ]
        # Keep only those that exist (defensive)
        cols = [c for c in cols if c in master_df.columns]
        self.master_df = master_df[cols].copy()

        print("\n" + "=" * 60)
        print("MASTER DATAFRAME CREATED")
        print("=" * 60)
        print(f"Total rows: {len(self.master_df)}")
        print(f"Unique time points: {self.master_df['time_point'].nunique()}")
        print(f"Unique metrics: {self.master_df['metric'].nunique()}")
        print(f"Unique wells: {self.master_df['well'].nunique()}")
        if "condition" in self.master_df.columns:
            print(f"Unique conditions (non-NaN): {self.master_df['condition'].dropna().nunique()}")
            print(f"Rows with unassigned condition (NaN): {int(self.master_df['condition'].isna().sum())}")
        print("=" * 60 + "\n")

        return self.master_df

    def get_master_dataframe(self) -> pd.DataFrame:
        if self.master_df is None:
            raise ValueError("Master DataFrame not created yet.")
        return self.master_df

    def save_master_dataframe(self, output_path: str | Path) -> None:
        if self.master_df is None:
            raise ValueError("Master DataFrame not created yet.")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.master_df.to_csv(output_path, index=False)
        print(f"✓ Saved master dataframe: {output_path}")
