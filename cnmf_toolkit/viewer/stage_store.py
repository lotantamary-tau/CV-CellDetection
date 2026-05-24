"""Lazy-loading stage catalogue for CNMF debug outputs (multi-run hierarchy).

The ``StageStore`` class scans a base directory that contains one or more
``run_<id>/<phase>/`` subfolders, each holding stage files:

    <stage>.npz                  Dense matrices for that stage
    <stage>_<sparse_key>.npz     Sparse matrices (e.g. {stage}_A.npz)
    metadata_<stage>.txt         Shape/size info

The set of stages present depends on which CNMF configuration ran (e.g. the
notebook's patches-based fit produces ``patches_init``, ``patches_merge``,
``patches_temporal``, ``final`` while the runner's no-patches config produces
``preprocess``, ``init``, ``spatial_1``, ..., ``final``). ``STAGE_DEFINITIONS``
in ``viewer/__init__.py`` is treated as **optional metadata** (nice display
names, canonical pipeline order). Any stage file present on disk gets
catalogued, even if not listed in ``STAGE_DEFINITIONS``.

The store tracks a "current run" and "current phase" so the viewer can
navigate between runs and phases (fit vs refit) without re-scanning the disk.
"""

from __future__ import annotations

import re
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
        self.npz_path = npz_path              # dense bundle ({stage}.npz)
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
        log.info("Loading matrices for stage: %s …", self.info.get('name', self.name))
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
            log.debug("Unloading stage: %s", self.info.get('name', self.name))
            self.matrices = None
            self.metadata = None


# Module-level helper for stage ordering when STAGE_DEFINITIONS doesn't include
# a stage. Used by _ordered_stages().
def _stage_sort_key(name: str, info: Dict) -> tuple:
    """Sort key: known stages by their declared 'order'; unknown stages alphabetically after known ones."""
    if 'order' in info:
        return (0, info['order'])
    return (1, name)


