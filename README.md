# CV-CellDetection

Lab-internal toolkit for adapting [CaImAn](https://github.com/flatironinstitute/CaImAn)'s **CNMF** algorithm — originally designed to detect neurons from two-photon calcium-imaging data — to detect **electrocytes** in our microscopy videos.

The repo has two parts:

- **cnmf_toolkit** ([cnmf_toolkit/](cnmf_toolkit/)) — a fork of upstream CaImAn CNMF instrumented with per-stage debug hooks. It saves the intermediate matrices at every step of the algorithm (init → spatial update → temporal update → merge → …) and ships an interactive napari viewer so you can step through them. We use it to understand exactly where and how the original CNMF needs to be adapted for electrocytes.
- **Notebooks** ([notebooks/](notebooks/)) — the actual analysis the lab runs on its electrocyte recordings.

## Repository layout

```
CV-CellDetection/
├── cnmf_toolkit/            # Forked CNMF + per-stage debug + napari viewer
├── notebooks/               # Lab's electrocyte-detection analyses
├── data/                    # *mostly gitignored* — structure ships pre-built (RawData/, TaggedData/, results/), drop your TIFs in
├── environment.yml          # Conda environment spec
├── CLAUDE.md                # Project context for Claude Code
└── .claude/docs/            # Deeper architectural notes
```

## Setup

This project uses a conda environment.

### Prerequisite: conda installed and initialized for your shell

If you've never used conda, install [Miniconda](https://docs.anaconda.com/miniconda/) and then initialize it for your shell **once** (so `conda activate` is available):

```bash
conda init bash         # Linux/macOS bash
conda init zsh          # macOS zsh
conda init powershell   # Windows PowerShell
```

Restart your shell after running `conda init`. If you already use conda in other projects, this is already done — skip to the next step.

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

Drop TIF videos into `data/RawData/` and tagged ROIs into `data/TaggedData/`. The folder structure (including `results/` for CNMF outputs) is already there — you don't need to create anything. Actual data files are gitignored, so your recordings stay local.

## Running cnmf_toolkit

From the activated env:

```bash
cd cnmf_toolkit

# Run CNMF on a movie and save per-stage debug data
python cnmf_runner.py path/to/movie.tif --config greedy_roi_no_patches_config

# Then inspect the stages interactively in napari
python cnmf_viewer.py
```

The viewer is keyboard-driven: digit keys (1–8) switch between pipeline stages, click on an ROI to open a component-analysis plot. Full controls and per-stage output format are documented in [cnmf_toolkit/USAGE.md](cnmf_toolkit/USAGE.md).

## Optional: Google Drive offload of debug outputs

A long run can produce many gigabytes of per-stage matrices and PNGs. `CNMFDebugTracker` can upload them to Google Drive and (optionally) delete the local copies. See [cnmf_toolkit/GDRIVE_SETUP.md](cnmf_toolkit/GDRIVE_SETUP.md) for the env-var configuration.

## References

- Giovannucci et al., *CaImAn: An open source tool for scalable calcium imaging data analysis*, eLife 2019.
- Pnevmatikakis et al., *Simultaneous Denoising, Deconvolution, and Demixing of Calcium Imaging Data*, Neuron 2016.
