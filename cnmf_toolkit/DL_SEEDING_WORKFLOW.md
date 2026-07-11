# DL-Seeding Pipeline — Step-by-Step Workflow (for teammates)

How to run the **CellPose → CNMF** detection pipeline on your own recording, end to end.
The pipeline spans **two notebooks** because the heavy AI model needs a GPU:

1. **Colab notebook** (`notebooks/cellpose_colab.ipynb`) — runs **CellPose-SAM** on a
   free cloud GPU to find the cells → outputs a **cell mask**.
2. **Local notebook** (`notebooks/OPCal_cell detection_caiman_150226_dl-seeding.ipynb`) — turns that
   mask into CNMF seeds and extracts each cell's **activity trace** → the final result.

> **Why two machines?** CellPose-SAM is a large transformer; on a CPU it takes 20+ min per image,
> so it runs on Colab's GPU (seconds). CNMF/CaImAn runs fine locally. Colab can't see your laptop's
> disk, so you move one small file up (the projection) and one small file back (the mask) by hand.

---

## What you need to change (only 3 paths — they're hard-coded)

Everything else is fixed. For your own recording you edit **three filenames** (the folder paths are
relative to the repo, so they keep working as long as you don't move things):

| Variable | In which cell | Set it to |
|---|---|---|
| `video_path` | top of the local notebook | your movie in `data/RawData/…tif` |
| `annotation_path` | top of the local notebook | your manual tags in `data/TaggedData/…tif` |
| `MASK_PATH` | the "Build CellPose seeds" cell | the CellPose mask you download from Colab |

---

## Step by step

### Step 0 — one-time setup
- Clone the repo; create the env: `conda env create -f environment.yml` → `conda activate cv-celldetection`.
- Put your movie in `data/RawData/` and your manual tags in `data/TaggedData/`.

### Step 1 — point the notebook at your data
In the local `_dl-seeding` notebook, edit `video_path` and `annotation_path` (Step-0 table above).

### Step 2 — make the projection image (local)
CellPose needs a single 2D image, not the movie. Build it:
```
conda activate cv-celldetection
python cnmf_toolkit/cellpose_export_projection.py
```
This writes `data/results/comparisons/_proj_corr.tif` (+ mean/max). `_proj_corr.tif` is the one you upload.
*(For a different movie, pass it as an argument: `python cnmf_toolkit/cellpose_export_projection.py path/to/your_movie.tif`.)*

### Step 3 — find the cells on Colab (GPU)
1. Go to **colab.research.google.com** → **File → Upload notebook** → pick
   `notebooks/cellpose_colab.ipynb`.
2. **Runtime → Change runtime type → GPU** (T4 is fine).
3. Run **Cell 1** (installs CellPose). When it says so → **Runtime → Restart session**, then re-run Cell 1 & 2.
   - *If Cell 1 prints a `numba requires numpy<2.1` WARNING — ignore it, it's harmless. Do NOT pin numpy.*
4. **Cell 3/4 (upload):** choose your `_proj_corr.tif`.  ← **manual transfer UP**
5. **Cell 4 (load model) → the run cells:** run cpsam at `diameter=0`. For the cleanest result, also run
   the **`6c`** cell (min_size/cellprob) if you want a stricter mask.
6. The notebook **downloads a `.npy` mask** (e.g. `_seg_labels_corr_d0.npy`).  ← **manual transfer DOWN**

### Step 4 — extract activity in the local notebook
1. Put the downloaded `.npy` mask into `data/results/comparisons/`.
2. In the "Build CellPose seeds" cell, set `MASK_PATH` to that file.
3. Run the notebook top to bottom. It builds seeds → extracts traces (footprints frozen) → shows the
   overlay. Writes results to `data/results/debug_outputs/run_<timestamp>/`.

### Step 5 — score against the manual tags
```
python cnmf_toolkit/ground_truth_scorer.py \
  --annotation data/TaggedData/<your_tags>.tif --run <run_timestamp> --stage fit/final
```
Prints the counts + saves a color-coded overlay PNG to `data/results/comparisons/`.

---

## The notebook toggles (what each does; the winning defaults)

In the local `_dl-seeding` notebook:

| Toggle | Where | Default | What it does |
|---|---|---|---|
| `INTENSITY_WEIGHT` | Build-seeds cell | `True` | Soft footprints (`mask × brightness`) → tight ROIs, fewer edge-clip merges. |
| `JUNK_FILTER` | Junk-filter cell | `'min'` | Drops the dimmest-on-min-projection ~10% of seeds → removes dead/moving artifacts. `'mean'` = weak; `None` = off. |
| `RUN_REFIT` | Refit cell | `False` | OFF — refit re-grows the frozen footprints into merges. |
| `RUN_COMPONENT_EVAL` | Eval cell | `False` | OFF — CaImAn's SNR/rval junk filter; removes real faint cells here. |

**The winning config = the defaults:** `INTENSITY_WEIGHT=True`, `JUNK_FILTER='min'`, refit & eval OFF.

---

## Recap of the two manual transfers (the only "glue")

```
LOCAL  ──_proj_corr.tif──►  COLAB (GPU: CellPose)  ──_seg_labels_*.npy──►  LOCAL (CNMF)
        upload widget                                  download widget
```
That's the whole reason the pipeline is two notebooks. Everything else is automatic.

*(Smoother options, if this gets used a lot: put all 3 paths in one config cell; or mount Google Drive
in Colab so the files sync instead of manual upload/download. Ask if you want that set up.)*

---

## Troubleshooting

- **Colab: `numpy _no_nep50_warning` / `_blas_supports_fpe` on `import cellpose`** → you didn't restart
  after Cell 1, or numpy got pinned. Fix: `Runtime → Restart session` (or Disconnect & delete runtime),
  keep Cell 1 as plain `!pip install cellpose` (no numpy pin), re-run.
- **Local: mask shape mismatch assert** → the mask was made from a different recording's projection than
  the movie/annotation you set. Re-export the projection (Step 2) for THIS recording and re-run CellPose.
- **The heavy CellPose run is slow / no GPU locally** → that's expected; use Colab. Don't run cpsam on CPU.
