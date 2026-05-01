# Architectural Patterns

Companion to [../../CLAUDE.md](../../CLAUDE.md). Documents how the CaImAn-Visualizer fork is structured, why it is structured that way, and the recurring patterns Claude should match when extending it.

## Architectural Patterns

### Forked-algorithm-with-instrumentation
[Lab/CaImAn-Visualizer/CaImAn-Visualizer.py](../../Lab/CaImAn-Visualizer/CaImAn-Visualizer.py) is a near-verbatim copy of upstream `caiman.source_extraction.cnmf.cnmf.CNMF`. The fork exists to insert `CNMFDebugTracker.save_stage(...)` calls between pipeline stages (initialization, spatial update, temporal update, merge, deconvolution) without changing the math. Treat the algorithmic body as upstream code under "do-not-touch" rules; only the hook sites and surrounding bookkeeping are local.

### Stage-keyed pipeline with pluggable visualization
The CNMF pipeline is conceptually a sequence of named stages (`init`, `spatial_1`, `temporal_1`, `merge`, …). Every stage produces a uniform on-disk shape: `{stage}_N.npz` (dense matrices), `{stage}_N_A.npz` (sparse spatial), `metadata_{stage}_N.txt`. The napari viewer reads this shape and switches stages via numeric keys (1–8). Adding a new stage is a three-line change documented in [Lab/CaImAn-Visualizer/MISSION_SUMMARY.txt](../../Lab/CaImAn-Visualizer/MISSION_SUMMARY.txt) (STAGE_DEFINITIONS in `Visualizer/__init__.py`, save it via `CNMFDebugTracker`, bind a key in `Visualizer/debug_viewer.py`).

### Two-tier package: research code vs. production code
[Lab/CaImAn-Visualizer/](../../Lab/CaImAn-Visualizer/) is the algorithm-adaptation surface — instrumented CNMF for understanding/tuning. [Lab/notebooks/](../../Lab/notebooks/) is where the lab's actual electrocyte-detection runs live. Cross-references go one direction: notebooks may use the visualizer; the visualizer does not depend on notebooks.

## Design Decisions

### Why fork CaImAn instead of subclassing
The CNMF class is heavily stateful with many in-place mutations across long methods. Subclassing would require overriding methods that are hundreds of lines long just to insert one debug call mid-method, and would be extremely fragile across CaImAn upstream versions. A static fork lets us pin a known-good upstream snapshot and edit only the lines we need.

### Adapting to electrocytes vs. neurons
Electrocyte cells have different spatial scale, firing dynamics, and acquisition rate than the calcium-imaging neurons CaImAn was tuned for. The "named-config" pattern in [Lab/CaImAn-Visualizer/cnmf_manager.py](../../Lab/CaImAn-Visualizer/cnmf_manager.py) captures this: each config bakes in a parameter set (`fr`, `decay_time`, `gSig`, `min_SNR`, `rval_thr`, `min_cnn_thr`, …) appropriate for our data. The `*_no_patches_config` variants are the lab's electrocyte parameters; the others are inherited from CaImAn defaults for comparison.

### Optional Google Drive offload
Per-stage outputs can balloon to many GB on a long movie. [Lab/CaImAn-Visualizer/gdrive_uploader.py](../../Lab/CaImAn-Visualizer/gdrive_uploader.py) and [Lab/CaImAn-Visualizer/GDRIVE_SETUP.md](../../Lab/CaImAn-Visualizer/GDRIVE_SETUP.md) provide an opt-in upload-and-delete-local flow so a debug run does not fill a workstation disk.

## State Management

State lives in three places, in order of mutability:

1. **In-memory CNMF object state** — `self.estimates.{Ab, C, S, b, f, YrA, AtA, …}` mutated in place by each stage of [CaImAn-Visualizer.py](../../Lab/CaImAn-Visualizer/CaImAn-Visualizer.py). This is upstream behavior, not local design.
2. **Per-stage on-disk snapshots** — written by [debug_tracker.py:15](../../Lab/CaImAn-Visualizer/debug_tracker.py#L15) `CNMFDebugTracker.save_stage(...)`. The viewer never modifies these; it reads-only.
3. **Final HDF5 + config JSON** — `cnmf_results/cnmf_results_<config>_<timestamp>.hdf5` plus `config_<config>_<timestamp>.json` produced after the full run. This is the persistent record.

Provenance is tracked separately in `self.provenance` (see e.g. [Lab/CaImAn-Visualizer/CaImAn-Visualizer.py:587](../../Lab/CaImAn-Visualizer/CaImAn-Visualizer.py#L587)) — a list of `{event, time, description, …}` dicts appended whenever components are removed, merged, or otherwise transformed.

## Recurring Logic Patterns

### Sparse + dense split for spatial components
The spatial component matrix `A` is sparse; everything else is dense. The save format reflects this: `{stage}_N.npz` for dense arrays, `{stage}_N_A.npz` for sparse `A`. Code that consumes a stage must handle the absence of `A_sparse` (some stages skip it).

### Lazy import to break circulars
[Lab/CaImAn-Visualizer/__init__.py:20](../../Lab/CaImAn-Visualizer/__init__.py#L20) uses module-level `__getattr__` to defer importing `CNMFManager`. This avoids a circular import between the visualizer's `__init__.py` and `cnmf_manager.py`, which itself imports from the CNMF module.

### Sibling-style imports inside the package
Because the package folder is named `CaImAn-Visualizer` (with a hyphen), it cannot be imported as a Python module by that name. Code inside the folder must use sibling imports (`from debug_tracker import CNMFDebugTracker`) and rely on running from inside the directory or having the directory on `sys.path`. Do not write `from CaImAn-Visualizer import ...` — it is a syntax error.

## API / Interface Design Patterns

### CLI entry points
[cnmf_runner.py](../../Lab/CaImAn-Visualizer/cnmf_runner.py) and [interactive_cnmf_viewer.py](../../Lab/CaImAn-Visualizer/interactive_cnmf_viewer.py) are both invoked as plain `python <file.py> [args]`. No `setup.py` console_scripts, no Click/Typer — just `argparse` (or simpler) and direct execution.

### Napari keybindings as the user surface
The viewer is keyboard-driven: digit keys switch stages, letter keys (`S`, `I`, `SPACE`) trigger analyses, mouse click on an ROI opens a detail plot. New interactivity should follow this pattern (single-key bindings, registered in `Visualizer/debug_viewer.py`'s `_bind_keys` method) rather than building a GUI panel.

### Environment-variable configuration for optional integrations
GDrive upload is configured exclusively through env vars (`GDRIVE_FOLDER_ID`, `GDRIVE_SERVICE_ACCOUNT_KEY`, `GDRIVE_CLIENT_SECRET`). No config file, no CLI flag — the integration silently no-ops if env vars are unset.

## Dependency Injection / Inversion of Control

There is no formal DI container — wiring is done by direct construction at the entry-point level:
- [cnmf_runner.py](../../Lab/CaImAn-Visualizer/cnmf_runner.py) constructs a `CNMFManager`, which constructs the CNMF object, which (when `enable_debug=True`) constructs a `CNMFDebugTracker`.
- The tracker optionally constructs a `GDriveUploader` if env vars are present.

The closest thing to inversion of control is the `enabled=` flag on `CNMFDebugTracker` and the env-var presence check on `GDriveUploader`: both let upstream callers leave the integration as a no-op without conditional code at every call site.
