#!/usr/bin/env python3
"""
ground_truth_scorer.py — score CNMF detections against a manual ground-truth annotation.

Overlays each detected CNMF component (its spatial footprint) on the manual annotation and
reports, for a run:
    correct  — one detection on one cell
    merge    — one detection covering >= 2 cells
    split    — one cell covered by >= 2 detections
    junk     — a detection on no cell
    covered / missed — cells of the total
It also saves a color-coded 2-panel PNG (left: the ground-truth cells; right: the detections
classified over the annotation).

VERSION 1 — APPROXIMATE. The annotation is treated as a BINARY mask and touching cells are
separated by a watershed heuristic, so the counts are reliable for *relative* comparison
between runs/configs but are NOT exact per-cell accuracy. For exact accuracy (per-cell
IoU/Dice) we need a per-cell LABELLED annotation (each cell its own integer label) — the
planned v2 upgrade.

Usage (run from the repo root):
    python cnmf_toolkit/ground_truth_scorer.py --annotation data/TaggedData/<tags>.tif
    python cnmf_toolkit/ground_truth_scorer.py --annotation <tags>.tif --run 20260620_164007 --stage refit/final
    python cnmf_toolkit/ground_truth_scorer.py --annotation <tags>.tif --no-plot

Reads per-stage footprints written by the debug tracker under
data/results/debug_outputs/run_<id>/<phase>/<stage>_A.npz (see cnmf_toolkit/USAGE.md).
Only depends on numpy / scipy / scikit-image / tifffile / matplotlib (already in environment.yml).
"""
import argparse
import glob
import os
import sys

import numpy as np
import tifffile
import scipy.sparse
from scipy import ndimage
from skimage.segmentation import watershed
from skimage.feature import peak_local_max
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

# Repo root = parent of cnmf_toolkit/, so default data paths work regardless of CWD
# (matches cnmf_manager.py). Run from the repo root OR from inside cnmf_toolkit/.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_DEBUG_DIR = os.path.join(_REPO_ROOT, 'data', 'results', 'debug_outputs')
_DEFAULT_OUTPUT_DIR = os.path.join(_REPO_ROOT, 'data', 'results', 'comparisons')


def load_cells(annotation_path, min_sep):
    """Binary annotation TIF -> per-cell label image (watershed-separates touching cells)."""
    ann = tifffile.imread(annotation_path)
    ann_bin = ann > 0
    dims = ann.shape
    dist = ndimage.distance_transform_edt(ann_bin)
    coords = peak_local_max(dist, min_distance=min_sep, labels=ann_bin)
    markers = np.zeros(dims, dtype=int)
    markers[tuple(coords.T)] = np.arange(1, len(coords) + 1)
    lbl = watershed(-dist, markers, mask=ann_bin)
    return ann_bin, lbl, int(lbl.max()), dims


def find_footprints(run_dir, stage):
    """Locate the spatial-footprint .npz for the requested stage (or auto-pick the best)."""
    candidates = [stage] if stage else ['refit/evaluated', 'refit/final', 'fit/final']
    for st in candidates:
        path = os.path.join(run_dir, st + '_A.npz')
        if os.path.exists(path):
            return path, st
    raise FileNotFoundError(
        f"No footprint file (<stage>_A.npz) found in {run_dir} for stage(s): {candidates}")


def classify(A, lbl, ann_bin, n_cells, dims, thr_foot):
    """Classify each detection vs the ground-truth cells. Returns counts + plotting data."""
    K = A.shape[1]
    comp_cells = []                       # cells each detection overlaps
    cell_ncomp = np.zeros(n_cells + 1, int)
    foot = []                             # (footprint image, peak) per detection, for plotting
    for k in range(K):
        col = np.asarray(A[:, k].todense()).ravel()
        m = col.max()
        img = col.reshape(dims, order='F')        # Fortran order = CaImAn footprint <-> image alignment
        foot.append((img, m))
        if m <= 0:
            comp_cells.append(np.array([], int))
            continue
        hits = np.unique(lbl[(img > thr_foot * m) & ann_bin])
        hits = hits[hits > 0]
        comp_cells.append(hits)
        for c in hits:
            cell_ncomp[c] += 1
    correct, merge, split, junk = [], [], [], []
    for k in range(K):
        h = comp_cells[k]
        if len(h) == 0:
            junk.append(k)
        elif len(h) >= 2:
            merge.append(k)
        elif cell_ncomp[h[0]] >= 2:
            split.append(k)
        else:
            correct.append(k)
    covered = int((cell_ncomp[1:] >= 1).sum())
    split_cells = int((cell_ncomp[1:] >= 2).sum())
    missed = [c for c in range(1, n_cells + 1) if cell_ncomp[c] == 0]
    return dict(K=K, correct=correct, merge=merge, split=split, junk=junk,
                covered=covered, split_cells=split_cells, missed=missed, foot=foot)


