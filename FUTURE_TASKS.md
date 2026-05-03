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

## 4. Wire the lab notebook into the debug tracker / viewer (with a debug-mode toggle)

**Problem.** The debug tracker + napari viewer only fire when CNMF is run via `cnmf_runner.py` / `CNMFManager` (which use `instrumented_cnmf.CNMF`). The lab notebook (`notebooks/OPCal_cell detection_caiman_150226.ipynb`) imports `CNMF` directly from upstream `caiman.source_extraction.cnmf` and applies its own lab-refined logic (custom parameter tweaks, post-processing, refit, evaluation). Result: the viewer has nothing to show for the *actual* analysis the lab runs in production — only the runner's path. We can inspect the toolkit's CaImAn-style pipeline but not the notebook's lab pipeline.

**What we want.** A switchable connection. When the lab is doing normal analysis, the notebook behaves exactly as it does today — zero debug overhead, no extra files. When someone wants to *inspect* a stage in napari, they flip a single flag at the top of the notebook, Run-All, then launch `cnmf_viewer.py` — the viewer finds the stages exactly the way it loads runner output today.

**Two implementation options to consider — pick before executing.** Both produce the same user-visible behavior (a `DEBUG_MODE` flag at the top of the notebook); they differ in *how* the toggle is wired underneath.

### Option A — branch on the import (simpler)

```python
DEBUG_MODE = False   # set True to enable per-stage debug snapshots for the viewer

if DEBUG_MODE:
    import sys; sys.path.insert(0, '../cnmf_toolkit')
    from instrumented_cnmf import CNMF
else:
    from caiman.source_extraction.cnmf.cnmf import CNMF
```

- **How it works.** Two completely separate CNMF classes get loaded depending on the flag. In `DEBUG_MODE = False` the notebook never even imports the instrumentation — zero overhead, zero risk of accidentally writing to `data/results/`. In `DEBUG_MODE = True` it imports the instrumented class and the hooks fire automatically.
- **Pros.** Trivially simple — flip one line, Run-All. Non-debug mode is byte-identical to the original notebook (no chance of behavior drift). Easy for friends to understand at a glance.
- **Cons.** Two import paths means two code paths, which is harder to reason about if someone later changes the upstream caiman version vs. the instrumented version. Not really a problem in practice since `instrumented_cnmf.py` is a near-verbatim copy of upstream.

### Option B — always import the instrumented class, toggle the tracker (cleaner architecture)

```python
import sys; sys.path.insert(0, '../cnmf_toolkit')
from instrumented_cnmf import CNMF
from debug_tracker import CNMFDebugTracker

DEBUG_MODE = False
tracker = CNMFDebugTracker(enabled=DEBUG_MODE)   # no-op when disabled
# ...later, when constructing the CNMF object, pass the tracker through.
```

- **How it works.** The notebook *always* uses the instrumented CNMF, but the tracker has an `enabled` flag (`debug_tracker.py:34`) that makes `save_stage` a no-op when False. So in non-debug mode the instrumentation is loaded but does nothing — same behavior, same outputs.
- **Pros.** Single code path. There's only one `CNMF` class to reason about. Closer to the runner's behavior, so any future improvement to the instrumented class flows to both runner and notebook.
- **Cons.** Slightly more machinery upfront — needs to plumb the tracker into the CNMF constructor (the runner does this automatically; the notebook would need to do it explicitly). Microscopically slower import time (loads `debug_tracker` and its matplotlib import).

### Recommendation

**Start with Option A** unless someone has a specific reason to prefer B. A is a 4-line change to the notebook with no tracker plumbing required, and labs are used to "flip flag, re-run." Switch to B later if the lab notebook starts wanting to capture *some* stages but not others (e.g., capture only the refit, not the initial fit) — at that point the tracker's `enabled` flag is more flexible than an import branch.

**Where to change (Option A).**
- `notebooks/OPCal_cell detection_caiman_150226.ipynb` — at the very top of the notebook, add the `DEBUG_MODE = False` cell with the conditional import. Update the cell that imports `CNMF` so it doesn't redundantly import again.
- `data/README.md` and `cnmf_toolkit/USAGE.md` — mention the toggle: "set `DEBUG_MODE = True` in the notebook + Run-All to write debug outputs; then `python cnmf_viewer.py` to inspect."

**Verification.** Run the notebook with `DEBUG_MODE = False`: nothing new in `data/results/`. Run with `DEBUG_MODE = True`: see fresh `.npz` files in `data/results/debug_outputs/` and a new HDF5 in `data/results/hdf5/`. Then `python cnmf_viewer.py` should load the notebook's stages. (If both runner and notebook end up writing to the same folder, see future task #2 — multi-run isolation — to keep them separated.)

---

## How we use this file

- One section per idea. No deadlines, no owners — these are notes, not tickets.
- When you start working on one, move it into a real plan (e.g., `docs/superpowers/plans/…`) or a GitHub issue and delete it from here.
- If an idea sits here for 6+ months unused, delete it — that's a signal nobody actually wants it.
