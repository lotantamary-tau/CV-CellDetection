#!/usr/bin/env python3
"""
Pixel Signal Comparison Tool

Compare the raw fluorescence signals from two pixel locations in the original
movie.  Provide two (x, y) coordinates and the script extracts the time-series
from each location, then shows an interactive matplotlib figure with:

  - Both raw traces overlaid
  - Each trace individually
  - Scatter plot & Pearson correlation
  - Cross-correlation lag analysis
  - Summary statistics table

Usage:
    python compare_pixels.py X1 Y1 X2 Y2
    python compare_pixels.py 120 85 130 90
    python compare_pixels.py 120 85 130 90 --movie /path/to/movie.tif
"""

import argparse
import json
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)

import numpy as np

import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt

from pathlib import Path


# ------------------------------------------------------------------
# Movie loading helpers
# ------------------------------------------------------------------
def find_movie_path() -> str | None:
    """Auto-detect movie path from the most recent cnmf_results config,
    or fall back to the newest TIFF file under sofi_helpers."""

    # 1) Try config files saved by cnmf_manager
    for base in [
        Path(_THIS_DIR) / 'cnmf_results',
        Path('cnmf_results'),
    ]:
        if not base.exists():
            continue
        configs = sorted(
            base.glob("config_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for cfg_path in configs:
            try:
                with open(cfg_path) as fh:
                    cfg = json.load(fh)
                fnames = (cfg.get('params') or {}).get('fnames')
                if fnames and isinstance(fnames, list) and fnames[0]:
                    return fnames[0]
                # Also check opts_dict.fnames
                fnames2 = (cfg.get('params', {})
                           .get('opts_dict', {})
                           .get('fnames'))
                if fnames2 and isinstance(fnames2, list) and fnames2[0]:
                    return fnames2[0]
            except Exception:
                continue

    # 2) Fall back: find the most recent TIFF under the sofi_helpers tree
    tiffs = sorted(
        Path(_THIS_DIR).rglob("*_VIDEO.tif"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if tiffs:
        return str(tiffs[0])

    # 3) Any .tif at all
    tiffs = sorted(
        Path(_THIS_DIR).rglob("*.tif"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if tiffs:
        return str(tiffs[0])

    return None


def load_movie(path: str) -> np.ndarray:
    """Load a TIFF movie and return an array of shape (T, H, W)."""
    from imageio.v3 import imread
    movie = imread(path)
    if movie.ndim == 2:
        # single frame
        movie = movie[np.newaxis, ...]
    print(f"Movie loaded: {movie.shape}  (T={movie.shape[0]}, "
          f"H={movie.shape[1]}, W={movie.shape[2]})")
    return movie


# ------------------------------------------------------------------
# Analysis / plotting
# ------------------------------------------------------------------
def compare_signals(
    movie: np.ndarray,
    x1: int, y1: int,
    x2: int, y2: int,
) -> None:
    """Extract and compare the signals at two pixel locations."""

    T, H, W = movie.shape

    # Validate bounds
    for label, x, y in [("Point 1", x1, y1), ("Point 2", x2, y2)]:
        if not (0 <= y < H and 0 <= x < W):
            print(f"ERROR: {label} ({x}, {y}) is out of bounds "
                  f"(image size {W} x {H})")
            sys.exit(1)

    # Extract time-series  (movie is T×H×W, indexing is [t, row, col])
    sig1 = movie[:, y1, x1].astype(np.float64)
    sig2 = movie[:, y2, x2].astype(np.float64)
    frames = np.arange(T)

    # ---- thresholds for activity detection (mean + 1 std) ----
    thresh1 = sig1.mean() + sig1.std()
    thresh2 = sig2.mean() + sig2.std()
    active1 = (sig1 > thresh1).astype(np.float64)
    active2 = (sig2 > thresh2).astype(np.float64)

    # ---- running standard deviation (cumulative) ----
    cum_std1 = np.array([sig1[:i+1].std() for i in range(T)])
    cum_std2 = np.array([sig2[:i+1].std() for i in range(T)])

    # ---- figure ----
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    fig.suptitle(
        f"Pixel Comparison:  ({x1}, {y1})  vs  ({x2}, {y2})",
        fontsize=14, fontweight='bold',
    )

    # (0,0) Mean Intensity Comparison
    ax = axes[0, 0]
    ax.plot(frames, sig1, color='blue', linewidth=0.8, label='Region 1')
    ax.plot(frames, sig2, color='red', linewidth=0.8, label='Region 2')
    ax.axhline(thresh1, ls='--', color='blue', lw=0.7, alpha=0.7,
               label=f'Region 1 threshold')
    ax.axhline(thresh2, ls='--', color='red', lw=0.7, alpha=0.7,
               label=f'Region 2 threshold')
    ax.legend(fontsize=7)
    ax.set_title("Mean Intensity Comparison")
    ax.set_xlabel("Frame")
    ax.set_ylabel("Intensity")

    # (0,1) Activity Detection Comparison
    ax = axes[0, 1]
    ax.bar(frames[active1 > 0], active1[active1 > 0],
           width=1.0, color='blue', alpha=0.6, label='Region 1 active')
    ax.bar(frames[active2 > 0], active2[active2 > 0],
           width=1.0, color='red', alpha=0.4, label='Region 2 active')
    ax.set_ylim(0, 1.15)
    ax.set_yticks([0, 0.5, 1.0])
    ax.legend(fontsize=8, loc='right')
    ax.set_title("Activity Detection Comparison")
    ax.set_xlabel("Frame")
    ax.set_ylabel("Activity")

    # (1,0) Spatial Variability (Standard Deviation) over time
    ax = axes[1, 0]
    ax.plot(frames, cum_std1, color='blue', linewidth=0.8, label='Region 1 std')
    ax.plot(frames, cum_std2, color='red', linewidth=0.8, label='Region 2 std')
    ax.fill_between(frames, 0, cum_std1, alpha=0.15, color='blue')
    ax.fill_between(frames, 0, cum_std2, alpha=0.15, color='red')
    ax.legend(fontsize=8)
    ax.set_title("Spatial Variability (Standard Deviation)")
    ax.set_xlabel("Frame")
    ax.set_ylabel("Standard Deviation")

    # (1,1) Region Verification — mean projection with pixel locations
    mean_img = np.mean(movie.astype(np.float64), axis=0)
    ax = axes[1, 1]
    ax.imshow(mean_img, cmap='gray')
    # Mark regions with small squares
    sq = 5  # half-size of marker square
    for (px, py, color, lbl) in [
        (x1, y1, 'red', f'R2: ({x1},{y1})'),
        (x2, y2, 'blue', f'R1: ({x2},{y2})'),
    ]:
        rect = plt.Rectangle((px - sq, py - sq), 2 * sq, 2 * sq,
                              linewidth=1.5, edgecolor=color, facecolor='none')
        ax.add_patch(rect)
        ax.text(px + sq + 3, py, lbl, color=color, fontsize=7,
                fontweight='bold', va='center')
    ax.set_title("Region Verification")
    ax.set_xlabel("X coordinate")
    ax.set_ylabel("Y coordinate")

    plt.tight_layout()
    plt.show()


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Compare raw fluorescence signals from two pixel locations",
    )
    parser.add_argument("x1", type=int, help="X coordinate of first pixel")
    parser.add_argument("y1", type=int, help="Y coordinate of first pixel")
    parser.add_argument("x2", type=int, help="X coordinate of second pixel")
    parser.add_argument("y2", type=int, help="Y coordinate of second pixel")
    parser.add_argument(
        "--movie", type=str, default=None,
        help="Path to TIFF movie (auto-detected from cnmf_results if omitted)",
    )
    args = parser.parse_args()

    # Resolve movie path
    movie_path = args.movie or find_movie_path()
    if movie_path is None:
        print("ERROR: Could not find movie file. "
              "Pass it explicitly with --movie /path/to/movie.tif")
        sys.exit(1)

    if not os.path.isfile(movie_path):
        print(f"ERROR: Movie file not found: {movie_path}")
        sys.exit(1)

    print(f"Movie : {movie_path}")
    print(f"Point 1: ({args.x1}, {args.y1})")
    print(f"Point 2: ({args.x2}, {args.y2})")
    print()

    movie = load_movie(movie_path)
    compare_signals(movie, args.x1, args.y1, args.x2, args.y2)


if __name__ == "__main__":
    main()
