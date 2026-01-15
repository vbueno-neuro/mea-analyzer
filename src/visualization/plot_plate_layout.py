"""
Plate layout visualizer for 24-well MEA plates (A1–D6).
"""

from __future__ import annotations

from pathlib import Path
import yaml
import matplotlib.pyplot as plt
import matplotlib.patches as patches


ROWS = ["A", "B", "C", "D"]
COLS = [1, 2, 3, 4, 5, 6]
ALL_WELLS = {f"{r}{c}" for r in ROWS for c in COLS}


def plot_plate_layout(
    experiment_config_path,
    *,
    show_condition_text: bool = True,
    condition_label_map: dict[str, str] | None = None,
    condition_fontsize: int = 8,
    well_fontsize: int = 8,
):
    """
    Plot a 24-well plate layout based on experiment configuration.

    Parameters
    ----------
    experiment_config_path : str | Path
        Path to experiment_config.yaml
    show_condition_text : bool
        If True, shows a short condition label inside wells (recommended).
        If False, only shows well IDs (cleanest).
    condition_label_map : dict[str,str] | None
        Optional mapping from full condition name -> short label.
        If None, short label is auto-generated from the condition name.
    """

    experiment_config_path = Path(experiment_config_path)

    with open(experiment_config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    conditions = config["conditions"]

    # Build well->condition and condition->color maps
    well_to_condition = {}
    condition_colors = {}

    for cond_name, cond_info in conditions.items():
        condition_colors[cond_name] = cond_info["color"]
        for well in cond_info["wells"]:
            if well in well_to_condition:
                raise ValueError(f"Well {well} assigned to multiple conditions.")
            well_to_condition[well] = cond_name

    used_wells = set(well_to_condition.keys())
    unused_wells = ALL_WELLS - used_wells

    # Auto short labels (fallback)
    def _auto_label(name: str) -> str:
        # Simple readable compression; user can override via condition_label_map
        s = name.replace("filtered", "F").replace("unfiltered", "U")
        s = s.replace("  ", " ").strip()
        # keep it short-ish
        return s if len(s) <= 12 else s[:12] + "…"

    def _label_for(cond_name: str) -> str:
        if condition_label_map and cond_name in condition_label_map:
            return condition_label_map[cond_name]
        return _auto_label(cond_name)

    fig, ax = plt.subplots(figsize=(9, 6))

    # Draw wells
    for row_idx, row in enumerate(ROWS):
        for col_idx, col in enumerate(COLS):
            well_id = f"{row}{col}"
            x = col_idx
            y = len(ROWS) - row_idx - 1  # invert y-axis so A is top row

            if well_id in used_wells:
                cond = well_to_condition[well_id]
                color = condition_colors[cond]
                rect = patches.Rectangle((x, y), 1, 1, facecolor=color, edgecolor="black")
                ax.add_patch(rect)

                # Optional short condition label (center)
                if show_condition_text:
                    ax.text(
                        x + 0.5,
                        y + 0.45,
                        _label_for(cond),
                        ha="center",
                        va="center",
                        fontsize=condition_fontsize,
                        color="black",
                        clip_on=True,
                    )

            else:
                rect = patches.Rectangle(
                    (x, y), 1, 1,
                    facecolor="lightgray",
                    edgecolor="black",
                    hatch="///"
                )
                ax.add_patch(rect)

            # Well label (top-left)
            ax.text(
                x + 0.04,
                y + 0.96,
                well_id,
                ha="left",
                va="top",
                fontsize=well_fontsize,
                color="black",
                clip_on=True,
            )

    # Formatting
    ax.set_xlim(0, len(COLS))
    ax.set_ylim(0, len(ROWS))
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"Plate Layout — {config['experiment']['plate_id']}", fontsize=14)

    # Legend (full condition names)
    legend_patches = [
        patches.Patch(facecolor=color, label=name)
        for name, color in condition_colors.items()
    ]
    legend_patches.append(patches.Patch(facecolor="lightgray", hatch="///", label="Unused"))

    ax.legend(handles=legend_patches, bbox_to_anchor=(1.02, 1), loc="upper left")

    plt.tight_layout()

    # IMPORTANT: no plt.show() here to avoid duplicate display in Jupyter
    return fig, ax
