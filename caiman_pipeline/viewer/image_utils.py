"""
Image-processing helpers for CNMF viewer.

Functions for creating ROI label maps, reference summary images, and
converting between sparse / dense matrix formats.
"""

from __future__ import annotations

import numpy as np

from . import log


# ---------------------------------------------------------------------------
# Matrix helpers
# ---------------------------------------------------------------------------

def dense(A):
    """Convert a sparse matrix to a dense ndarray (no-op if already dense)."""
    return A.toarray() if hasattr(A, 'toarray') else np.asarray(A)


def get_n_components(matrices: dict) -> int:
    """Return number of spatial components from a matrices dict, or 0."""
    A = matrices.get('A')
    if A is not None and A.ndim >= 2:
        return A.shape[1]
    return 0


def get_n_frames(matrices: dict) -> int:
    """Return number of frames from C matrix, or 0."""
    C = matrices.get('C')
    if C is not None and C.ndim >= 2:
        return C.shape[1]
    return 0


# ---------------------------------------------------------------------------
# ROI labels (fully vectorised)
# ---------------------------------------------------------------------------

def create_roi_labels(A_spatial, threshold: float = 1e-10):
    """
    Create a label image from spatial components (fully vectorised).

    Parameters
    ----------
    A_spatial : ndarray, shape (h, w, n_components)
        Spatial footprints reshaped to image dimensions.
    threshold : float
        Minimum spatial weight to consider a pixel active.

    Returns
    -------
    labels : ndarray, shape (h, w), dtype int32
        Each pixel contains the 1-based label of its dominant component
        (0 = background).
    """
    max_vals = np.max(A_spatial, axis=2)
    best_roi = np.argmax(A_spatial, axis=2)

    h, w = max_vals.shape
    labels = np.zeros((h, w), dtype=np.int32)
    active = max_vals > threshold
    labels[active] = best_roi[active] + 1  # 1-based

    n_labels = len(np.unique(labels[labels > 0]))
    log.info(
        "Created %d ROI labels covering %d pixels",
        n_labels, np.count_nonzero(labels),
    )
    return labels


# ---------------------------------------------------------------------------
# Reference summary images
# ---------------------------------------------------------------------------

def create_reference_images(A_dense, C, dims):
    """
    Build reference summary images from CNMF spatial/temporal matrices.

    Returns
    -------
    mean_components, max_projection, reconstructed_mean, component_density

    Notes
    -----
    CaImAn stores pixels in Fortran (column-major) order, so all reshapes
    use ``order='F'`` with the original ``(d1, d2)`` dimensions.
    """
    d1, d2 = dims[0], dims[1]

    mean_components = np.mean(A_dense, axis=1).reshape(d1, d2, order='F')
    max_projection = np.max(A_dense, axis=1).reshape(d1, d2, order='F')

    # Efficient reconstruction mean: A @ mean(C) == mean(A @ C)
    # Avoids allocating the full (n_pixels × n_frames) matrix.
    mean_C = np.mean(C, axis=1)
    reconstructed_mean = (A_dense @ mean_C).reshape(d1, d2, order='F')

    density_threshold = np.max(A_dense) * 0.01
    component_density = np.sum(A_dense > density_threshold, axis=1).reshape(
        d1, d2, order='F',
    )

    return mean_components, max_projection, reconstructed_mean, component_density
