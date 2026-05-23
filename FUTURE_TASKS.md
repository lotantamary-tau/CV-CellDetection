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

## 3. ~~Stage-switch keys 1 & 2 collide with napari built-in shortcuts~~ — RESOLVED

Resolved by the 2026-05-23 multi-run + fit/refit + dynamic keymap refactor:
stage keys moved off digits onto F1-F7. F-keys have no napari built-in
conflict. The mapping is also dynamic — F1 binds to the first stage in the
current phase's pipeline order, F2 to the second, and so on — so it works
for both the patches-based fit phase and the non-patches refit phase.

---

## 4. ~~Wire the lab notebook into the debug tracker / viewer~~ — RESOLVED

Resolved by the same 2026-05-23 refactor: notebook has `DEBUG_FIT` and
`DEBUG_REFIT` boolean toggles at the top; the tracker is phase-aware
(writes to `run_<ts>/fit/` or `/refit/`); the viewer can walk between runs
(F9/F10) and toggle phase (F8). The viewer's stage discovery is dynamic so
it handles patches and non-patches stage sets seamlessly.

---

## How we use this file

- One section per idea. No deadlines, no owners — these are notes, not tickets.
- When you start working on one, move it into a real plan (e.g., `docs/superpowers/plans/…`) or a GitHub issue and delete it from here.
- If an idea sits here for 6+ months unused, delete it — that's a signal nobody actually wants it.
