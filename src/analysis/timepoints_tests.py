"""
Time point utilities for MEA analysis.

Handles mapping of time_point indices to human-readable labels
for plotting (e.g., 0 -> Baseline, 1 -> 1h, 2 -> 24h).
"""

from pathlib import Path
import yaml


def load_timepoint_labels(experiment_config_path):
    """
    Load time point labels from experiment_config.yaml.

    Expected YAML structure (optional):

    time_points:
      - index: 0
        label: "Baseline"
      - index: 1
        label: "1h"
      - index: 2
        label: "24h"

    Parameters
    ----------
    experiment_config_path : str or Path

    Returns
    -------
    dict[int, str]
        Mapping from time_point index to label.
        Returns empty dict if no time_points are defined.
    """
    experiment_config_path = Path(experiment_config_path)

    if not experiment_config_path.exists():
        raise FileNotFoundError(f"Config file not found: {experiment_config_path}")

    with open(experiment_config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    time_points = config.get("time_points", None)
    if not time_points:
        return {}

    labels = {}
    for tp in time_points:
        idx = int(tp["index"])
        label = str(tp["label"])
        labels[idx] = label

    return labels
