# 🧠 MEA Analyzer – Axion MEA Data Processing Pipeline

A reproducible Python pipeline for cleaning, organizing, visualizing, normalizing, and statistically analyzing multi-electrode array (MEA) data generated with Axion Biosystems 24-well plates.

Designed for neuroscientists and biologists with minimal programming experience. Allows an intuitive experience with straight forwarded but robust data analysis and plotting.

## 📌 Project goals

This project provides tools to:

- Read Axion MEA Neural Metrics CSV files

- Clean and organize data across multiple time points

- Handle missing values correctly depending on metric type

- Assign wells to experimental conditions 

- Perform quality control & outlier detection 

- Apply baseline normalization

- Run time-point–based statistics 

- Export publication-ready tables and figures

- Export Prism-friendly CSVs for external analysis

## 📁 Project structure
```text
mea_project/
│
├── config/                         # Experiment & metrics configuration
│   ├── metrics_config.yaml         # Metric categories, types, missing-value rules
│   └── Plate_*.yaml                # Plate layout & condition assignment (user-defined)
│
├── data/
│   ├── raw/                        # Raw Axion CSVs (NOT tracked by git)
│   └── processed/                  # Optional exported / intermediate tables
│
├── notebooks/
│   └── mea_analyzer_v1.ipynb       # Main analysis notebook (entry point)
│
├── outputs/                        # Exported tables (stats, long-format data)
├── figures/                        # Saved figures (timecourses, layouts)
│
├── src/                            # Core analysis library
│   ├── data_loader.py              # Axion CSV parsing (Well Averages block)
│   ├── data_organizer.py           # Master dataframe creation & cleaning
│   ├── config_handler.py           # Metrics configuration logic
│   │
│   ├── utilities/                  # User-facing helper scripts
│   │   └── create_plate_config.py  # Interactive helper to generate Plate_*.yaml
│   │
│   ├── qc/
│   │   └── outliers.py             # Outlier detection & flagging
│   │
│   ├── analysis/
│   │   └── normalization.py        # Baseline normalization logic
│   │
│   ├── statistics/
│   │   └── timepoint_tests.py      # Condition comparisons at single time points
│   │
│   ├── visualization/
│   │   ├── plot_plate_layout.py    # Plate layout visualization
│   │   └── timecourse.py           # Metric time-course plotting utilities
│   │
│   └── io/
│       └── table_export.py         # Export to Prism / CSV formats
│
├── environment.yaml                # Conda environment specification
├── .gitignore                      # Excludes raw data, outputs, figures
└── README.md                       # Project overview & usage
```

## ⚙️ Environment setup

1. Create the conda environment (Anconda Prompt).
  ```  
  conda env create -f environment.yaml
  conda activate mea
  ```

2. Open jupyter lab from the project root directory

## 📊 Supported metrics

The pipeline currently supports the following Axion metrics:

- Number of Active Electrodes
- Number of Bursts
- Number of Network Bursts
- Weighted Mean Firing Rate (Hz)
- Burst Frequency - Avg (Hz)
- Network Burst Frequency
- Burst Duration - Avg (sec)
- Network Burst Duration - Avg (sec)
- Network IBI Coefficient of Variation
- Synchrony Index

Metric behavior (missing values, normalization rules) is defined in
config/metrics_config.yaml.

## 🧪 Experimental design assumptions

- Experimental unit = MEA plate

- Wells are technical replicates, not independent biological replicates

- Baseline is the first recording (file name starting with 0_)

- Wells with missing or zero baseline are excluded from normalization

- Outliers are detected within condition × time point × metric

## 📓 Main workflow (Notebook)

- All analysis is performed in:

- notebooks/mea_analyzer_v1.ipynb

- The notebook guides you through:

- Project setup & root detection

- Loading experiment configuration

- Plate layout visualization

- Data loading & master table construction

- Raw data visualization

- Outlier detection & QC

- Baseline normalization

- Time-point–based statistics

- Export of tables and figures

### 👉 Users do not need to modify source code — only the notebook and config files.

## 🧾 Exported outputs

- Tables

- Long-format master tables (outputs/)

- Wide, Prism-ready tables (data/processed/)

- Statistics tables (descriptives, omnibus, pairwise)

- Figures

- Raw time courses

- Normalized time courses

- Plate layout visualization

## 📤 Export of cleaned tables for GraphPad Prism

- One CSV per metric

- Rows = time points

- Columns = wells

- Raw and/or baseline-normalized values

- This allows direct import into Prism for further statistical analysis.

## 🛑 What is NOT included

- Spike-level data analysis

- Electrode-level spatial statistics

- Cross-plate mixed-effects modeling

- These are intentionally out of scope for the moment.

## 🧠 Scientific notes

- Outlier detection is descriptive/QC-oriented, not inferential

- Statistics are time-point–specific, avoiding invalid repeated-measures assumptions

- Normalization is optional and transparent

- All exclusions are explicitly tracked

## 📚 Documentation

- Non-programmers-friendly instructions for lab members: [Quickstart guide for lab users](docs/quickstart.md)

## 📜 License & authorship

This was developed as a project for the "Scientific Programming" course lectured by Dr. Renato Duarte (CNC - University of Coimbra)

For academic research use

Author: Vitor Bueno

Contributions: ChatGPT, Claude
