#!/usr/bin/env python
"""Convert a CellPose label mask -> CNMF-style _A.npz, so ground_truth_scorer.py
can score the segmentation directly (without running the full CNMF hybrid).

The scorer reshapes each footprint column with order='F' against the annotation
dims, so we Fortran-flatten each cell's binary mask into a column of a sparse
(H*W, n_cells) matrix — the same convention as CaImAn's spatial A and the
seeded-CNMF Ain contract.

Usage (from repo root, cv-celldetection env):
    python cnmf_toolkit/cellpose_mask_to_A.py [labels.npy]
        labels.npy : path to a label mask (default: data/results/comparisons/_seg_labels.npy)

Output:
    data/results/debug_outputs/run_cellpose/fit/final_A.npz
Then score with:
    python cnmf_toolkit/ground_truth_scorer.py \
        --annotation data/TaggedData/20250409_3_Glut_1mM_ROI_AllCells.tif \
        --run cellpose --stage fit/final --label cellpose-seg
"""
import os
import sys

import numpy as np
import scipy.sparse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))     # cnmf_toolkit/ -> repo root
DEFAULT_LBL = os.path.join(REPO, 'data', 'results', 'comparisons', '_seg_labels.npy')
OUT = os.path.join(REPO, 'data', 'results', 'debug_outputs', 'run_cellpose', 'fit', 'final_A.npz')

lbl_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LBL
lbl = np.load(lbl_path)
H, W = lbl.shape
n = int(lbl.max())
print(f'[mask_to_A] {lbl_path}  ->  {H}x{W}, {n} cells')

# one column per cell, Fortran-flattened (matches scorer's reshape(dims, order="F"))
cols = [(lbl == j).flatten(order='F').astype('float32') for j in range(1, n + 1)]
A = scipy.sparse.csc_matrix(np.array(cols).T)          # (H*W, n_cells)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
scipy.sparse.save_npz(OUT, A)
print(f'[mask_to_A] saved A {A.shape} (nnz={A.nnz}) -> {OUT}')
print('[mask_to_A] now score:  python cnmf_toolkit/ground_truth_scorer.py '
      '--annotation data/TaggedData/20250409_3_Glut_1mM_ROI_AllCells.tif '
      '--run cellpose --stage fit/final --label cellpose-seg')
