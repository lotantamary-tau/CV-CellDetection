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
STAGE_DEFINITIONS = {
    'init':       {'order': 1, 'name': 'Initial Detection',  'key': '1'},
    'spatial_1':  {'order': 2, 'name': 'Spatial Update 1',   'key': '2'},
    'temporal_1': {'order': 3, 'name': 'Temporal Update 1',  'key': '3'},
    'merge':      {'order': 4, 'name': 'Component Merging',  'key': '4'},
    'spatial_2':  {'order': 5, 'name': 'Spatial Update 2',   'key': '5'},
    'temporal_2': {'order': 6, 'name': 'Temporal Update 2',  'key': '6'},
    'final':      {'order': 7, 'name': 'Final Results',      'key': '7'},
    'cnn':        {'order': 8, 'name': 'CNN Evaluation',      'key': '8'},
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
