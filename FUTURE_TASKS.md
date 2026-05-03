# Future Tasks

Lightweight, low-priority improvements we've noticed but haven't acted on. Pick one off when convenient.

---

## 1. `--no-png` flag for `cnmf_runner.py`

**Problem.** A single run with ~234 components produces ~1,640 per-ROI PNGs in `data/results/debug_outputs/` (one PNG per component per stage). Disk impact is small (~50–80 MB) but the file count is overwhelming, and the napari viewer doesn't actually read these PNGs — it reads the `.npz` matrices. The PNGs only exist for offline browsing.

**Idea.** Add a `--no-png` (or `--png/--no-png`) flag on `cnmf_runner.py` that gets forwarded into `CNMFDebugTracker` and skips both `_save_masks_as_png` and `_plot_YrA_traces`. Saves a few seconds of runtime and ~1.6k files per run.

**Where to change.**
- `cnmf_toolkit/debug_tracker.py:34` — add `save_pngs=True` kwarg to `__init__`, gate the two `_save_masks_as_png` / `_plot_YrA_traces` calls in `save_stage`.
- `cnmf_toolkit/cnmf_runner.py` — add the CLI flag, plumb it into `CNMFManager`.
- `cnmf_toolkit/cnmf_manager.py` — accept the flag and pass to the tracker constructor.

**Default.** Keep PNGs ON by default — current behavior — so we don't break workflows that depend on them.

---

## 2. Multi-run isolation in `data/results/debug_outputs/`

**Problem.** `CNMFDebugTracker.stage_counter` resets to 0 every time the tracker is instantiated (per-instance state, not persisted to disk). Combined with no pre-run cleanup, this means:

- Run #2 silently overwrites run #1 files that share names (`init_0.npz`, `ROI_5_init_0.png`, …).
- Run #2 leaves stale files from run #1 behind whenever run #1 had more components or different stages (e.g., `ROI_233_*.png` from a 234-component run sticks around if run #2 finds 100).
- The napari viewer then loads a mixed-run folder with no warning.

