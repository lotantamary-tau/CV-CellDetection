#!/usr/bin/env python
"""Export projections of the movie to small image files for the Colab CellPose run.

Colab won't have CaImAn (needed for the correlation image), so we build the
projections HERE (in cv-celldetection) and save them. You then upload the tiny
projection files to the Colab notebook, run cpsam_v2 on the GPU there, and bring
the label masks back to score locally.

Usage (repo root, cv-celldetection env):
    python cnmf_toolkit/cellpose_export_projection.py [path/to/movie.tif]

Outputs (data/results/comparisons/):
    _proj_mean.tif / .npy   mean projection   (normalized [0,1] float32)
    _proj_max.tif  / .npy   max projection
    _proj_corr.tif / .npy   CaImAn local-correlation image (recommended first)
Upload the .tif files to Colab (they're ~1 MB each, 512x512).
"""
import os
import sys
import numpy as np
import tifffile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))     # cnmf_toolkit/ -> repo root
_DEFAULT_MOVIE = os.path.join(REPO, 'data', 'RawData', '20250409_3_Glut_1mM_TIF_VIDEO.tif')
MOVIE = sys.argv[1] if len(sys.argv) > 1 else _DEFAULT_MOVIE
OUTDIR = os.path.join(REPO, 'data', 'results', 'comparisons')
os.makedirs(OUTDIR, exist_ok=True)


def norm01(a):
    a = a.astype('float32')
    return np.nan_to_num((a - np.nanmin(a)) / (np.ptp(a) + 1e-9), nan=0.0)


print(f'[export] loading movie: {MOVIE}')
mv = tifffile.imread(MOVIE).astype('float32')      # (T, H, W)
print(f'[export] movie shape {mv.shape}')

projs = {'mean': mv.mean(0), 'max': mv.max(0)}
print('[export] building CaImAn local-correlation image ...')
from caiman.summary_images import local_correlations
projs['corr'] = local_correlations(mv, swap_dim=False)

for kind, proj in projs.items():
    img = norm01(proj)
    tif = os.path.join(OUTDIR, f'_proj_{kind}.tif')
    npy = os.path.join(OUTDIR, f'_proj_{kind}.npy')
    tifffile.imwrite(tif, img)
    np.save(npy, img)
    print(f'[export] {kind}: shape {img.shape}  ->  {tif}')

print('[export] done. Upload the _proj_*.tif files to the Colab notebook '
      '(cellpose_colab.ipynb). Recommended: start with _proj_corr.tif.')
