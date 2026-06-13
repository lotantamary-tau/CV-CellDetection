# CV-CellDetection

Lab-internal toolkit for adapting [CaImAn](https://github.com/flatironinstitute/CaImAn)'s **CNMF** algorithm — originally designed to detect neurons from two-photon calcium-imaging data — to detect **electrocytes** in our microscopy videos.

The repo has two parts:

- **cnmf_toolkit** ([cnmf_toolkit/](cnmf_toolkit/)) — a fork of upstream CaImAn CNMF instrumented with per-stage debug hooks. It saves the intermediate matrices at every step of the algorithm (init → spatial update → temporal update → merge → …) and ships an interactive napari viewer so you can step through them. We use it to understand exactly where and how the original CNMF needs to be adapted for electrocytes.
- **Notebooks** ([notebooks/](notebooks/)) — the actual analysis the lab runs on its electrocyte recordings.

## Repository layout

```
CV-CellDetection/
├── cnmf_toolkit/            # Forked CNMF + per-stage debug hooks + napari viewer
│   ├── cnmf_runner.py       #   run CNMF on a movie (CLI)
│   ├── cnmf_viewer.py       #   launch the napari stage-by-stage viewer (CLI)
│   ├── instrumented_cnmf.py #   upstream CNMF, instrumented with debug hooks
│   ├── debug_tracker.py     #   writes per-stage snapshots
│   ├── cnmf_manager.py      #   named-config runner
│   ├── viewer/              #   napari viewer sub-package
│   └── USAGE.md             #   operational guide + full keymap
├── notebooks/               # Lab's electrocyte-detection analyses
├── data/                    # content gitignored — but the folder structure ships pre-built:
│   ├── RawData/             #   drop your .tif movies here
│   ├── TaggedData/          #   manual ROI annotations
│   └── results/
│       ├── debug_outputs/   #   per-run, per-stage matrices (run_<ts>/<phase>/)
│       └── hdf5/            #   final CNMF results
├── environment.yml          # One-command conda env: cv-celldetection
├── README.md                # This file
├── CHANGELOG.md             # Per-PR history of what changed on main
├── FUTURE_TASKS.md          # Backlog of low-priority improvements
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

From the activated env, `cd cnmf_toolkit` first.

### Step 1 — produce per-stage debug data

There are **two ways** to generate the stage snapshots the viewer reads. Both write to the same place and feed the same viewer:

**a) Runner — one command, headless.** Best for a quick, repeatable run with a named config:

```bash
python cnmf_runner.py "../data/RawData/your_movie.tif" --config greedy_roi_no_patches_config
```

Runs no-patches, `fit` phase only.

**b) Notebook — your normal analysis.** In [the analysis notebook](notebooks/OPCal_cell%20detection_caiman_150226.ipynb), flip the two toggles near the top (the "Imports and general setup" cell), then run the notebook as usual:

```python
DEBUG_FIT = True     # capture the initial (patches-mode) fit
DEBUG_REFIT = True   # capture the refit
```

With both left `False` (the default), the notebook behaves byte-identically to upstream CaImAn — nothing is written.

Either way, each run lands in its own folder — `data/results/debug_outputs/run_<timestamp>/<phase>/`, where `<phase>` is `fit` or `refit` — so runs never overwrite each other.

### Step 2 — inspect the stages in napari

```bash
python cnmf_viewer.py
```

The viewer auto-discovers every run/phase/stage on disk. It is keyboard-driven, scoped coarse → fine, and **all navigation wraps** at the edges:

| Key | Action |
|---|---|
| `F1` / `F2` | previous / next **run** |
| `F3` / `F4` | previous / next **phase** (fit ↔ refit) |
| `F5` / `F6` | previous / next **stage** (within the phase) |
| `Ctrl+1`..`Ctrl+9` | jump directly to the Nth stage in the current phase |
| `S` | print the "you are here" map (runs / phases / stages) to the terminal |
| `I` | print component info to the terminal |
| `SPACE` | analyze the ROI under the cursor (opens a component-analysis plot) |

A couple of rules worth knowing: switching run or phase always lands you on the `final` stage (a consistent starting point), and **mouse-click is not bound** — napari's pan/zoom owns it, so hover a cell and press `SPACE` to inspect it. Full keymap and per-stage output format: [cnmf_toolkit/USAGE.md](cnmf_toolkit/USAGE.md).

## Optional: Google Drive offload of debug outputs

A long run can produce many gigabytes of per-stage matrices and PNGs. `CNMFDebugTracker` can upload them to Google Drive and (optionally) delete the local copies. See [cnmf_toolkit/GDRIVE_SETUP.md](cnmf_toolkit/GDRIVE_SETUP.md) for the env-var configuration.

## References

- Giovannucci et al., *CaImAn: An open source tool for scalable calcium imaging data analysis*, eLife 2019.
- Pnevmatikakis et al., *Simultaneous Denoising, Deconvolution, and Demixing of Calcium Imaging Data*, Neuron 2016.
