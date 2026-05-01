"""
sofi_helpers — CNMF debugging, configuration, and visualization toolkit.

Modules
-------
debug_tracker   : CNMFDebugTracker — saves matrices/images at each CNMF stage.
cnmf_manager    : CNMFManager — run CNMF with named parameter configurations.
gdrive_uploader : GDriveUploader — upload debug outputs to Google Drive.
interactive_cnmf_viewer : Launch an interactive napari-based stage viewer.

Sub-packages
------------
viewer : Interactive napari viewer components (StageStore, plotting, etc.).
"""

from .debug_tracker import CNMFDebugTracker
from .gdrive_uploader import GDriveUploader


def __getattr__(name):
    """Lazy import for CNMFManager to avoid circular import with cnmf.py."""
    if name == "CNMFManager":
        from .cnmf_manager import CNMFManager
        return CNMFManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CNMFDebugTracker",
    "CNMFManager",
    "GDriveUploader",
]
