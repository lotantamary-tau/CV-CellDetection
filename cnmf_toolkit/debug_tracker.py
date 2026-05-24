
import os
import logging
import datetime
import numpy as np
import scipy.sparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.ndimage import center_of_mass

logger = logging.getLogger("caiman")


class CNMFDebugTracker:
    """Tracks and saves all CNMF matrices at each pipeline stage.

    Outputs are organized as:

        <save_dir>/run_<run_id>/<phase>/<stage_name>.npz
        <save_dir>/run_<run_id>/<phase>/<stage_name>_<sparse_key>.npz
        <save_dir>/run_<run_id>/<phase>/metadata_<stage_name>.txt
        ...

    where ``run_id`` is a timestamp (auto-generated at construction) and
    ``phase`` is one of ``'fit'`` (default) or ``'refit'`` (set explicitly by
    the notebook via ``set_phase('refit')``).

    Args:
        save_dir: Directory to write outputs into. Defaults to env var
            ``CNMF_DEBUG_DIR`` or ``<repo>/data/results/debug_outputs/``
            (computed relative to this file so the path works from any CWD).
            The actual run folder is appended below this.
        enabled: If False, all ``save_stage`` calls become no-ops.
        run_id: Run identifier (used in the subfolder name). Defaults to
            the current timestamp ``YYYYMMDD_HHMMSS``.
        default_phase: Initial phase. Defaults to ``'fit'`` so the runner
            (which never calls ``set_phase``) automatically writes to
            ``run_<id>/fit/``.
        gdrive_folder_id: Google Drive folder ID to upload files to.
            Falls back to env var ``GDRIVE_FOLDER_ID``.  Set to enable
            automatic upload of every debug file to Google Drive.
        gdrive_service_account_key: Path to service-account JSON key.
            Falls back to env var ``GDRIVE_SERVICE_ACCOUNT_KEY``.
        gdrive_client_secret: Path to OAuth client-secret JSON.
            Falls back to env var ``GDRIVE_CLIENT_SECRET``.
        gdrive_delete_local: If True, delete each local file after it has
            been uploaded to Google Drive (saves disk space).
    """

    def __init__(self, save_dir=None, enabled=True,
                 run_id=None, default_phase='fit',
                 gdrive_folder_id=None, gdrive_service_account_key=None,
                 gdrive_client_secret=None, gdrive_delete_local=False):
        # Resolve base dir (the parent of all run_<id>/ subfolders)
        if save_dir is None:
            # Default: <repo>/data/results/debug_outputs/, computed relative to
            # this file so it works regardless of CWD. CNMF_DEBUG_DIR env var
            # overrides for users who want a custom location.
            _default = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "data", "results", "debug_outputs",
            )
            save_dir = os.environ.get("CNMF_DEBUG_DIR", _default)
        self.base_dir = save_dir

        # Auto-generate a run_id from current timestamp if not provided.
        if run_id is None:
            run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_id = run_id

        self.current_phase = default_phase
        self.enabled = enabled
        self.gdrive_delete_local = gdrive_delete_local
        self._gdrive = None  # lazy-initialised on first use

        # Compute the active save_dir = base/run_<id>/<phase>/ and create it
        self._refresh_save_dir()

        # ---- Google Drive setup (optional) --------------------------------
        folder_id = gdrive_folder_id or os.environ.get("GDRIVE_FOLDER_ID")
        if folder_id and self.enabled:
            try:
                from .gdrive_uploader import GDriveUploader
                self._gdrive = GDriveUploader(
                    folder_id=folder_id,
                    service_account_key=gdrive_service_account_key,
                    client_secret=gdrive_client_secret,
                )
                # Create a session sub-folder named after the run_id
                self._gdrive.create_session_folder(
                    f"cnmf_debug_{self.run_id}"
                )
                print("[CNMFDebugTracker] Google Drive upload ENABLED")
            except Exception as exc:
                logger.warning(
                    "Google Drive upload requested but setup failed: %s", exc
                )
                self._gdrive = None

    # ------------------------------------------------------------------
    # Phase / enabled state management
    # ------------------------------------------------------------------
    def _refresh_save_dir(self):
        """Recompute self.save_dir = base/run_<id>/<phase>/ and mkdir if enabled."""
        self.save_dir = os.path.join(
            self.base_dir, f"run_{self.run_id}", self.current_phase
        )
        if self.enabled:
            os.makedirs(self.save_dir, exist_ok=True)

    def set_phase(self, name):
        """Switch the phase subfolder. Subsequent save_stage calls write here."""
        self.current_phase = name
        self._refresh_save_dir()

    def enable(self):
        """Re-enable snapshot writing. Idempotent."""
        self.enabled = True
        self._refresh_save_dir()

    def disable(self):
        """Stop writing snapshots. Subsequent save_stage calls are no-ops."""
        self.enabled = False

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def save_stage(self, stage_name, dims=None, max_rois=100,
                   max_components=10, **matrices):
        """Persist every matrix passed as a keyword argument.

        Files land at ``self.save_dir/{stage_name}.npz``,
        ``self.save_dir/{stage_name}_<sparse_key>.npz``, and
        ``self.save_dir/metadata_{stage_name}.txt`` — one set per stage per
        phase per run. Calls in the same phase with the same stage_name
        overwrite previous files (which is fine because one
        algorithm pass produces each stage exactly once).
        """
        if not self.enabled:
            return

        print(f"\n========== [CNMFDebugTracker] Saving stage: "
              f"'{stage_name}' (run={self.run_id}, phase={self.current_phase}) ==========")

        # --- separate sparse vs dense values ---------------------------------
        sparse_dict = {}
        dense_dict = {}
        for key, val in matrices.items():
            if val is None:
                continue
            if scipy.sparse.issparse(val):
                sparse_dict[key] = val
            else:
                dense_dict[key] = np.asarray(val)

        # Save dense arrays in a single compressed npz
        if dense_dict:
            npz_path = os.path.join(self.save_dir, f"{stage_name}.npz")
            np.savez_compressed(npz_path, **dense_dict)
            print(f"[CNMFDebugTracker] Dense arrays saved to {npz_path} "
                  f"with keys: {list(dense_dict.keys())}")

        # Save sparse matrices individually (keeps them sparse on disk)
        for key, val in sparse_dict.items():
            sp_path = os.path.join(self.save_dir, f"{stage_name}_{key}.npz")
            scipy.sparse.save_npz(sp_path, val.tocsc())
            print(f"[CNMFDebugTracker] Sparse {key} saved to {sp_path} "
                  f"(shape={val.shape}, nnz={val.nnz})")

        # Metadata text file
        self._save_metadata(stage_name, dims, {**dense_dict, **sparse_dict})

        # Save masks as PNG (needs dense A, so only densify the ROIs we plot)
        if 'A' in matrices and matrices['A'] is not None and dims is not None:
            self._save_masks_as_png(stage_name, matrices['A'],
                                    dims, max_rois)

        # Plot YrA traces
        if 'YrA' in dense_dict:
            self._plot_YrA_traces(stage_name, dense_dict['YrA'],
                                  max_components)

        # ---- Upload to Google Drive if configured -------------------------
        if self._gdrive is not None:
            self._upload_stage_files(stage_name)

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------
    def _upload_stage_files(self, stage_name):
        """Upload all files belonging to this stage to Google Drive."""
        prefix_patterns = [
            f"{stage_name}.npz",
            f"{stage_name}_",        # sparse matrices
            f"metadata_{stage_name}.txt",
            f"ROI_",                 # ROI PNGs include stage_name in their filename
            f"YrA_traces_{stage_name}.png",
        ]
        uploaded = []
        for fname in sorted(os.listdir(self.save_dir)):
            fpath = os.path.join(self.save_dir, fname)
            if not os.path.isfile(fpath):
                continue
            if not any(
                fname.startswith(p) and f"{stage_name}" in fname
                for p in prefix_patterns
            ):
                continue
            try:
                self._gdrive.upload_file(fpath)
                uploaded.append(fname)
                if self.gdrive_delete_local:
                    os.remove(fpath)
            except Exception as exc:
                logger.warning(
                    "GDrive upload failed for %s: %s", fname, exc
                )
        if uploaded:
            print(f"[CNMFDebugTracker] Uploaded {len(uploaded)} file(s) "
                  f"to Google Drive for stage '{stage_name}'")

    def _save_metadata(self, stage_name, dims, matrices):
        path = os.path.join(self.save_dir, f"metadata_{stage_name}.txt")
        with open(path, "w") as f:
            f.write(f"Stage: {stage_name}\n")
            f.write(f"Run ID: {self.run_id}\n")
            f.write(f"Phase: {self.current_phase}\n")
            for key, val in matrices.items():
                shape = val.shape if hasattr(val, 'shape') else 'N/A'
                if scipy.sparse.issparse(val):
                    f.write(f"{key} shape: {shape} (sparse, nnz={val.nnz})\n")
                else:
                    f.write(f"{key} shape: {shape}\n")
            f.write(f"dims: {dims}\n")
        print(f"  Saved metadata to {path}")

    def _save_masks_as_png(self, stage_name, A, dims, max_rois=100):
        try:
            is_sparse = scipy.sparse.issparse(A)
            n_components = A.shape[1]
            n_plot = min(n_components, max_rois)
            for i in range(n_plot):
                col = A[:, i]
                if is_sparse:
                    col = col.toarray().ravel()
                else:
                    col = np.asarray(col).ravel()
                mask = col.reshape(dims, order='F') > 0
                if not np.any(mask):
                    continue
                cy, cx = center_of_mass(mask)
                x0 = max(0, int(cx) - 20)
                y0 = max(0, int(cy) - 20)
                crop = mask[y0:y0 + 40, x0:x0 + 40]
                fig, ax = plt.subplots()
                ax.imshow(crop, cmap="gray")
                ax.set_title(f"ROI {i} ({stage_name})")
                ax.axis('off')
                path = os.path.join(self.save_dir,
                                    f"ROI_{i}_{stage_name}.png")
                plt.savefig(path)
                plt.close(fig)
        except Exception as e:
            logger.warning(f"Failed to save mask PNGs for {stage_name}: {e}")

    def _plot_YrA_traces(self, stage_name, YrA, max_components=10):
        try:
            if YrA is None or YrA.size == 0:
                logger.warning(f"YrA is empty at {stage_name}")
                return
            K, T = YrA.shape if YrA.ndim == 2 else (1, YrA.size)
            n_plot = min(K, max_components)
            fig, axes = plt.subplots(n_plot, 1, figsize=(12, 2 * n_plot))
            if n_plot == 1:
                axes = [axes]
            for i in range(n_plot):
                trace = YrA[i, :] if YrA.ndim == 2 else YrA
                axes[i].plot(trace, color='blue', linewidth=1)
                axes[i].set_title(
                    f'YrA Residual Component {i} ({stage_name})')
                axes[i].set_ylabel('Residual')
                if i == n_plot - 1:
                    axes[i].set_xlabel('Time (frames)')
            plt.tight_layout()
            save_path = os.path.join(
                self.save_dir, f"YrA_traces_{stage_name}.png")
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            print(f"  Saved YrA traces to {save_path}")
        except Exception as e:
            logger.warning(f"Failed to plot YrA traces for {stage_name}: {e}")
