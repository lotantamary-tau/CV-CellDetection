#!/usr/bin/env python3
"""
Interactive CNMF Debug Stage Viewer

View and switch between CNMF processing stages (init, spatial_1, temporal_1,
merge, spatial_2, temporal_2, final, cnn) in napari with clickable ROIs and
matplotlib trace analysis.

Controls:
    1-8        Switch between debug stages
    SPACE      Analyze ROI at cursor position
    S          Print stage info and statistics
    I          Show pixel component values
    Click ROI  Detailed component analysis

Usage:
    python cnmf_viewer.py
"""

import os
import signal
import sys

# macOS Qt compatibility
os.environ['QT_MAC_WANTS_LAYER'] = '1'
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'

import napari

from viewer import CNMFDebugStageViewer, HDF5Viewer, log


def main():
    print("=" * 60)
    print("  CNMF Debug Stage Viewer")
    print("=" * 60)

    viewer = CNMFDebugStageViewer()

    if not viewer.store:
        log.info("Falling back to HDF5 results...")
        result = HDF5Viewer.load_results()
        if result is None:
            log.error("No results found. Run CNMF with --debug first.")
            return
        A, C, b, f_bg, dims = result
        HDF5Viewer.launch(A, C, dims, b, f_bg)
        return

    if viewer.viewer is None:
        log.error("Viewer failed to initialise")
        return

    def _sigint(signum, frame):
        log.info("Interrupted -- closing viewer")
        viewer.viewer.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sigint)

    try:
        napari.run()
    except Exception as exc:
        log.error("Viewer error: %s", exc)
    finally:
        if viewer.viewer is not None:
            try:
                viewer.viewer.close()
            except Exception:
                pass
        log.info("Viewer closed")


if __name__ == "__main__":
    main()

