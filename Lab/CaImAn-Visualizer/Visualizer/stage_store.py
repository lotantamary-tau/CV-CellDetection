"""
Lazy-loading stage catalogue for CNMF debug outputs.

The ``StageStore`` class scans a directory for stage files at init time but
does **not** load any matrix data until explicitly asked.  This keeps startup
fast and memory bounded regardless of how many stages exist on disk.

File-format contract (matches :class:`CNMFDebugTracker`):
    Dense arrays  → ``{stage}_{count}.npz``  (numpy compressed archive,
                     multiple keys like C, S, YrA, b, f, …)
    Sparse arrays → ``{stage}_{count}_{key}.npz``  (scipy.sparse format,
                     one matrix per file — typically A)
    Metadata      → ``metadata_{stage}_{count}.txt``
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import numpy as np
import scipy.sparse

from . import MATRIX_NAMES, STAGE_DEFINITIONS, log


class StageEntry:
    """One stage's file paths + lazily-loaded data."""

    __slots__ = (
        'name', 'info', 'npz_path', 'sparse_paths',
        'metadata_path', 'matrices', 'metadata',
    )

    def __init__(
        self,
        name: str,
        info: dict,
        npz_path: Path,
        sparse_paths: Dict[str, Path],
        metadata_path: Path,
    ):
        self.name = name
        self.info = info
        self.npz_path = npz_path              # dense bundle ({stage}_0.npz)
        self.sparse_paths = sparse_paths      # per-key sparse files
        self.metadata_path = metadata_path
        self.matrices: Optional[dict] = None
        self.metadata: Optional[dict] = None

    # ------------------------------------------------------------------
    @property
    def is_loaded(self) -> bool:
        return self.matrices is not None

    @property
    def n_components(self) -> int:
        A = (self.matrices or {}).get('A')
        if A is not None and hasattr(A, 'shape') and A.ndim >= 2:
            return A.shape[1]
        return 0

    @property
    def n_frames(self) -> int:
        C = (self.matrices or {}).get('C')
        if C is not None and hasattr(C, 'shape') and C.ndim >= 2:
            return C.shape[1]
        return 0

    # ------------------------------------------------------------------
    def load(self) -> None:
        """Load matrix data from the files written by CNMFDebugTracker.

        Dense arrays are stored together in a single compressed ``.npz``
        archive (``numpy.savez_compressed``).  Sparse matrices are stored
        individually via ``scipy.sparse.save_npz``.
        """
        if self.is_loaded:
            return
        log.info("Loading matrices for stage: %s …", self.info['name'])
        self.matrices = {}

        # 1. Dense bundle — extract every array from the npz archive
        if self.npz_path and self.npz_path.exists():
            try:
                with np.load(str(self.npz_path), allow_pickle=True) as npz:
                    for key in npz.files:
                        arr = npz[key]
                        self.matrices[key] = arr
                        log.info("  %s: %s (dense)", key, arr.shape)
            except Exception as exc:
                log.warning("  Failed to load dense bundle %s: %s",
                            self.npz_path, exc)

        # 2. Sparse matrices — one scipy-sparse npz per key
        for mat_name, mat_path in self.sparse_paths.items():
            try:
                sp = scipy.sparse.load_npz(str(mat_path))
                self.matrices[mat_name] = sp
                log.info("  %s: %s (sparse, nnz=%d)",
                         mat_name, sp.shape, sp.nnz)
            except Exception as exc:
                log.warning("  Failed to load sparse %s from %s: %s",
                            mat_name, mat_path, exc)

        self.metadata = _load_metadata(self.metadata_path)

    def unload(self) -> None:
        """Release matrix data to free memory."""
        if self.is_loaded:
            log.debug("Unloading stage: %s", self.info['name'])
            self.matrices = None
            self.metadata = None


class StageStore:
    """
    Manages a catalogue of CNMF debug stage files.

    Scans the directory once and provides load/unload per stage so that
    only one stage needs to reside in memory at a time.
    """

    def __init__(self, debug_dir: str):
        self.debug_dir = Path(debug_dir)
        self.stages: Dict[str, StageEntry] = {}
        self._scan()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def __contains__(self, name: str) -> bool:
        return name in self.stages

    def __getitem__(self, name: str) -> StageEntry:
        return self.stages[name]

    def __len__(self) -> int:
        return len(self.stages)

    def __bool__(self) -> bool:
        return len(self.stages) > 0

    def __iter__(self):
        """Iterate stage names in pipeline order."""
        return iter(
            sorted(self.stages, key=lambda s: self.stages[s].info['order'])
        )

    def items(self):
        for name in self:
            yield name, self.stages[name]

    def best_initial_stage(self) -> str:
        """Return 'final' if available, otherwise the highest-order stage."""
        if 'final' in self.stages:
            return 'final'
        return max(self.stages, key=lambda s: self.stages[s].info['order'])

    def load(self, name: str) -> StageEntry:
        entry = self.stages[name]
        entry.load()
        return entry

    def unload(self, name: str) -> None:
        self.stages[name].unload()

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------
    def _scan(self) -> None:
        if not self.debug_dir.exists():
            log.error("Debug directory not found: %s", self.debug_dir)
            return

        for stage_name, info in STAGE_DEFINITIONS.items():
            # The dense bundle created by CNMFDebugTracker
            npz_path = self.debug_dir / f"{stage_name}_0.npz"
            if not npz_path.exists():
                if stage_name == 'cnn':
                    log.info("CNN stage not found (optional)")
                else:
                    log.warning("Stage file missing: %s", npz_path)
                continue

            # Sparse matrices are saved individually as
            # {stage}_{count}_{key}.npz  (via scipy.sparse.save_npz)
            sparse_paths: Dict[str, Path] = {}
            for mat_name in MATRIX_NAMES:
                sp_path = self.debug_dir / f"{stage_name}_0_{mat_name}.npz"
                if sp_path.exists():
                    sparse_paths[mat_name] = sp_path

            metadata_path = self.debug_dir / f"metadata_{stage_name}_0.txt"

            # Peek into the dense bundle to report which keys it contains
            dense_keys: list[str] = []
            try:
                with np.load(str(npz_path), allow_pickle=True) as npz:
                    dense_keys = list(npz.files)
            except Exception:
                pass

            self.stages[stage_name] = StageEntry(
                name=stage_name,
                info=info,
                npz_path=npz_path,
                sparse_paths=sparse_paths,
                metadata_path=metadata_path,
            )

            all_keys = sorted(set(dense_keys) | set(sparse_paths.keys()))
            log.info(
                "Found stage %-12s  matrices: %s",
                stage_name, ', '.join(all_keys) if all_keys else '(none)',
            )

        log.info("Scanned %d stages in %s", len(self.stages), self.debug_dir)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _load_metadata(path: Path) -> dict:
    """Load a simple ``key: value`` metadata text file."""
    metadata: dict = {}
    if not path.exists():
        return metadata
    try:
        with open(path, 'r') as fh:
            for line in fh:
                if ':' in line:
                    key, value = line.strip().split(':', 1)
                    metadata[key.strip()] = value.strip()
    except Exception as exc:
        log.warning("Failed to load metadata %s: %s", path, exc)
    return metadata
