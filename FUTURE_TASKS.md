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

## 2. ~~Multi-run isolation in `data/results/debug_outputs/`~~ — RESOLVED

Resolved by the same 2026-05-23 multi-run + fit/refit + dynamic keymap
refactor that closed #3 and #4. Implemented Option A (per-run subfolder):
the tracker auto-generates a `run_id` timestamp at construction and writes
to `data/results/debug_outputs/run_<TS>/<phase>/<stage>.npz`. Each CNMF
invocation gets its own isolated folder — no silent overwrites between
runs, and the viewer walks between runs with F1/F2. The old per-instance
counter suffix is gone; the run+phase subfolder hierarchy discriminates
between invocations instead.

---

## 3. ~~Stage-switch keys 1 & 2 collide with napari built-in shortcuts~~ — RESOLVED

Resolved by the 2026-05-23 multi-run + fit/refit + dynamic keymap refactor:
stage navigation moved off bare digits entirely. Stages step with F5/F6
(prev/next, circular within the current phase), and Ctrl+1..Ctrl+9 jumps
directly to the Nth stage in the current phase. F-keys and Ctrl-digit
combos have no napari built-in conflict, and the mapping is dynamic — it
works for both the patches-based fit phase and the non-patches refit
phase regardless of how many stages each emits.

---

## 4. ~~Wire the lab notebook into the debug tracker / viewer~~ — RESOLVED

Resolved by the same 2026-05-23 refactor: notebook has `DEBUG_FIT` and
`DEBUG_REFIT` boolean toggles at the top (both default `False` — toolkit
stays out of the way unless explicitly enabled); the tracker is phase-aware
(writes to `run_<ts>/fit/` or `/refit/`); the viewer walks between runs
with F1/F2 and toggles phases (fit ↔ refit) with F3/F4. The viewer's
stage discovery is dynamic so it handles patches and non-patches stage
sets seamlessly.

---

## How we use this file

- One section per idea. No deadlines, no owners — these are notes, not tickets.
- When you start working on one, move it into a real plan (e.g., `docs/superpowers/plans/…`) or a GitHub issue and delete it from here.
- If an idea sits here for 6+ months unused, delete it — that's a signal nobody actually wants it.
