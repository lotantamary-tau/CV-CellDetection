# Project Overview

CV-CellDetection is a lab-internal toolkit for adapting [CaImAn](https://github.com/flatironinstitute/CaImAn)'s CNMF algorithm — originally built to detect neurons in two-photon calcium-imaging data — to detect **electrocytes** in our microscopy videos. The CaImAn-Visualizer subproject is a fork of the upstream CNMF code instrumented with per-stage debug hooks, so each step of the algorithm (init → spatial update → temporal update → merge → …) can be inspected interactively in napari while we tune it for the new cell type.

## Tech Stack & Environment

- **Language:** Python 3.12 (conda env: `cv-celldetection`)
- **Core libraries:** CaImAn, NumPy, SciPy, scikit-image, OpenCV, matplotlib, napari, h5py / pynwb
- **Notebook stack:** JupyterLab, ipywidgets
- **Optional:** Google Drive API (`google-api-python-client`, `google-auth-*`) for uploading per-stage debug outputs
- **Optional env vars** (only if using GDrive upload, see [Lab/CaImAn-Visualizer/GDRIVE_SETUP.md](Lab/CaImAn-Visualizer/GDRIVE_SETUP.md)):
  - `GDRIVE_FOLDER_ID`
  - `GDRIVE_SERVICE_ACCOUNT_KEY` (service-account flow) **or** `GDRIVE_CLIENT_SECRET` (OAuth flow)

## Key Directories & Architecture

| Path | Role |
|---|---|
| [Lab/CaImAn-Visualizer/](Lab/CaImAn-Visualizer/) | Forked CaImAn CNMF instrumented with debug hooks. The visualization layer that breaks CNMF into inspectable stages. |
| [Lab/CaImAn-Visualizer/CaImAn-Visualizer.py](Lab/CaImAn-Visualizer/CaImAn-Visualizer.py) | Main `CNMF` class — fork of upstream `caiman.source_extraction.cnmf.cnmf`, modified only to call `CNMFDebugTracker` between stages. |
| [Lab/CaImAn-Visualizer/debug_tracker.py:15](Lab/CaImAn-Visualizer/debug_tracker.py#L15) | `CNMFDebugTracker` — saves matrices (A, C, S, b, f, YrA), ROI PNGs, and metadata for each stage. |
| [Lab/CaImAn-Visualizer/cnmf_manager.py](Lab/CaImAn-Visualizer/cnmf_manager.py) | `CNMFManager` — runs CNMF with named parameter configs (e.g. `greedy_roi_no_patches_config`, `corr_pnr_no_patches_config`). |
| [Lab/CaImAn-Visualizer/cnmf_runner.py](Lab/CaImAn-Visualizer/cnmf_runner.py) | CLI entry point for a single CNMF run. |
| [Lab/CaImAn-Visualizer/interactive_cnmf_viewer.py](Lab/CaImAn-Visualizer/interactive_cnmf_viewer.py) | Launches the napari stage-by-stage viewer. |
| [Lab/CaImAn-Visualizer/Visualizer/](Lab/CaImAn-Visualizer/Visualizer/) | Napari viewer subpackage (stage store, plotting, image utils). |
| [Lab/CaImAn-Visualizer/gdrive_uploader.py](Lab/CaImAn-Visualizer/gdrive_uploader.py) | Optional Google Drive upload of debug outputs. |
| [Lab/notebooks/](Lab/notebooks/) | The notebooks the lab actually uses for electrocyte detection (production analysis lives here, not in the visualizer fork). |
| `Lab/data/` | **Gitignored.** Local TIF videos (`RawData/`) and tagged ROIs (`TaggedData/`). |
| `caiman_data/` | **Gitignored.** Installed via `caimanmanager install`; not project code. |
| `reserch/` | **Gitignored.** Reference papers (kept locally, not redistributed). |

See [.claude/docs/architectural_patterns.md](.claude/docs/architectural_patterns.md) for the staged-debug pattern, viewer plugin model, and config-naming scheme.

## Build & Test Commands

```bash
# Create the environment (one time)
conda env create -f environment.yml
conda activate cv-celldetection

# Install CaImAn sample data (one time, optional)
caimanmanager install

# Run CNMF on a movie (writes per-stage debug data to cnmf_debug_outputs/)
cd Lab/CaImAn-Visualizer
python cnmf_runner.py path/to/movie.tif --config greedy_roi_no_patches_config

# Launch the napari viewer to inspect stages
python interactive_cnmf_viewer.py
```

No automated test suite exists yet. Validation is currently visual via the napari viewer and notebook outputs.

## Conventions & Anti-patterns

**Naming:** `snake_case` for modules, functions, and variables; `PascalCase` for classes (`CNMFDebugTracker`, `CNMFManager`, `GDriveUploader`). Filenames are descriptive (`cnmf_runner.py`, `debug_tracker.py`) — verbose over abbreviated.

**Patterns used:**
- **Forked-with-hooks:** [CaImAn-Visualizer.py](Lab/CaImAn-Visualizer/CaImAn-Visualizer.py) is a near-verbatim copy of upstream CaImAn CNMF; debug calls are inserted between stages but the algorithm logic is unchanged.
- **Staged debug capture:** `CNMFDebugTracker.save_stage(name, ...)` writes `{stage}_0.npz` + `{stage}_0_A.npz` (sparse) + `metadata_{stage}_0.txt` per pipeline step.
- **Named-config runner:** `CNMFManager` exposes runs by config name rather than ad-hoc kwargs.
- **Lazy imports:** see [Lab/CaImAn-Visualizer/__init__.py:20](Lab/CaImAn-Visualizer/__init__.py#L20) — `__getattr__` defers `CNMFManager` import to avoid circular imports.

**Avoid:**
- **Don't modify upstream CaImAn algorithm logic** in [CaImAn-Visualizer.py](Lab/CaImAn-Visualizer/CaImAn-Visualizer.py). The whole point is to mirror upstream so we can isolate where electrocyte adaptation diverges. Add debug hooks; do not refactor the math.
- **Don't commit data or secrets.** TIF videos, GDrive credentials JSON, `.env` files, and `caiman_data/` are all out of git on purpose — keep them out.
- **Don't add heavy new dependencies casually.** The conda env is already large; new ML/CV libraries should be discussed before being added.
- **Don't use hyphens in Python module names.** The folder is `CaImAn-Visualizer/` (legacy name) but Python imports inside it must use sibling-style imports (`from debug_tracker import ...`) — never `from CaImAn-Visualizer import ...`.

## Maintenance

This file is a living document. Claude must update it automatically — without being asked — whenever any of the following occur:
- A new file or directory is added that changes the project structure
- A new dependency, library, or tool is introduced
- A build, test, or run command is established or changes
- An architectural pattern or convention is established or changed

Update only the affected section(s). Do not rewrite the whole file. Apply the same updates to [.claude/docs/architectural_patterns.md](.claude/docs/architectural_patterns.md) when relevant.

## Additional Documentation

- [.claude/docs/architectural_patterns.md](.claude/docs/architectural_patterns.md) — staged-debug pattern, napari viewer plugin model, named-config conventions, and the relationship between this fork and upstream CaImAn.
- [Lab/CaImAn-Visualizer/MISSION_SUMMARY.txt](Lab/CaImAn-Visualizer/MISSION_SUMMARY.txt) — operational guide: per-stage outputs, viewer keybindings, RAM-pressure recovery.
- [Lab/CaImAn-Visualizer/GDRIVE_SETUP.md](Lab/CaImAn-Visualizer/GDRIVE_SETUP.md) — Google Drive upload setup for debug outputs.