**Possible fixes (pick one).**
- **A. Per-run subfolder (cleanest).** Tracker creates a timestamped sub-directory `data/results/debug_outputs/run_YYYYMMDD_HHMMSS/` on init. Each run is fully isolated. Viewer either accepts a `--run` argument or auto-picks the most recent.
- **B. Wipe-on-start (simpler).** Before the first `save_stage` call, the tracker clears its `save_dir`. One-line behavior change but destructive — easy to lose data accidentally.
- **C. Continue-the-counter (smallest change).** On init, scan existing files matching `{stage}_*.npz`, set `stage_counter[stage]` to one past the highest seen. Files coexist (`init_0.npz` from run #1, `init_1.npz` from run #2), but the viewer needs to learn to filter by run.

**Recommendation.** Option A. Cleanest semantics, easy for the viewer to handle, plays nicely with the existing `_upload_stage_files` GDrive logic (a per-run folder maps naturally to a per-run GDrive folder, which the code already creates).

**Where to change.**
- `cnmf_toolkit/debug_tracker.py:34-46` — adjust `save_dir` to append a timestamped sub-dir.
- `cnmf_toolkit/viewer/stage_store.py` — teach it to look in the most recent sub-dir (or accept an explicit one).

---

## 3. Stage-switch keys 1 & 2 collide with napari built-in shortcuts

**Problem.** `viewer/stage_viewer.py:271` binds digit keys `1`–`8` to stage switching. Keys 3–7 work, but **`1` and `2` are silently intercepted by napari's layer-level shortcuts** (`1` = pan/zoom mode, `2` = transform mode). These are wired at the Qt event level so `viewer.bind_key('1', overwrite=True)` doesn't actually win — the user's keypress never reaches `switch_stage('init')`. There's a visible hint at the bottom-right of the napari window that gives this away: `use <2> for transform`.

**Fix.** Remap the conflicting keys in `_bind_keys()`:
- Option A: keep digit keys but remap `1`/`2` to non-conflicting alternatives (e.g., `Q` for init, `W` for spatial_1, then `3`–`7` continue as today).
- Option B: move all stage shortcuts off digits onto letters (`Q W E R T Y U` for the 7 stages).
- Option C: use function keys (`F1`–`F7`).

**Recommendation.** Option B (letters Q–U) is the cleanest — uniform, easy to remember (sequential row on the keyboard), and dodges every built-in conflict. Update `USAGE.md` keybinding doc to match.

**Where to change.**
- `cnmf_toolkit/viewer/stage_viewer.py:270-274` — the `stage_keys` dict.
- `cnmf_toolkit/viewer/stage_viewer.py:262-263` — the printed help banner.
- `cnmf_toolkit/USAGE.md` — keybinding documentation.

---

## 4. Wire the lab notebook into the debug tracker / viewer

**Problem.** The debug tracker + napari viewer only fire when CNMF is run via `cnmf_runner.py` / `CNMFManager` (which use `instrumented_cnmf.CNMF`). The lab notebook (`notebooks/OPCal_cell detection_caiman_150226.ipynb`) imports `CNMF` directly from upstream `caiman.source_extraction.cnmf` and applies its own lab-refined logic (custom parameter tweaks, post-processing, refit, evaluation). Result: the viewer has nothing to show for the *actual* analysis the lab runs in production — only the runner's path. We can inspect the toolkit's CaImAn-style pipeline but not the notebook's lab pipeline.

**What we want.** When the lab runs the notebook end-to-end, every stage (init → spatial → temporal → merge → final, plus refit) should write debug snapshots, and `cnmf_viewer.py` should be able to load those exactly the way it loads runner output today.

**Possible approaches.**

- **A. Swap the CNMF import in the notebook.** Replace `from caiman.source_extraction.cnmf.cnmf import CNMF` with `from instrumented_cnmf import CNMF` (after adding `sys.path.insert(0, '../cnmf_toolkit')`). The notebook keeps all its lab-refined logic; debug hooks fire automatically because the instrumented class IS the CNMF the notebook instantiates. Lowest-touch.
- **B. Use `CNMFManager` from the notebook.** Refactor the notebook to call `CNMFManager.run_cnmf(...)` for the heavy lifting and then layer the lab's post-processing on top. Cleaner separation, but the notebook's parameter tuning has to flow through the manager's named-config system — moderate refactor.
- **C. Manually instantiate `CNMFDebugTracker` in the notebook.** Have the notebook create a tracker and call `tracker.save_stage(...)` at chosen checkpoints. Most flexible but loses the "automatic hooks" property — the notebook author has to know where to call `save_stage`.

**Recommendation.** Start with **A** (swap the import). It's a 2-line change and gives the lab the viewer for free. Re-evaluate B if the notebook outgrows its current shape.

**Where to change.**
- `notebooks/OPCal_cell detection_caiman_150226.ipynb` — the cell that imports `CNMF`. Add `sys.path.insert(0, '../cnmf_toolkit')` and change the import.
- `data/README.md` and `cnmf_toolkit/USAGE.md` — once the notebook also writes debug outputs, mention that the viewer works on notebook runs too.

**Verification.** After the change, Run-All on the notebook, then `cd cnmf_toolkit && python cnmf_viewer.py`. The viewer should find stages from the notebook run in `data/results/debug_outputs/`. (If both runner and notebook are run, see future task #2 — multi-run isolation — to keep them separate.)

---

## How we use this file

- One section per idea. No deadlines, no owners — these are notes, not tickets.
- When you start working on one, move it into a real plan (e.g., `docs/superpowers/plans/…`) or a GitHub issue and delete it from here.
- If an idea sits here for 6+ months unused, delete it — that's a signal nobody actually wants it.
