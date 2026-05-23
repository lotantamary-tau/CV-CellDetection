"""
viewer — Interactive CNMF Debug Stage Viewer package.

Modules
-------
stage_store    : Lazy-loading stage catalogue (StageStore).
image_utils    : ROI label creation, reference images, matrix helpers.
plotting       : Matplotlib component analysis (ComponentPlotter).
stage_viewer   : Napari viewer with stage switching (CNMFDebugStageViewer).
results_viewer : Fallback HDF5-based viewer (HDF5Viewer).
"""

import logging
import os

# ---------------------------------------------------------------------------
# Logging — one shared logger for the whole package
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-7s | %(message)s",
)
log = logging.getLogger("viewer")

# ---------------------------------------------------------------------------
# Constants shared across the package
# ---------------------------------------------------------------------------
# Catalogue of all stage names that instrumented_cnmf.py may emit, with
# their canonical position in the CNMF pipeline. Multiple stage names can
# share an 'order' when they are alternatives — e.g. 'init' and
# 'patches_init' both occupy "stage 1" but only one fires per configuration
# (non-patches vs patches mode), so they never coexist in the same phase
# folder. The viewer's stage_store does dynamic discovery: any *.npz file
# present on disk gets catalogued, even if the stage name is not listed
# here — unknown stages just sort last (order=999) with a default display
# name. F1-F7 keys are bound dynamically to the Nth stage in pipeline
# order within the current phase, not to specific stage names.
STAGE_DEFINITIONS = {
    # Always-present preprocess step
    'preprocess':         {'order': 0,  'name': 'Preprocess'},
    # Initialization variants (mutually exclusive across configs)
    'init':               {'order': 1,  'name': 'Initial Detection'},
    'patches_init':       {'order': 1,  'name': 'Patches Init'},
    'only_init_final':    {'order': 1,  'name': 'Only-Init Final'},
    # Spatial / temporal updates (non-patches vs patches variants)
    'spatial_1':          {'order': 2,  'name': 'Spatial Update 1'},
    'patches_spatial':    {'order': 2,  'name': 'Patches Spatial'},
    'temporal_1':         {'order': 3,  'name': 'Temporal Update 1'},
    'patches_temporal_1': {'order': 3,  'name': 'Patches Temporal 1'},
    'merge':              {'order': 4,  'name': 'Component Merging'},
    'patches_merge':      {'order': 4,  'name': 'Patches Merge'},
    'spatial_2':          {'order': 5,  'name': 'Spatial Update 2'},
    'temporal_2':         {'order': 6,  'name': 'Temporal Update 2'},
    'patches_temporal_2': {'order': 6,  'name': 'Patches Temporal 2'},
    'patches_deconvolve': {'order': 7,  'name': 'Patches Deconvolve'},
    'patches_temporal':   {'order': 7,  'name': 'Patches Temporal'},
    # Final
    'final':              {'order': 8,  'name': 'Final Results'},
    'cnn':                {'order': 9,  'name': 'CNN Evaluation'},
}

MATRIX_NAMES = ('A', 'C', 'S', 'YrA', 'b', 'f')

DEFAULT_DEBUG_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', 'data', 'results', 'debug_outputs',
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
from .stage_viewer import CNMFDebugStageViewer   # noqa: E402
from .results_viewer import HDF5Viewer            # noqa: E402
from .stage_store import StageStore               # noqa: E402

__all__ = [
    'CNMFDebugStageViewer',
    'HDF5Viewer',
    'StageStore',
    'STAGE_DEFINITIONS',
    'MATRIX_NAMES',
    'DEFAULT_DEBUG_DIR',
    'log',
]
