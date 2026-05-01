"""
HDF5 fallback viewer for CNMF results.

When debug-stage outputs are not present, :func:`launch` loads the most recent
``cnmf_results_*.hdf5`` and opens a simpler napari viewer with ROI click
analysis.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import napari
import h5py
import scipy.sparse

from . import log
from .image_utils import create_reference_images, create_roi_labels
from .plotting import ComponentPlotter


class HDF5Viewer:
    """Thin wrapper around the HDF5 fallback viewer."""

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    @staticmethod
    def load_results(results_dir: str = "./cnmf_results"):
        """Load the most recent CNMF HDF5 results file.

        Returns
        -------
        tuple or None
            ``(A, C, b, f_bg, dims)`` if found, else *None*.
        """
        results_path = Path(results_dir)
        hdf5_files = sorted(
            results_path.glob("cnmf_results_*.hdf5"),
            key=lambda p: p.stat().st_mtime,
        )
        if not hdf5_files:
            log.error("No CNMF HDF5 results found in %s", results_dir)
            return None

        latest = hdf5_files[-1]
        log.info("Loading HDF5: %s", latest)

        with h5py.File(latest, 'r') as fh:
            dims = fh['dims'][()]
            est = fh['estimates']
            A_grp = est['A']
            A_sparse = scipy.sparse.csc_matrix((
                A_grp['data'][()],
                A_grp['indices'][()],
                A_grp['indptr'][()],
            ), shape=A_grp['shape'][()])
            A = A_sparse.toarray()
            C = est['C'][()]
            b = est['b'][()] if 'b' in est else None
            f_bg = est['f'][()] if 'f' in est else None

        log.info("A %s  C %s  dims %s", A.shape, C.shape, dims)
        return A, C, b, f_bg, dims

    # ------------------------------------------------------------------
    # Video helpers
    # ------------------------------------------------------------------
    @staticmethod
    def try_load_video():
        """Search common relative paths for the original TIF video."""
        from imageio.v3 import imread

        here = Path(__file__).parent
        candidates = [
            here / '20250409_3_Glut_1mM' / '20250409_3_Glut_1mM_TIF_VIDEO.TIF',
            here.parent / '20250409_3_Glut_1mM' / '20250409_3_Glut_1mM_TIF_VIDEO.TIF',
        ]
        for path in candidates:
            if path.exists():
                try:
                    vid = imread(str(path))
                    log.info("Loaded video: %s  shape %s", path, vid.shape)
                    return vid[:300]
                except Exception as exc:
                    log.warning("Error loading %s: %s", path, exc)
        log.info("Original video not found -- will use reconstructed data")
        return None

    # ------------------------------------------------------------------
    # Launch viewer
    # ------------------------------------------------------------------
    @staticmethod
    def launch(A, C, dims, b=None, f_bg=None):
        """Launch a basic napari viewer from HDF5 results (no stage switching)."""
        d1, d2 = dims[0], dims[1]
        n_comp = A.shape[1]

        viewer = napari.Viewer(title=f"CNMF Viewer -- {n_comp} components")

        video = HDF5Viewer.try_load_video()
        if video is None:
            mean_C = np.mean(C, axis=1)
            reconstructed = (A @ mean_C).reshape(d1, d2, order='F')
            viewer.add_image(
                reconstructed, name="Reconstructed Mean", colormap='gray',
            )
        else:
            viewer.add_image(video, name="Raw Video", colormap='gray')
            mean_img = np.mean(video[:50], axis=0)
            viewer.add_image(
                mean_img, name="Mean Image", colormap='gray',
                blending='additive', visible=True,
            )

        # Reference layers
        _, max_proj, _, _ = create_reference_images(A, C, dims)
        viewer.add_image(
            max_proj, name="Max Projection", colormap='hot',
            visible=False, blending='additive',
        )

        # ROI labels
        A_spatial = A.reshape(d1, d2, n_comp, order='F')
        roi_labels = create_roi_labels(A_spatial)
        labels_layer = viewer.add_labels(
            roi_labels,
            name=f"ROIs ({n_comp} components)",
            opacity=0.7,
        )
        viewer.layers.selection.active = labels_layer

        # Precompute reconstructed traces for click analysis
        Yr = A @ C

        @labels_layer.mouse_drag_callbacks.append
        def _on_click(layer, event):
            if event.type != 'mouse_press':
                yield
                while event.type == 'mouse_move':
                    yield
                return
            coords = layer.world_to_data(event.position)
            y, x = int(coords[-2]), int(coords[-1])
            roi_id = (
                layer.data[y, x]
                if (0 <= y < d2 and 0 <= x < d1)
                else 0
            )
            if roi_id == 0:
                yield
                return
            ComponentPlotter.plot_hdf5_component(
                A_spatial, C, Yr, roi_id - 1, d1, d2,
            )
            yield
            while event.type == 'mouse_move':
                yield

        @viewer.bind_key('space', overwrite=True)
        def _space(viewer):
            pos = viewer.cursor.position
            y, x = int(pos[-2]), int(pos[-1])
            roi_id = (
                labels_layer.data[y, x]
                if (0 <= y < d2 and 0 <= x < d1)
                else 0
            )
            if roi_id > 0:
                ComponentPlotter.plot_hdf5_component(
                    A_spatial, C, Yr, roi_id - 1, d1, d2,
                )

        log.info("HDF5 viewer ready -- click/SPACE on ROIs for analysis")
        try:
            napari.run()
        except RuntimeError:
            return viewer
