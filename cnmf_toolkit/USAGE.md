================================================================================
  CNMF_TOOLKIT — USAGE GUIDE & CRASH RECOVERY
================================================================================
  Last updated: 2026-05-03
================================================================================

PURPOSE
-------
Run CNMF calcium imaging analysis on TIFF movies, save debug data at every
pipeline stage, and inspect results interactively in napari.


DATA LAYOUT
-----------
Drop your TIFF movies into the repo's gitignored `data/` folder (one level up
from `cnmf_toolkit/`). See `data/README.md` for the expected structure. The
examples below assume a movie at `../data/your_movie.tif`.

The lab's reference movies have been ~1380 frames, 512x512, uint16, ~690 MB,
recorded at fr=1.08 Hz with 1.243 µm/px spatial resolution. CNMF parameters
in the named configs (e.g. `greedy_roi_no_patches_config`) are tuned for
that regime.


STEP-BY-STEP (copy-paste these commands)
-----------------------------------------

  ┌──────────────────────────────────────────────────────────────────┐
  │ STEP 0 — Always activate conda first                           │
  │                                                                  │
  │   conda activate cv-celldetection                                │
  │   cd cnmf_toolkit                                                │
  └──────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────┐
  │ STEP 1 — Run CNMF analysis                                      │
  │                                                                  │
  │   python cnmf_runner.py "../data/your_movie.tif"                 │
  │                                                                  │
  │   Options:                                                       │
  │     --config greedy_roi_no_patches_config   (default)            │
  │     --config corr_pnr_no_patches_config     (alternative)        │
  │     --also-corr-pnr                         (run both)           │
  └──────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────┐
  │ STEP 2 — View results in napari                                  │
  │                                                                  │
  │   python cnmf_viewer.py                              │
  │                                                                  │
  │   Controls:                                                      │
  │     1-8        Switch stages (init → spatial → temporal → etc.)  │
  │     Click ROI  Detailed component analysis plot                  │
  │     SPACE      Analyze ROI at cursor                             │
  │     S          Print stage stats                                 │
  │     I          Top-10 most active components                     │
  └──────────────────────────────────────────────────────────────────┘


OUTPUT FILES (auto-created)
---------------------------
  cnmf_debug_outputs/       Per-stage matrices, PNGs, metadata
    init_0.npz              Dense arrays (C, S, YrA, b, f, ...)
    init_0_A.npz            Sparse spatial components (A)
    metadata_init_0.txt     Shape/size info
    ROI_*_init_0.png        Individual ROI masks
    YrA_traces_init_0.png   Residual traces
    ... (same pattern for spatial_1, temporal_1, merge, etc.)

  cnmf_results/             Final HDF5 + config JSON
    cnmf_results_<config>_<timestamp>.hdf5
    config_<config>_<timestamp>.json


IF THE COMPUTER CRASHES / FREEZES
----------------------------------
This is usually caused by running out of RAM. The movie is ~0.7 GB but CNMF
can use 5-10x that during processing. Recovery steps:

  1. Force restart / kill Python if frozen:
       killall -9 python                       # macOS / Linux
       taskkill /F /IM python.exe              # Windows (cmd / PowerShell)

  2. Clean up leftover memory-mapped files:
       rm -f /tmp/caiman_memmap_*              # macOS / Linux
       Remove-Item $env:TEMP\caiman_memmap_*   # Windows (PowerShell)

  3. To reduce memory usage, re-run with fewer frames:
       python -c "
       from cnmf_manager import CNMFManager
       m = CNMFManager()
       m.run_cnmf('greedy_roi_no_patches_config',
                   movie_file='../data/your_movie.tif',
                   enable_debug=True, max_frames=500)
       "

  4. Or disable debug tracking to reduce disk I/O:
       CNMF_DEBUG=0 python cnmf_runner.py <movie.tif>

  5. Check if partial results were saved:
       ls -la cnmf_debug_outputs/    # per-stage data
       ls -la cnmf_results/          # final HDF5

  6. If debug stages exist but no final HDF5, you can still view
     the partial results:
       python cnmf_viewer.py


ADDING A CUSTOM DEBUG STAGE
----------------------------
If you want to save your own stage (e.g. after custom filtering or manual
corrections) and view it in the napari viewer, follow these steps:

  1. Define your new stage in viewer/__init__.py (STAGE_DEFINITIONS dict):

       'my_stage': {'order': 9, 'name': 'My Custom Stage', 'key': '9'},

  2. Save the stage using CNMFDebugTracker from a Python script or REPL:

       from debug_tracker import CNMFDebugTracker
       tracker = CNMFDebugTracker(save_dir="cnmf_debug_outputs")

       # A = spatial components (sparse or dense, pixels × components)
       # C = temporal traces (components × frames)
       # S, b, f, YrA = optional extra matrices
       tracker.save_stage(
           "my_stage",
           dims=(512, 512),    # image height, width
           A=my_A_matrix,
           C=my_C_matrix,
           S=my_S_matrix,      # optional
           b=my_b_matrix,      # optional (background spatial)
           f=my_f_matrix,      # optional (background temporal)
           YrA=my_YrA_matrix,  # optional (residuals)
       )

     This creates three files in cnmf_debug_outputs/:
       my_stage_0.npz         Dense arrays (C, S, YrA, b, f, ...)
       my_stage_0_A.npz       Sparse A matrix (if A was sparse)
       metadata_my_stage_0.txt

  3. Add a key binding in viewer/stage_viewer.py (_bind_keys method):

       stage_keys = {
           ...
           '9': 'my_stage',    # <-- add this line
       }

  4. Launch the viewer and press 9 to switch to your stage:

       python cnmf_viewer.py

  Note: The viewer expects stage files to follow the naming convention
  {stage_name}_0.npz for dense arrays and {stage_name}_0_{key}.npz for
  sparse matrices (e.g. A). The StageStore scans cnmf_debug_outputs/
  at startup and will automatically pick up any stage whose name matches
  an entry in STAGE_DEFINITIONS.


AVAILABLE CONFIGS
-----------------
  greedy_roi_no_patches_config  - Greedy ROI, no patches, YOUR data params
  corr_pnr_no_patches_config   - Corr/PNR, no patches, YOUR data params
  greedy_roi_config             - Greedy ROI with patches (generic)
  corr_pnr_config               - Corr/PNR with patches (generic)
  fast_config                    - Fast/rough for testing
  high_quality_config            - Slow/thorough, piecewise-rigid MC

  Your data parameters (used in *_no_patches configs):
    fr=1.08, decay_time=20, gSig=[4,4], p=2, merge_thr=0.2,
    min_SNR=2.0, rval_thr=0.85, min_cnn_thr=0.99


FILES IN THIS DIRECTORY
-----------------------
  USAGE.md                     This file
  GDRIVE_SETUP.md              Google Drive upload instructions
  cnmf_runner.py               CLI entry point (Step 1)
  cnmf_manager.py              CNMFManager class with all configs
  debug_tracker.py             CNMFDebugTracker (saves per-stage data)
  gdrive_uploader.py           Optional Google Drive upload
  cnmf_viewer.py               Napari viewer entry point (Step 2)
  instrumented_cnmf.py         CNMF class with per-stage debug hooks
  compare_pixels.py            Diagnostic CLI: compare 2 pixel signals
  viewer/                      Viewer sub-package
    stage_viewer.py            Stage-switching napari viewer
    results_viewer.py          Fallback HDF5 viewer
    stage_store.py             Lazy-loads debug stage files
    image_utils.py             ROI labels, reference images
    plotting.py                Matplotlib component analysis plots
