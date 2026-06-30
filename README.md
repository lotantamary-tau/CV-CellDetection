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
│   ├── ground_truth_scorer.py #  score a run vs manual tags + overlay PNG (CLI)
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
│       ├── comparisons/     #   ground-truth-scorer overlay PNGs
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

## Running the detection (the one required step)

Run CNMF on a movie. This is the **only required step** — it produces the per-stage output that the optional tools further down read. From the activated env, `cd cnmf_toolkit` first.

There are **two ways** to run; both write to the same place:

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

## Optional tools — inspect or score a run

After a run, **two independent tools** read its output. They are **separate and optional** — use either, both, or neither, and **neither one needs the other** (the scorer does *not* require the viewer). Both just need a run to exist; the scorer also needs a manual annotation.

### Tool A — view the stages in napari (the viewer)

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

### Tool B — score a run against your manual tags (the ground-truth scorer)

```bash
python ground_truth_scorer.py --annotation ../data/TaggedData/your_tags.tif
```

`--annotation` points to your **manual ground-truth file** — the hand-made tag image (your "answer key" for where the real cells are). It is a **single `.tif` file** inside `data/TaggedData/`; replace `your_tags.tif` with the actual file name for the recording you scored (e.g. `20250409_3_Glut_1mM_ROI_AllCells.tif`).

The scorer overlays the detected cells on that annotation and reports, for the run, how many cells were detected **correctly** vs **merged** (one detection over several cells), **split** (several detections on one cell), **junk** (a detection on no cell), and **missed** — plus a color-coded overlay PNG saved to `data/results/comparisons/`. It scores the most recent run by default (`--run <id>` for a specific one, `--stage refit/final` to pick a stage, `--no-plot` for counts only).

> **Accuracy — version 1.** It treats the annotation as a binary mask and separates touching cells with a watershed heuristic, so the numbers are reliable for **comparing runs/configs against each other**, but are **not** exact per-cell accuracy. Exact accuracy (per-cell IoU/Dice) needs a **per-cell labelled** annotation (each cell its own label) — the planned v2. Details: [cnmf_toolkit/USAGE.md](cnmf_toolkit/USAGE.md).

## Optional: Google Drive offload of debug outputs

A long run can produce many gigabytes of per-stage matrices and PNGs. `CNMFDebugTracker` can upload them to Google Drive and (optionally) delete the local copies. See [cnmf_toolkit/GDRIVE_SETUP.md](cnmf_toolkit/GDRIVE_SETUP.md) for the env-var configuration.

## References

- Giovannucci et al., *CaImAn: An open source tool for scalable calcium imaging data analysis*, eLife 2019.
- Pnevmatikakis et al., *Simultaneous Denoising, Deconvolution, and Demixing of Calcium Imaging Data*, Neuron 2016.
