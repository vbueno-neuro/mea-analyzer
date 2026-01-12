import pandas as pd
from pathlib import Path
from io import StringIO

WELL_IDS = [f"{r}{c}" for r in "ABCD" for c in range(1, 7)]

def load_mea_csv_well_averages(csv_path, verbose=True, return_long=True):
    """
    Load the 'Well Averages' block from an Axion MEA CSV file,
    ignoring the Treatment/ID row below the header.
    
    Parameters
    ----------
    csv_path : str or Path
        Path to the CSV file.
    verbose : bool
        Whether to print info.
    return_long : bool
        If True, also return a long-format DataFrame.
    
    Returns
    -------
    df_wide : pd.DataFrame
        Wide-format DataFrame with Metric as first column, wells as remaining columns.
    df_long : pd.DataFrame, optional
        Long-format DataFrame with columns ['Metric', 'Well', 'Value'] if return_long=True.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} not found")
    
    # --- Step 1: read all lines ---
    with open(csv_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f]
    
    # --- Step 2: find the 'Well Averages' row ---
    start_idx = next((i for i, line in enumerate(lines) if line.startswith("Well Averages")), None)
    if start_idx is None:
        raise ValueError("'Well Averages' not found")
    
    if verbose:
        print(f"'Well Averages' found at line {start_idx}")
    
    # --- Step 3: header and skip Treatment/ID row ---
    header_line = lines[start_idx]
    header = [h.strip() for h in header_line.split(",")]
    
    # rename first column to Metric
    header[0] = "Metric"
    
    # --- Step 4: find end row (first 'Synchrony Index') ---
    end_idx = next((i for i, line in enumerate(lines[start_idx+2:], start=start_idx+2)
                    if line.split(',')[0].strip() == "Synchrony Index"), None)
    if end_idx is None:
        raise ValueError("'Synchrony Index' not found after 'Well Averages'")
    
    # --- Step 5: extract data block ---
    data_lines = lines[start_idx+2 : end_idx+1]  # skip Treatment/ID row
    csv_block = "\n".join([",".join(line.split(",")) for line in data_lines])
    
    # --- Step 6: load into DataFrame ---
    df_wide = pd.read_csv(StringIO(csv_block), header=None)
    df_wide.columns = header
    
    # --- Step 7: convert numeric columns ---
    for col in df_wide.columns[1:]:
        df_wide[col] = pd.to_numeric(df_wide[col], errors='coerce')
        if verbose:
            n_missing = df_wide[col].isna().sum()
            if n_missing > 0:
                print(f"Warning: {n_missing} missing values in column {col}")
    
    if verbose:
        print(f"Loaded {len(df_wide)} metrics for {len(df_wide.columns)-1} wells")
    
    if return_long:
        df_long = df_wide.melt(id_vars=["Metric"], var_name="Well", value_name="Value")
        return df_wide, df_long
    
    return df_wide
