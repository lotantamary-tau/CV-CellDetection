# Changelog

All notable changes to CV-CellDetection, in reverse chronological order. Each top-level entry corresponds to a merged PR. New entries get added when work merges to `main`.

Format loosely follows [Keep a Changelog](https://keepachangelog.com): each PR has Added / Changed / Fixed / Documentation sections. For the exact diff of any entry, see the referenced merge commit on GitHub.

---

## [2026-05-24] PR #3 — Multi-run isolation + fit/refit phase + new viewer keymap

Merge commit: [`90008e5`](https://github.com/lotantamary-tau/CV-CellDetection/commit/90008e5). Resolved FUTURE_TASKS items #2, #3, #4.

### Added

- **Multi-run output hierarchy.** Every CNMF invocation writes to its own timestamped folder: `data/results/debug_outputs/run_<TS>/<phase>/<stage>.npz`. Runs never silently overwrite each other anymore.
- **Phase-aware tracker API.** `CNMFDebugTracker.set_phase(name)`, `enable()`, `disable()`. Constructor auto-generates a `run_id` timestamp; `default_phase='fit'`.
- **Notebook DEBUG_FIT / DEBUG_REFIT toggles.** Two booleans at the top of `notebooks/OPCal_cell detection_caiman_150226.ipynb`, both default `False` (byte-identical to upstream behavior). When True, the notebook imports CNMF from `cnmf_toolkit/instrumented_cnmf.py` via `sys.path.insert` and snapshots are written to the corresponding `run_<TS>/fit/` and/or `run_<TS>/refit/` subfolder.
- **New viewer keymap** (paired prev/next, ordered coarse-to-fine, all circular):
  - F1/F2 = previous/next run
  - F3/F4 = previous/next phase (fit ↔ refit)
  - F5/F6 = previous/next stage (within current phase)
  - Ctrl+1..Ctrl+9 = direct jump to Nth stage in current phase
- **Dynamic stage discovery.** Viewer's `StageStore` scans whatever `.npz` files exist on disk instead of a hardcoded list. Handles patches-mode stages (notebook initial fit: `patches_init`, `patches_merge`, `patches_temporal`, `final`) AND non-patches stages (runner / notebook refit: `preprocess`, `init`, `spatial_1`, `temporal_1`, `merge`, `spatial_2`, `temporal_2`, `final`) without code changes.
- **Terminal "you are here" map.** `print_stage_info()` shows three sections in coarse-to-fine order: runs, phases, stages (numbered `1)`, `2)`, … for the Ctrl+N jump). Current selection marked `>>`.

### Changed

- Tracker output filenames dropped the `_N` counter — the `run_<TS>/<phase>/` subfolder hierarchy now discriminates between invocations.
- `STAGE_DEFINITIONS` in `viewer/__init__.py` is now optional display metadata (was an authoritative list of 8 hardcoded stages). Unknown stages still appear in the viewer with bare names + `order=999`.
- **Policy B reset semantics.** Switching run ALWAYS resets phase to refit (if present) else fit, and stage to final (else last). Switching phase ALWAYS resets stage to final. Switching stage just changes stage. Predictable consistent landing.

### Fixed

- Bare digit keys `1` and `2` were silently intercepted by napari's layer-mode shortcuts at the Qt event level (`overwrite=True` couldn't recover them). F-keys have no such conflict.
- Memory leak — switching run/phase previously left old `StageEntry` matrices loaded in RAM. Now sweep-unloads all entries on switch; exactly one stage loaded at a time.

### Documentation

- All docs aligned to the final state: `CLAUDE.md`, `README.md`, `cnmf_toolkit/USAGE.md`, `data/README.md`, `FUTURE_TASKS.md`, `cnmf_toolkit/GDRIVE_SETUP.md`, `.claude/docs/architectural_patterns.md`.

### Known intentional non-features

- Mouse click on an ROI is NOT bound — napari's pan/zoom mode intercepts mouse clicks at the layer level. Use SPACE for ROI analysis. Double-clicking still zooms (napari default).

---

## [2026-05-03] PR #2 — Data layout consolidation + `.gitkeep` markers + typo fix

Merge commit: [`b828d29`](https://github.com/lotantamary-tau/CV-CellDetection/commit/b828d29). Plus a post-merge filesystem move of TIF files from `Lab/data/RawData/` → `data/RawData/`.

### Added

- `.gitkeep` markers in `data/RawData/`, `data/TaggedData/`, `data/results/debug_outputs/`, `data/results/hdf5/` so the folder structure ships pre-built on clone. Friends drop a TIF into `data/RawData/` and run — no folder-creation required.
- `data/README.md` documenting the input/output layout.

### Changed

- **All CNMF outputs moved from inside `cnmf_toolkit/` to a unified `data/results/` tree:**
  - `cnmf_toolkit/cnmf_debug_outputs/` → `data/results/debug_outputs/`
  - `cnmf_toolkit/cnmf_results/` → `data/results/hdf5/`
- Default output paths in `debug_tracker.py`, `cnmf_manager.py`, and the viewer modules now resolve via `Path(__file__).resolve().parents[N]` so they work regardless of CWD. `CNMF_DEBUG_DIR` env-var override preserved.
- `.gitignore` rule `docs/superpowers/` widened to `docs/` (the whole folder is local-only; nothing tracked in it). `docs/` no longer appears in fresh clones.
- `reserch/` → `research/` typo fix (folder rename + `.gitignore` line + `CLAUDE.md` reference).

### Fixed

- Notebook's `video_path`: `../data/<movie>.tif` → `../data/RawData/<movie>.tif`. The flat path was always-broken on a fresh clone; only worked when an inspection worktree happened to have a flat copy of the TIF.

---

## [2026-05-02] PR #1 — Cleanup and portability

Merge commit: [`e317fd9`](https://github.com/lotantamary-tau/CV-CellDetection/commit/e317fd9). The first major restructuring — made the project cloneable and wired up the dead-code debug pipeline.

### Added

- Named conda env `cv-celldetection` (was path-based `.venv` which broke whenever the project folder moved — cv2 / numpy / scipy / contourpy / caiman all hardcoded the old project path).
- `environment.yml` with napari, scikit-image, scipy as pip extras.
- `cnmf_toolkit/` as a real Python-importable package.
- Debug-pipeline actually works end-to-end. Was previously dead code — `cnmf_manager.py` imported upstream CNMF instead of the instrumented copy, so debug hooks never fired and the viewer had nothing to read.

### Changed

- `Lab/CaImAn-Visualizer/` → `cnmf_toolkit/` (lowercase, Python-importable, purpose-named).
- `CaImAn-Visualizer.py` → `instrumented_cnmf.py` (hyphenated filenames can't be Python-imported).
- `Visualizer/` → `viewer/` (matches existing `from viewer import …` line and Python conventions).
- `debug_viewer.py` → `stage_viewer.py`, `hdf5_viewer.py` → `results_viewer.py`.
- `interactive_cnmf_viewer.py` → `cnmf_viewer.py`.
- `MISSION_SUMMARY.txt` → `cnmf_toolkit/USAGE.md`.
- `Lab/notebooks/` → `notebooks/`, `Lab/data/` → `data/`. `Lab/` removed entirely.
- The architectural wire-up: `cnmf_manager.py` now imports `from instrumented_cnmf import CNMF` instead of upstream CaImAn's CNMF. This is what makes debug hooks actually fire on every run.

### Fixed

- Removed broken `_REPO_ROOT = ../../../..` `sys.path` hack from `cnmf_runner.py`, `cnmf_manager.py`, `compare_pixels.py` (kept the working `_THIS_DIR` insertion for sibling imports when run as scripts).
- Notebook `video_path` changed from a hardcoded user-specific absolute path to a relative one (`../data/<movie>.tif`).
- macOS-only `QT_MAC_WANTS_LAYER` env var in `cnmf_viewer.py` now guarded by `sys.platform == 'darwin'`.

### Documentation

- `README.md` and `CLAUDE.md` rewritten for the new layout.
- `data/README.md` created.

### Post-merge fixes during 2026-05-24 inspection

- `environment.yml`: `napari[pyqt6]>=0.5` → `napari>=0.5`. The pip-installed PyQt6 6.11 conflicted with conda's `qt6-main` 6.10.2 (transitively from caiman/opencv). Napari now uses the conda-provided pyside6 binding via qtpy auto-detection.
- `cnmf_toolkit/USAGE.md` had the wrong conda env name (`caiman` instead of `cv-celldetection`) in the copy-paste setup block.

---

## How to use this file

- When a new PR merges, add a top-level dated entry above with the merge commit SHA and Added / Changed / Fixed / Documentation sections.
- When in doubt about what changed, prefer this file. For the exact diff of any entry, see the referenced merge commit on GitHub.
- Keep entries action-oriented and concrete. Avoid marketing language; describe the actual change.