class StageStore:
    """Manages a catalogue of CNMF debug stage files across runs and phases."""

    def __init__(self, debug_dir):
        self.debug_dir = Path(debug_dir)
        # Map: run_id -> {phase_name: {stage_name: StageEntry}}
        self.runs: Dict[str, Dict[str, Dict[str, StageEntry]]] = {}
        self.current_run_id: Optional[str] = None
        self.current_phase: Optional[str] = None
        self._scan()
        self._init_current()

    def _scan(self) -> None:
        """Walk debug_dir/run_*/<phase>/<stage>.npz and build the catalogue.

        Dynamically discovers any stage name present on disk (not limited to
        STAGE_DEFINITIONS). Empty phases / empty runs are skipped.
        """
        if not self.debug_dir.exists():
            log.warning("debug_dir does not exist: %s", self.debug_dir)
            return

        run_re = re.compile(r"^run_(\d{8}_\d{6})$")
        for run_path in sorted(self.debug_dir.iterdir()):
            if not run_path.is_dir():
                continue
            m = run_re.match(run_path.name)
            if not m:
                continue
            run_id = m.group(1)

            phases: Dict[str, Dict[str, StageEntry]] = {}
            for phase_path in sorted(run_path.iterdir()):
                if not phase_path.is_dir():
                    continue
                phase_name = phase_path.name  # 'fit' or 'refit'

                stages: Dict[str, StageEntry] = {}
                # Find every <stage>.npz file (excluding sparse <stage>_<key>.npz)
                for npz_path in sorted(phase_path.glob("*.npz")):
                    stem = npz_path.stem
                    # Sparse files look like {stage}_{key}.npz. We need the
                    # main dense file which is {stage}.npz. Check whether
                    # stem contains an underscore-suffix that matches a
                    # known matrix-key shape — but simpler: a {stage}.npz
                    # exists only if there's NO corresponding stage-without-
                    # this-suffix file. The cleanest discrimination is to
                    # look for the metadata_<stage>.txt — that confirms it's
                    # a real stage entry (since metadata only exists per
                    # stage, not per sparse-key).
                    if not (phase_path / f"metadata_{stem}.txt").exists():
                        continue
                    stage_name = stem

                    info = STAGE_DEFINITIONS.get(stage_name, {
                        'name': stage_name.replace('_', ' ').title(),
                        'order': 999,  # unknown stages sort last
                    })

                    # Sparse matrices: {stage}_{key}.npz
                    sparse_paths: Dict[str, Path] = {}
                    for spath in phase_path.glob(f"{stage_name}_*.npz"):
                        suffix = spath.stem[len(stage_name) + 1:]
                        if suffix:
                            sparse_paths[suffix] = spath

                    metadata_path = phase_path / f"metadata_{stage_name}.txt"

                    stages[stage_name] = StageEntry(
                        name=stage_name,
                        info=info,
                        npz_path=npz_path,
                        sparse_paths=sparse_paths,
                        metadata_path=metadata_path,
                    )
                    log.info(
                        "Found run=%s phase=%s stage=%s",
                        run_id, phase_name, stage_name,
                    )

                if stages:
                    phases[phase_name] = stages
            if phases:
                self.runs[run_id] = phases

        log.info("Scanned %d run(s) in %s", len(self.runs), self.debug_dir)

    def _init_current(self) -> None:
        """Pick the default (most recent run, prefer refit phase)."""
        if not self.runs:
            return
        # Most recent run by timestamp (the IDs sort lexicographically by date)
        self.current_run_id = sorted(self.runs.keys())[-1]
        phases = self.runs[self.current_run_id]
        self.current_phase = 'refit' if 'refit' in phases else (
            'fit' if 'fit' in phases else next(iter(phases))
        )

    # ------------------------------------------------------------------
    # Public API — operates on the CURRENT run+phase
    # ------------------------------------------------------------------
    def _current_stages(self) -> Dict[str, "StageEntry"]:
        """Return the stages dict for the active run+phase, or empty."""
        if self.current_run_id is None or self.current_phase is None:
            return {}
        return self.runs.get(self.current_run_id, {}).get(self.current_phase, {})

    def __contains__(self, name: str) -> bool:
        return name in self._current_stages()

    def __getitem__(self, name: str) -> "StageEntry":
        return self._current_stages()[name]

    def __len__(self) -> int:
        return len(self._current_stages())

    def __bool__(self) -> bool:
        return len(self._current_stages()) > 0

    def __iter__(self):
        """Iterate stage names of the CURRENT run+phase in pipeline order.

        Stages with a declared 'order' in STAGE_DEFINITIONS sort first by that
        order. Unknown stages sort after, alphabetically.
        """
        stages = self._current_stages()
        return iter(
            sorted(stages, key=lambda s: _stage_sort_key(s, stages[s].info))
        )

    def items(self):
        """Iterate (stage_name, StageEntry) tuples in pipeline order."""
        stages = self._current_stages()
        for name in iter(self):
            yield name, stages[name]

    def best_initial_stage(self) -> str:
        """Return 'final' if available in current selection, else last stage in order."""
        stages = self._current_stages()
        if not stages:
            raise RuntimeError("No stages available in current selection.")
        if 'final' in stages:
            return 'final'
        # Last stage in pipeline order
        return list(self)[-1]

    def load(self, name: str) -> None:
        entry = self._current_stages()[name]
        entry.load()

    def unload(self, name: str) -> None:
        stages = self._current_stages()
        if name in stages:
            stages[name].unload()

    # ------------------------------------------------------------------
    # Run / phase navigation (used by the viewer's keybindings)
    # ------------------------------------------------------------------
    def available_runs(self) -> list:
        """Sorted list of run_ids, oldest first."""
        return sorted(self.runs.keys())

    def available_phases(self, run_id: Optional[str] = None) -> list:
        """List of phase names present in the given (or current) run."""
        run_id = run_id or self.current_run_id
        if run_id is None or run_id not in self.runs:
            return []
        return list(self.runs[run_id].keys())

    def switch_run(self, run_id: str) -> bool:
        """Switch active run. Returns True if switch succeeded.

        Phase is ALWAYS reset to refit (if present), else fit, else first.
        No preservation of the previous run's phase — consistent behavior
        matters more than minimal surprise.
        """
        if run_id not in self.runs:
            log.warning("switch_run: unknown run_id '%s'", run_id)
            return False
        self.current_run_id = run_id
        phases = self.runs[run_id]
        self.current_phase = 'refit' if 'refit' in phases else (
            'fit' if 'fit' in phases else next(iter(phases))
        )
        return True

    def switch_phase(self, phase_name: str) -> bool:
        """Switch active phase within the current run. Returns True if it succeeded."""
        if self.current_run_id is None:
            return False
        phases = self.runs[self.current_run_id]
        if phase_name not in phases:
            log.warning(
                "switch_phase: phase '%s' not present in run %s",
                phase_name, self.current_run_id,
            )
            return False
        self.current_phase = phase_name
        return True

    def previous_run(self) -> Optional[str]:
        """Circular: return the run_id of the run before the current one.

        Wraps to the last run if currently at the oldest. Returns None only
        if there are no runs at all.
        """
        runs = self.available_runs()
        if not runs or self.current_run_id is None:
            return None
        try:
            idx = runs.index(self.current_run_id)
        except ValueError:
            return None
        return runs[idx - 1] if idx > 0 else runs[-1]

    def next_run(self) -> Optional[str]:
        """Circular: return the run_id of the run after the current one.

        Wraps to the first run if currently at the newest. Returns None only
        if there are no runs at all.
        """
        runs = self.available_runs()
        if not runs or self.current_run_id is None:
            return None
        try:
            idx = runs.index(self.current_run_id)
        except ValueError:
            return None
        return runs[idx + 1] if idx + 1 < len(runs) else runs[0]

    def previous_stage(self) -> Optional[str]:
        """Circular: return the previous stage name in the current phase's pipeline order.

        Wraps to the last stage if currently at the first. Returns None if
        no stages are loaded.
        """
        stages = list(self)
        if not stages:
            return None
        try:
            idx = stages.index(self.current_stage_name())
        except (ValueError, RuntimeError):
            return stages[0]
        return stages[idx - 1] if idx > 0 else stages[-1]

    def next_stage(self) -> Optional[str]:
        """Circular: return the next stage name in the current phase's pipeline order."""
        stages = list(self)
        if not stages:
            return None
        try:
            idx = stages.index(self.current_stage_name())
        except (ValueError, RuntimeError):
            return stages[0]
        return stages[idx + 1] if idx + 1 < len(stages) else stages[0]

    def current_stage_name(self) -> Optional[str]:
        """Return the name of the stage the viewer is currently displaying.

        StageStore itself doesn't track the active stage (the viewer does),
        so this is provided as an override hook. Default returns None;
        the viewer can set ``store.current_stage_name = lambda: self.current_stage``
        or override on a subclass. In our setup the viewer sets it via the
        attribute ``_current_stage_name`` (set by the viewer when it switches).
        """
        return getattr(self, '_current_stage_name', None)

    def previous_phase(self) -> Optional[str]:
        """Circular: return the previous phase in the current run."""
        if self.current_run_id is None:
            return None
        phases = list(self.runs[self.current_run_id].keys())
        if not phases:
            return None
        try:
            idx = phases.index(self.current_phase)
        except ValueError:
            return phases[0]
        return phases[idx - 1] if idx > 0 else phases[-1]

    def next_phase(self) -> Optional[str]:
        """Circular: return the next phase in the current run."""
        if self.current_run_id is None:
            return None
        phases = list(self.runs[self.current_run_id].keys())
        if not phases:
            return None
        try:
            idx = phases.index(self.current_phase)
        except ValueError:
            return phases[0]
        return phases[idx + 1] if idx + 1 < len(phases) else phases[0]

    def other_phase(self) -> Optional[str]:
        """Return the OTHER phase in the current run, or None if only one exists."""
        if self.current_run_id is None:
            return None
        phases = list(self.runs[self.current_run_id].keys())
        if len(phases) != 2:
            return None
        return phases[0] if phases[1] == self.current_phase else phases[1]


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
