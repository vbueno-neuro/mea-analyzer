"""
Interactive Script to Create Experiment Configuration

This script helps users create experiment config files by asking simple questions.

Key features:
- Saves config ALWAYS into <project_root>/config/
- Validates wells (only A1–D6)
- Prevents a well being assigned to multiple conditions
- Time points: labels only (no numeric hours)
"""

import yaml
from pathlib import Path

# -------------------------
# Plate definition (Axion 24-well: A–D rows, 1–6 columns)
# -------------------------
ROWS = "ABCD"
COLS = range(1, 7)
VALID_WELLS = {f"{r}{c}" for r in ROWS for c in COLS}

# -------------------------
# Paths (assumes script is in: <project_root>/src/utilities/)
# If your script is elsewhere, adjust parents[...] accordingly.
# -------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


def _parse_wells(wells_input: str) -> list[str]:
    """
    Parse comma-separated wells, normalize to uppercase, validate.
    """
    wells = [w.strip().upper() for w in wells_input.split(",") if w.strip()]
    if not wells:
        raise ValueError("No wells provided.")

    invalid = set(wells) - VALID_WELLS
    if invalid:
        raise ValueError(
            f"Invalid well IDs: {sorted(invalid)}. "
            f"Valid wells are A1–D6."
        )

    # Remove duplicates within the same condition (keeps order)
    seen = set()
    deduped = []
    for w in wells:
        if w not in seen:
            deduped.append(w)
            seen.add(w)

    return deduped


def create_experiment_config():
    """Interactive config file creator"""

    print("=" * 70)
    print("MEA EXPERIMENT CONFIGURATION CREATOR")
    print("=" * 70)
    print("\nThis will help you create a configuration file for your experiment.")
    print("It will be saved into your project's /config folder.\n")

    config = {}

    # -------------------------
    # EXPERIMENT INFO
    # -------------------------
    print("\n--- EXPERIMENT INFORMATION ---")
    plate_id = input("Plate ID (e.g., Plate_001): ").strip()
    data_dir = input("Data directory path (e.g., data/raw/): ").strip()
    description = input("Experiment description (optional): ").strip()
    date = input("Experiment date (YYYY-MM-DD, optional): ").strip()

    config["experiment"] = {
        "plate_id": plate_id,
        "data_dir": data_dir,
    }
    if description:
        config["experiment"]["description"] = description
    if date:
        config["experiment"]["date"] = date

    # -------------------------
    # CONDITIONS
    # -------------------------
    print("\n--- EXPERIMENTAL CONDITIONS ---")
    while True:
        try:
            n_conditions = int(input("How many conditions? (e.g., 4): ").strip())
            if n_conditions <= 0:
                raise ValueError
            break
        except ValueError:
            print("⚠ Please enter a positive integer for number of conditions.")

    default_colors = [
        "#1f77b4",  # blue
        "#ff7f0e",  # orange
        "#2ca02c",  # green
        "#d62728",  # red
        "#9467bd",  # purple
        "#8c564b",  # brown
        "#e377c2",  # pink
        "#7f7f7f",  # gray
    ]

    conditions = {}
    used_wells = set()

    for i in range(n_conditions):
        print(f"\nCondition {i + 1}:")
        cond_name = input("  Name (e.g., Control, Drug_Low): ").strip()

        while True:
            wells_input = input("  Wells (comma-separated, e.g., A1,A2,A3): ").strip()
            try:
                wells = _parse_wells(wells_input)
            except ValueError as e:
                print(f"⚠ {e}")
                continue

            overlap = used_wells.intersection(wells)
            if overlap:
                print(
                    f"⚠ These wells are already assigned to another condition: "
                    f"{sorted(overlap)}"
                )
                print("  Please enter wells that are not already used.")
                continue

            break

        cond_desc = input("  Description (optional): ").strip()

        conditions[cond_name] = {
            "wells": wells,
            "color": default_colors[i % len(default_colors)],
        }
        if cond_desc:
            conditions[cond_name]["description"] = cond_desc

        used_wells.update(wells)
        print(f"  ✓ Added {len(wells)} wells to '{cond_name}'")

    config["conditions"] = conditions

    # -------------------------
    # UNUSED / IGNORED WELLS (optional)
    # -------------------------
    # These are typically wells that are intentionally empty or to be excluded.
    # Unassigned wells are *implicitly* unused, but this lets you explicitly mark
    # wells as "ignore" if you want a record.
    print("\n--- WELLS TO IGNORE (OPTIONAL) ---")
    ignore_input = input(
        "Enter wells to ignore (comma-separated) or press Enter to skip: "
    ).strip()

    if ignore_input:
        ignore_wells = _parse_wells(ignore_input)

        # Ensure ignored wells are not simultaneously assigned
        overlap_ignore = used_wells.intersection(ignore_wells)
        if overlap_ignore:
            raise ValueError(
                f"Ignored wells overlap with assigned wells: {sorted(overlap_ignore)}. "
                f"Either remove them from conditions or don't ignore them."
            )
        config["ignore_wells"] = ignore_wells
        print(f"  ✓ Marked {len(ignore_wells)} wells as ignored")

    # -------------------------
    # TIME POINTS (labels only)
    # -------------------------
    print("\n--- TIME POINTS ---")
    add_timepoints = input("Do you want to define time point labels? (y/n): ").strip().lower()

    if add_timepoints == "y":
        while True:
            try:
                n_timepoints = int(input("How many time points (including baseline)? ").strip())
                if n_timepoints <= 0:
                    raise ValueError
                break
            except ValueError:
                print("⚠ Please enter a positive integer for number of time points.")

        time_points = []
        print("\nFor each time point, enter a label used for plotting (e.g., Baseline, 15 min, 1h).")

        for i in range(n_timepoints):
            label = input(f"  Time point {i} label: ").strip()
            time_points.append({"index": i, "label": label})

        config["time_points"] = time_points

    # -------------------------
    # ANALYSIS SETTINGS (defaults)
    # Keep defaults here; can be edited later if you want.
    # -------------------------
    config["analysis"] = {
        "outlier_threshold": 3.0,
        "outlier_method": "zscore",
        "normalize_to_baseline": False,
    }

    # -------------------------
    # SAVE CONFIG (always to <project_root>/config)
    # -------------------------
    print("\n--- SAVING CONFIGURATION ---")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    default_filename = f"{plate_id}.yaml"
    filename = input(f"Save as (default: {default_filename}): ").strip() or default_filename
    output_path = CONFIG_DIR / filename

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # -------------------------
    # SUMMARY
    # -------------------------
    print("\n✓ Configuration saved to:")
    print(f"  {output_path.resolve()}")

    print("\n" + "=" * 70)
    print("CONFIGURATION SUMMARY")
    print("=" * 70)
    print(f"Plate ID: {plate_id}")
    print(f"Data directory: {data_dir}")
    print(f"Conditions: {len(conditions)}")
    for cond_name, cond_info in conditions.items():
        print(f"  - {cond_name}: {len(cond_info['wells'])} wells")
    if "ignore_wells" in config:
        print(f"Ignored wells: {len(config['ignore_wells'])} ({', '.join(config['ignore_wells'])})")
    if "time_points" in config:
        print(f"Time points: {len(config['time_points'])}")
    else:
        print("Time points: not specified")
    print("=" * 70)
    print("\nYou can now use this config file in your analysis, e.g.:")
    print(f"  organizer = DataOrganizer('{output_path.as_posix()}')")
    print("=" * 70)


if __name__ == "__main__":
    create_experiment_config()
