# data/

This folder holds **everything** that isn't source code: input movies, tagged labels, and CNMF outputs. The folder structure ships with the repo (via `.gitkeep` markers in each subfolder), so a fresh clone is ready to use — just drop your TIFs in.

## Layout

```
data/
├── README.md            (this file)
├── RawData/             input  — raw TIF movies that CNMF processes
├── TaggedData/          input  — manually-tagged ROI labels (used for validation)
└── results/             output — everything CNMF produces
    ├── debug_outputs/   per-stage .npz / metadata snapshots
    │   └── run_YYYYMMDD_HHMMSS/   one folder per CNMF invocation
    │       ├── fit/                 always present from cnmf_runner.py;
    │       │   ├── <stage>.npz                from notebook if DEBUG_FIT=True
    │       │   ├── metadata_<stage>.txt
    │       │   └── ...
    │       └── refit/               from notebook if DEBUG_REFIT=True
    │           └── (same stage files as fit/)
    └── hdf5/            final HDF5 + config JSON written by cnmf_runner.py
```

## What's gitignored

Everything under `data/` is gitignored **except this README and the empty `.gitkeep` marker files** that preserve each subfolder's existence in the repo. Your TIFs (`*.tif`/`*.tiff`), tagged ROIs, debug outputs, and HDF5 results all stay local — drop them freely, they will never be committed. Each contributor supplies their own raw data; the repo stays small.

## How to use it

1. **Add your raw movies** to `data/RawData/`. Example: `data/RawData/my_movie.tif`.
2. **Add validation labels** (if you have any) to `data/TaggedData/`.
3. **Run CNMF**:
   - From the terminal: `cd cnmf_toolkit && python cnmf_runner.py "../data/RawData/my_movie.tif"`.
     Always produces a `run_<ts>/fit/` snapshot.
   - From the notebook (`notebooks/OPCal_cell detection_caiman_150226.ipynb`):
     set `DEBUG_FIT = True` and/or `DEBUG_REFIT = True` at the top, then Run-All.
     Each enabled flag produces its corresponding subfolder.
4. **Outputs land automatically** in `data/results/debug_outputs/run_<ts>/<phase>/` and `data/results/hdf5/`.
5. **View results** with `python cnmf_viewer.py` — it defaults to the most-recent run and the refit phase (if present).

## Overriding output locations

Set `CNMF_DEBUG_DIR=/some/other/path` to send debug outputs elsewhere (the env-var escape hatch survives this layout change).
