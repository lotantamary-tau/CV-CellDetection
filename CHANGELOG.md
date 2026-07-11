# Changelog

All notable changes to CV-CellDetection, in reverse chronological order. Each top-level entry corresponds to a merged PR. New entries get added when work merges to `main`.

Format loosely follows [Keep a Changelog](https://keepachangelog.com): each PR has Added / Changed / Fixed / Documentation sections. For the exact diff of any entry, see the referenced merge commit on GitHub.

---

## [2026-07-11] PR #5 — CellPose→CNMF hybrid detection pipeline

Merge commit: [`30ff799`](https://github.com/lotantamary-tau/CV-CellDetection/commit/30ff799).

### Added

- **CellPose→CNMF hybrid pipeline** — replaces CNMF's brightness-based seeding (which merges touching cells) with **CellPose-SAM** deep-learning cell detection, then extracts each cell's activity trace via **seeded CNMF** with the footprints frozen. On the OPCal test recording it beats the greedy CNMF baseline: **186 covered / 14 missed / 17 merges** vs **158 / 42 / 25** (+28 cells, −28 missed, −8 merges), with a per-cell trace.
- **`notebooks/cellpose_colab.ipynb`** — Colab (GPU) notebook that runs CellPose-SAM (`cpsam_v2`) on a movie projection → a cell mask. Step 1 (the heavy model needs a GPU).
- **`notebooks/OPCal_cell detection_caiman_150226_dl-seeding.ipynb`** — the local hybrid notebook. Step 2: CellPose mask → seeded CNMF (intensity-weighted seeds, min-brightness junk filter, frozen footprints) → traces + scored overlay. A **CONFIG cell** at the top holds the 3 paths teammates edit; key steps are off/on toggles (`INTENSITY_WEIGHT`, `JUNK_FILTER`, `RUN_REFIT`, `RUN_COMPONENT_EVAL`).
- **`cnmf_toolkit/cellpose_export_projection.py`** — build mean/max/correlation projections of a movie (the 2D image uploaded to Colab). Accepts an optional movie path argument.
- **`cnmf_toolkit/cellpose_mask_to_A.py`** — convert a CellPose label mask → CNMF-style `_A.npz` so `ground_truth_scorer.py` can score a segmentation directly.
- **`cnmf_toolkit/DL_SEEDING_WORKFLOW.md`** — step-by-step teammate guide (which 3 paths to edit, the Colab↔local upload/download, the toggles, troubleshooting).
- No new dependencies for the local side (CellPose runs only on Colab; local uses the existing CaImAn/numpy/scipy/scikit-image stack).

### Documentation

- `CLAUDE.md`: directory-table entries for the hybrid pipeline + its files.

---

## [2026-06-25] PR #4 — Ground-truth scorer tool

Merge commit: [`3a1deee`](https://github.com/lotantamary-tau/CV-CellDetection/commit/3a1deee).

### Added

- **`cnmf_toolkit/ground_truth_scorer.py`** — CLI tool that scores a CNMF run's detections against a manual ground-truth annotation: prints **correct / merge / split / junk / covered / missed** and saves a color-coded 2-panel overlay PNG to `data/results/comparisons/`. It is the **generalized, shareable** version of the lab's local `merge_eval.py` research script — identical scoring math, but with `argparse` flags (`--annotation`, `--run`, `--stage`, `--output`, `--label`, `--no-plot`, `--thr-foot`, `--min-sep`), repo-anchored default paths (works from the repo root or `cnmf_toolkit/`), and no hardcoded experiment bookkeeping. No new dependencies (numpy / scipy / scikit-image / tifffile / matplotlib, all already in `environment.yml`).
- **Accuracy = v1 (approximate):** treats the annotation as a binary mask and watershed-separates touching cells, so counts are reliable for *relative* run-vs-run comparison but not exact per-cell accuracy. Exact per-cell IoU/Dice needs a per-cell **labelled** annotation (planned v2).

### Documentation

- `README.md`: "Step 3 — score a run against manual tags" + the tool in the repo-layout block + `data/results/comparisons/`.
- `cnmf_toolkit/USAGE.md`: "GROUND-TRUTH SCORER" section + a STEP 3 box + the file list.
- `CLAUDE.md`: directory-table entry for the new tool.

---

## [Unreleased] — local working state (NOT a merged PR)

> ⚠️ Everything in this section is **local-only / gitignored / untracked** — it has **not**
> merged to `main` and has **no commit SHA**. It's recorded here for traceability of the
> in-progress **merge-tuning mission** (Notion "Merge parameter tuning"). It will graduate
> into a real dated PR entry above only if/when keeper changes to tracked code (`cnmf_toolkit/`,
> the committed notebook) are merged. The authoritative trace lives under
> `docs/superpowers/` (git-ignored) — start at `docs/superpowers/README.md`.

### Added (local working artifacts)

- **Merge-tuning research mission (test plan 1 → test plan 2).** Investigated CaImAn's merge
  step + surrounding pipeline against the manual annotation. Key result: the merge **errors are
  set at initialization**, not the merge step (`merge_thr`/`K`/`gSig` sweeps don't reduce them);
  the dominant *fixable* signal (junk/over-detection) is confounded by an incomplete binary
  annotation. A second deep dive (with the previous teammate Sheer Glaor's research + the
  neuron→electrocyte lens) reframed the next phase around `corr_pnr` initialization + motion
  correction. Trace: `docs/superpowers/research/` (findings, testlog, summary, deep-dive) and
  `specs/2026-06-20-merge-tuning-spec.md`.
- **`docs/superpowers/research/merge_eval.py`** — local evaluation tool. Scores a CNMF run vs
  the annotation (correct/merge/split/junk/covered/missed), watershed-separates touching cells,
  and saves a color-coded 2-panel overlay PNG. Precursor to a formal `cnmf_toolkit/` evaluator.
- **Experiment notebook** `notebooks/OPCal_cell detection_caiman_150226_merge-tuning.ipynb`
  (untracked duplicate; the committed original stays pristine) — adds an annotation-path cell,
  a component-evaluation (Path-D) cell, and a ground-truth comparison cell.

### Changed (local working artifacts)

- **`merge_eval.py` save scheme.** Now takes `<exp> <slug>` → writes
  `data/results/comparisons/test-plan-2/exp<NN>_<slug>.png` and **auto-appends a metrics row**
  to that folder's `INDEX.md` (replaces the old confusable `eval_<label>_n<K>.png` naming). The
  notebook's by-eye overlay now saves alongside as `notebook-overlay_<run_id>.png`.
- **Folder reorganization (2026-06-20).**
  - `data/results/comparisons/` — flat, confusably-named PNGs reorganized **by test plan**:
    `test-plan-1/` (the Exp #0–#4 figures, renamed `exp00…exp04`), `test-plan-2/` (current),
    `_superseded/` (old duplicate renders), and a top-level `INDEX.md` mapping every figure.
  - `docs/superpowers/` — consistent `…-merge-tuning-<role>.md` names, a new `README.md` index,
    and an `archive/` for the closed v1 spec/plan + older unrelated plans. (`merge_eval.py`
    stays in `research/`.)

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