def save_plot(lbl, ann_bin, n_cells, res, dims, label, out_path, thr_foot):
    """Two-panel color-coded overlay PNG."""
    fig, axes = plt.subplots(1, 2, figsize=(20, 10))
    rng = np.random.default_rng(0)
    cell_colors = rng.random((n_cells + 1, 3))
    cell_colors[0] = 0
    axes[0].imshow(lbl, cmap=ListedColormap(cell_colors), interpolation='nearest')
    axes[0].set_title(f'Ground-truth cells (separated): {n_cells}')
    axes[0].axis('off')

    axes[1].imshow(ann_bin, cmap='gray')
    for idxs, color in [(res['junk'], 'red'), (res['correct'], 'lime'),
                        (res['split'], 'deepskyblue'), (res['merge'], 'orange')]:
        for k in idxs:
            img, m = res['foot'][k]
            if m > 0:
                axes[1].contour(img, levels=[thr_foot * m], colors=color, linewidths=0.8)
    if res['missed']:
        cents = ndimage.center_of_mass(ann_bin, lbl, res['missed'])
        axes[1].plot([c[1] for c in cents], [c[0] for c in cents], 'x',
                     color='magenta', markersize=7, markeredgewidth=1.5)
    axes[1].set_title(
        f'{label}   |   cells={n_cells}, detections={res["K"]}\n'
        f'green correct={len(res["correct"])}  orange MERGE={len(res["merge"])}  '
        f'blue split={len(res["split"])}  red JUNK={len(res["junk"])}  '
        f'magenta-X missed={len(res["missed"])}')
    axes[1].axis('off')

    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    fig.savefig(out_path, dpi=130, bbox_inches='tight')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--annotation', required=True,
                        help='manual ground-truth TIF (binary all-cells mask). REQUIRED.')
    parser.add_argument('--run', default=None,
                        help='run id / folder name to score (default: the most recent run)')
    parser.add_argument('--debug-dir', default=_DEFAULT_DEBUG_DIR,
                        help='folder holding the run_* dirs (default: <repo>/data/results/debug_outputs)')
    parser.add_argument('--stage', default=None,
                        help="stage to score, e.g. 'refit/final' or 'fit/final' "
                             "(default: auto — refit/evaluated, else refit/final, else fit/final)")
    parser.add_argument('--output', default=_DEFAULT_OUTPUT_DIR,
                        help='directory for the PNG (default: <repo>/data/results/comparisons)')
    parser.add_argument('--label', default=None,
                        help='title + PNG file name (default: the run id)')
    parser.add_argument('--thr-foot', type=float, default=0.2,
                        help='footprint threshold = fraction of each detection peak (default 0.2)')
    parser.add_argument('--min-sep', type=int, default=5,
                        help='min pixels between cell centres for the watershed (default 5)')
    parser.add_argument('--no-plot', action='store_true',
                        help='print the counts only; do not save the PNG')
    args = parser.parse_args()

    ann_bin, lbl, n_cells, dims = load_cells(args.annotation, args.min_sep)
    print(f'ground-truth cells: {n_cells} (after watershed-separating touching cells)')

    if args.run:
        name = args.run if args.run.startswith('run_') else 'run_' + args.run
        run_dir = os.path.join(args.debug_dir, name)
        if not os.path.isdir(run_dir):
            sys.exit(f'Run not found: {run_dir}')
    else:
        runs = sorted(glob.glob(os.path.join(args.debug_dir, 'run_*')))
        if not runs:
            sys.exit(f'No run_* folders found under {args.debug_dir}')
        run_dir = runs[-1]

    Apath, stage = find_footprints(run_dir, args.stage)
    A = scipy.sparse.load_npz(Apath).tocsc()
    label = args.label or os.path.basename(run_dir)

    res = classify(A, lbl, ann_bin, n_cells, dims, args.thr_foot)
    print(f'run={os.path.basename(run_dir)}  stage={stage}  detections={res["K"]}')
    print(f'  correct={len(res["correct"])}  MERGE={len(res["merge"])}  '
          f'split={len(res["split"])}  JUNK={len(res["junk"])}')
    print(f'  cells covered={res["covered"]}/{n_cells}  missed={len(res["missed"])}  '
          f'split cells={res["split_cells"]}')

    if not args.no_plot:
        out_path = os.path.join(args.output, f'{label}.png')
        save_plot(lbl, ann_bin, n_cells, res, dims, label, out_path, args.thr_foot)
        print(f'Saved: {os.path.abspath(out_path)}')


if __name__ == '__main__':
    main()
