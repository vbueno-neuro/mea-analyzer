import csv
import pandas as pd
from pathlib import Path
from io import StringIO

WELL_IDS = [f"{r}{c}" for r in "ABCD" for c in range(1, 7)]


def load_mea_csv_well_averages(csv_path, verbose=True, return_long=True):
    """
    Load the 'Well Averages' block from an Axion MEA Neural Metrics CSV file.

    Robust parsing rules:
    - Find the row whose first cell is "Well Averages"
    - Use that row to define the well columns
    - Read subsequent rows until:
        (a) a blank line, OR
        (b) the next major section starts (e.g., first cell == "Measurement")
    - Skip section header rows like "Activity Metrics" that have no data cells
    - Ignore the "Treatment/ID" row
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} not found")

    # Use utf-8-sig to safely handle BOM (common in Axion exports)
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    # --- Find "Well Averages" header row ---
    start_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip() == "Well Averages":
            start_idx = i
            break
    if start_idx is None:
        raise ValueError("'Well Averages' not found")

    header_row = rows[start_idx]

    # wells are the non-empty cells after the first
    wells = [c.strip() for c in header_row[1:] if c.strip() != ""]
    if not wells:
        raise ValueError("Found 'Well Averages' but could not parse well IDs from header row.")

    if verbose:
        print(f"'Well Averages' found at row {start_idx}. Parsed {len(wells)} wells.")

    # --- Collect metric rows until block ends ---
    metric_names = []
    metric_values = []

    def is_blank_row(r):
        return (not r) or all((c.strip() == "" for c in r))

    for row in rows[start_idx + 1 :]:
        if is_blank_row(row):
            # Well Averages block usually ends at the first truly blank line
            break

        first = (row[0] if row else "").strip()

        # stop if next major section begins
        if first == "Measurement":
            break

        # skip treatment/ID row
        if first == "Treatment/ID":
            continue

        # Determine if the row actually has data cells
        data_cells = [c.strip() for c in row[1:] if c.strip() != ""]
        if len(data_cells) == 0:
            # This catches section headers like "Activity Metrics", etc.
            continue

        # Metric name (strip indentation if present)
        metric = first

        # Take only as many values as wells, pad if short
        vals = row[1 : 1 + len(wells)]
        if len(vals) < len(wells):
            vals = vals + [""] * (len(wells) - len(vals))

        metric_names.append(metric)
        metric_values.append(vals)

    if len(metric_names) == 0:
        raise ValueError("Well Averages section found, but no metric rows were parsed.")

    # --- Build wide dataframe ---
    df_wide = pd.DataFrame(metric_values, columns=wells)
    df_wide.insert(0, "Metric", metric_names)

    # Convert numeric columns
    for col in df_wide.columns[1:]:
        df_wide[col] = pd.to_numeric(df_wide[col], errors="coerce")

    if verbose:
        print(f"Loaded {df_wide.shape[0]} metrics for {len(wells)} wells")

    if return_long:
        df_long = df_wide.melt(id_vars=["Metric"], var_name="Well", value_name="Value")
        return df_wide, df_long

    return df_wide