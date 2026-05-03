# data/

This folder holds **everything** that isn't source code: input movies, tagged labels, and CNMF outputs. The folder structure ships with the repo (via `.gitkeep` markers in each subfolder), so a fresh clone is ready to use — just drop your TIFs in.

## Layout

```
data/
├── README.md            (this file)
├── RawData/             input  — raw TIF movies that CNMF processes
├── TaggedData/          input  — manually-tagged ROI labels (used for validation)
└── results/             output — everything CNMF produces
    ├── debug_outputs/   per-stage .npz / metadata snapshots from each CNMF stage
    └── hdf5/            final HDF5 + config JSON written by cnmf_runner.py
```

## What's gitignored

Everything under `data/` is gitignored **except this README and the empty `.gitkeep` marker files** that preserve each subfolder's existence in the repo. Your TIFs (`*.tif`/`*.tiff`), tagged ROIs, debug outputs, and HDF5 results all stay local — drop them freely, they will never be committed. Each contributor supplies their own raw data; the repo stays small.

## How to use it

1. **Add your raw movies** to `data/RawData/`. Example: `data/RawData/my_movie.tif`.
2. **Add validation labels** (if you have any) to `data/TaggedData/`.
3. **Run CNMF** from `cnmf_toolkit/`:
   ```bash
   cd cnmf_toolkit
   python cnmf_runner.py "../data/RawData/my_movie.tif"
   ```
4. **Outputs land automatically** in `data/results/debug_outputs/` and `data/results/hdf5/` — those folders already exist (via `.gitkeep`) and the toolkit fills them.
5. **View results** with `python cnmf_viewer.py` — it reads from `data/results/` by default.

## Overriding output locations

Set `CNMF_DEBUG_DIR=/some/other/path` to send debug outputs elsewhere (the env-var escape hatch survives this layout change).
