# CV-CellDetection

Lab-internal toolkit for adapting [CaImAn](https://github.com/flatironinstitute/CaImAn)'s **CNMF** algorithm — originally designed to detect neurons from two-photon calcium-imaging data — to detect **electrocytes** in our microscopy videos.

The repo has two parts:

- **CaImAn-Visualizer** ([Lab/CaImAn-Visualizer/](Lab/CaImAn-Visualizer/)) — a fork of upstream CaImAn CNMF instrumented with per-stage debug hooks. It saves the intermediate matrices at every step of the algorithm (init → spatial update → temporal update → merge → …) and ships an interactive napari viewer so you can step through them. We use it to understand exactly where and how the original CNMF needs to be adapted for electrocytes.
- **Notebooks** ([Lab/notebooks/](Lab/notebooks/)) — the actual analysis the lab runs on its electrocyte recordings.

## Repository layout

```
CV-CellDetection/
├── Lab/
│   ├── CaImAn-Visualizer/   # Forked CNMF + per-stage debug + napari viewer
│   ├── notebooks/           # Lab's electrocyte-detection analyses
│   └── data/                # *gitignored* — local TIF videos and ROI tags
├── environment.yml          # Conda environment spec
├── CLAUDE.md                # Project context for Claude Code
└── .claude/docs/            # Deeper architectural notes
```

## Setup

This project uses a conda environment.

### 1. Create the environment

```bash
conda env create -f environment.yml
conda activate cv-celldetection
```

This installs CaImAn and all visualization dependencies pinned to the versions used during development.

### 2. Install CaImAn sample data (optional)

CaImAn ships sample movies used in some demos. After activating the env:

```bash
caimanmanager install
```

This populates a local `caiman_data/` folder (not committed to this repo).

### 3. Add your own data

Drop TIF videos into `Lab/data/RawData/` and tagged ROIs into `Lab/data/TaggedData/`. The repository ignores `Lab/data/` so your recordings stay local.

## Running CaImAn-Visualizer

From the activated env:

```bash
cd Lab/CaImAn-Visualizer

# Run CNMF on a movie and save per-stage debug data
python cnmf_runner.py path/to/movie.tif --config greedy_roi_no_patches_config

# Then inspect the stages interactively in napari
python interactive_cnmf_viewer.py
```

The viewer is keyboard-driven: digit keys (1–8) switch between pipeline stages, click on an ROI to open a component-analysis plot. Full controls and per-stage output format are documented in [Lab/CaImAn-Visualizer/MISSION_SUMMARY.txt](Lab/CaImAn-Visualizer/MISSION_SUMMARY.txt).

## Optional: Google Drive offload of debug outputs

A long run can produce many gigabytes of per-stage matrices and PNGs. `CNMFDebugTracker` can upload them to Google Drive and (optionally) delete the local copies. See [Lab/CaImAn-Visualizer/GDRIVE_SETUP.md](Lab/CaImAn-Visualizer/GDRIVE_SETUP.md) for the env-var configuration.

## References

- Giovannucci et al., *CaImAn: An open source tool for scalable calcium imaging data analysis*, eLife 2019.
- Pnevmatikakis et al., *Simultaneous Denoising, Deconvolution, and Demixing of Calcium Imaging Data*, Neuron 2016.
