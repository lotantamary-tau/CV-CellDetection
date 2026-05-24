# Project Overview

CV-CellDetection is a lab-internal toolkit for adapting [CaImAn](https://github.com/flatironinstitute/CaImAn)'s CNMF algorithm — originally built to detect neurons in two-photon calcium-imaging data — to detect **electrocytes** in our microscopy videos. The `cnmf_toolkit` subproject is a fork of the upstream CNMF code instrumented with per-stage debug hooks, so each step of the algorithm (init → spatial update → temporal update → merge → …) can be inspected interactively in napari while we tune it for the new cell type.

## Tech Stack & Environment

- **Language:** Python 3.12 (conda env: `cv-celldetection`)
- **Core libraries:** CaImAn, NumPy, SciPy, scikit-image, OpenCV, matplotlib, napari, h5py / pynwb
- **Notebook stack:** JupyterLab, ipywidgets
- **Optional:** Google Drive API (`google-api-python-client`, `google-auth-*`) for uploading per-stage debug outputs
- **Optional env vars** (only if using GDrive upload, see [cnmf_toolkit/GDRIVE_SETUP.md](cnmf_toolkit/GDRIVE_SETUP.md)):
  - `GDRIVE_FOLDER_ID`
  - `GDRIVE_SERVICE_ACCOUNT_KEY` (service-account flow) **or** `GDRIVE_CLIENT_SECRET` (OAuth flow)

## Key Directories & Architecture

| Path | Role |
|---|---|
| [cnmf_toolkit/](cnmf_toolkit/) | Forked CaImAn CNMF instrumented with debug hooks. The instrumentation layer that breaks CNMF into inspectable stages. |
| [cnmf_toolkit/instrumented_cnmf.py](cnmf_toolkit/instrumented_cnmf.py) | Main `CNMF` class — fork of upstream `caiman.source_extraction.cnmf.cnmf`, modified only to call `CNMFDebugTracker` between stages. |
| [cnmf_toolkit/debug_tracker.py:15](cnmf_toolkit/debug_tracker.py#L15) | `CNMFDebugTracker` — saves matrices (A, C, S, b, f, YrA), ROI PNGs, and metadata for each stage. Auto-generates a `run_id` timestamp at construction; phase-aware via `set_phase('fit'\|'refit')` so each CNMF invocation writes to its own `run_<ts>/<phase>/` subfolder. |
| [cnmf_toolkit/cnmf_manager.py](cnmf_toolkit/cnmf_manager.py) | `CNMFManager` — runs CNMF with named parameter configs (e.g. `greedy_roi_no_patches_config`, `corr_pnr_no_patches_config`). |
| [cnmf_toolkit/cnmf_runner.py](cnmf_toolkit/cnmf_runner.py) | CLI entry point for a single CNMF run. |
| [cnmf_toolkit/cnmf_viewer.py](cnmf_toolkit/cnmf_viewer.py) | Launches the napari stage-by-stage viewer. |
| [cnmf_toolkit/viewer/](cnmf_toolkit/viewer/) | Napari viewer subpackage (stage store, plotting, image utils). |
| [cnmf_toolkit/gdrive_uploader.py](cnmf_toolkit/gdrive_uploader.py) | Optional Google Drive upload of debug outputs. |
| [cnmf_toolkit/compare_pixels.py](cnmf_toolkit/compare_pixels.py) | Diagnostic CLI: compare raw fluorescence signals at two pixel locations side-by-side. |
| [notebooks/](notebooks/) | The notebooks the lab actually uses for electrocyte detection (production analysis lives here, not in the toolkit). |
| [`data/`](data/) | Folder structure (`RawData/`, `TaggedData/`, `results/debug_outputs/`, `results/hdf5/`) ships with the repo via `.gitkeep` markers — friends cloning don't need to create any folder. All actual content (TIFs, NPZs, HDF5s) is gitignored. See [data/README.md](data/README.md) for full layout. |
| `caiman_data/` | **Gitignored.** Installed via `caimanmanager install`; not project code. |
| `research/` | **Gitignored.** Reference papers (kept locally, not redistributed). |

See [.claude/docs/architectural_patterns.md](.claude/docs/architectural_patterns.md) for the staged-debug pattern, viewer plugin model, and config-naming scheme.

## Build & Test Commands

```bash
# Create the environment (one time)
conda env create -f environment.yml
conda activate cv-celldetection

# Install CaImAn sample data (one time, optional)
caimanmanager install

# Run CNMF on a movie. Writes per-stage debug data to
# data/results/debug_outputs/run_<TS>/fit/ (and refit/ from the notebook),
# and the final HDF5 to data/results/hdf5/.
cd cnmf_toolkit
python cnmf_runner.py path/to/movie.tif --config greedy_roi_no_patches_config

# Launch the napari viewer to inspect stages
python cnmf_viewer.py
```

No automated test suite exists yet. Validation is currently visual via the napari viewer and notebook outputs.

## Conventions & Anti-patterns

**Naming:** `snake_case` for modules, functions, and variables; `PascalCase` for classes (`CNMFDebugTracker`, `CNMFManager`, `GDriveUploader`). Filenames are descriptive (`cnmf_runner.py`, `debug_tracker.py`) — verbose over abbreviated.

**Patterns used:**
- **Forked-with-hooks:** [instrumented_cnmf.py](cnmf_toolkit/instrumented_cnmf.py) is a near-verbatim copy of upstream CaImAn CNMF; debug calls are inserted between stages but the algorithm logic is unchanged.
- **Staged debug capture:** `CNMFDebugTracker` writes per-stage snapshots to `data/results/debug_outputs/run_<TS>/<phase>/` where `<TS>` is auto-generated at construction and `<phase>` is `fit` or `refit`. Files: `{stage}.npz` (dense), `{stage}_A.npz` (sparse spatial), `metadata_{stage}.txt`. No counter suffix — the run/phase subfolder hierarchy discriminates between invocations. Set `set_phase('refit')` / `enable()` / `disable()` to control snapshot writing per phase (the notebook uses this for `DEBUG_FIT` / `DEBUG_REFIT` toggles; the runner inherits default `'fit'`).
- **Named-config runner:** `CNMFManager` exposes runs by config name rather than ad-hoc kwargs.
- **Lazy imports:** see [cnmf_toolkit/__init__.py:21](cnmf_toolkit/__init__.py#L21) — `__getattr__` defers `CNMFManager` import to avoid circular imports.

**Avoid:**
- **Don't modify upstream CaImAn algorithm logic** in [instrumented_cnmf.py](cnmf_toolkit/instrumented_cnmf.py). The whole point is to mirror upstream so we can isolate where electrocyte adaptation diverges. Add debug hooks; do not refactor the math.
- **Don't commit data or secrets.** TIF videos, GDrive credentials JSON, `.env` files, and `caiman_data/` are all out of git on purpose — keep them out.
- **Don't add heavy new dependencies casually.** The conda env is already large; new ML/CV libraries should be discussed before being added.
- **Don't use hyphens in Python module names.** (Past lesson: the file was once called `CaImAn-Visualizer.py`, which Python could not import. It's now `instrumented_cnmf.py`.)

## Maintenance

This file is a living document. Claude must update it automatically — without being asked — whenever any of the following occur:
- A new file or directory is added that changes the project structure
- A new dependency, library, or tool is introduced
- A build, test, or run command is established or changes
- An architectural pattern or convention is established or changed

Update only the affected section(s). Do not rewrite the whole file. Apply the same updates to [.claude/docs/architectural_patterns.md](.claude/docs/architectural_patterns.md) when relevant.

## Additional Documentation

- [.claude/docs/architectural_patterns.md](.claude/docs/architectural_patterns.md) — staged-debug pattern, napari viewer plugin model, named-config conventions, and the relationship between this fork and upstream CaImAn.
- [cnmf_toolkit/USAGE.md](cnmf_toolkit/USAGE.md) — operational guide: per-stage outputs, viewer keybindings, RAM-pressure recovery.
- [cnmf_toolkit/GDRIVE_SETUP.md](cnmf_toolkit/GDRIVE_SETUP.md) — Google Drive upload setup for debug outputs.
