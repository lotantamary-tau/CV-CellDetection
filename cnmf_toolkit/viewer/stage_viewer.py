"""
Napari-based interactive viewer for CNMF debug stages.

The :class:`CNMFDebugStageViewer` loads a :class:`StageStore`, displays one
stage at a time, and lets the user navigate runs/phases/stages via F-keys
(F1/F2 run, F3/F4 phase, F5/F6 stage; Ctrl+1..9 to jump) and analyse the
ROI under the cursor with SPACE — all while keeping only the active stage
in RAM.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import numpy as np
import napari

from . import DEFAULT_DEBUG_DIR, log
from .image_utils import (
    create_reference_images,
    create_roi_labels,
    dense,
    get_n_components,
    get_n_frames,
)
from .plotting import ComponentPlotter
from .stage_store import StageStore


class CNMFDebugStageViewer:
    """
    Interactive napari viewer for CNMF debug stages.

    Only the *active* stage's matrices are held in memory at a time.
    Switching stages unloads the previous data before loading the new one.
    """

    def __init__(self, debug_dir: str = DEFAULT_DEBUG_DIR):
        self.debug_dir = debug_dir
        self.store = StageStore(debug_dir)
        self.current_stage = ''
        self.viewer: napari.Viewer | None = None
        self.original_movie = None
        self.dims: tuple | None = None


        if not self.store:
            log.error("No debug stages found. Run CNMF with debug tracking first.")
            return

        # Pick initial stage
        self.current_stage = self.store.best_initial_stage()
        self.store._current_stage_name = self.current_stage
        self.store.load(self.current_stage)
        log.info("Starting with stage: %s", self.current_stage)

        self._load_original_movie()
        self._setup_viewer()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def _entry(self):
        """Shortcut for the current StageEntry."""
        return self.store[self.current_stage]

    @property
    def _matrices(self) -> dict:
        return self._entry.matrices or {}

    # ------------------------------------------------------------------
    # Movie loading
    # ------------------------------------------------------------------
    def _load_original_movie(self) -> None:
        """Try to load the original movie using the most recent config."""
        try:
            # Primary: hdf5/ as a sibling of debug_outputs/ under data/results/
            results_path = Path(self.debug_dir).parent / 'hdf5'
            if not results_path.exists():
                # Fallback: compute the canonical data/results/hdf5/ path from
                # this script's location (handles non-default debug_dir setups).
                results_path = Path(__file__).resolve().parents[2] / 'data' / 'results' / 'hdf5'
            if not results_path.exists():
                results_path = Path('cnmf_results')  # last-ditch CWD-relative fallback

            configs = sorted(
                results_path.glob("config_*.json"),
                key=lambda p: p.stat().st_mtime, reverse=True,
            )
            if not configs:
                log.info("No config files found -- original movie not loaded")
                return

            with open(configs[0]) as fh:
                cfg = json.load(fh)

            movie_path = cfg['params']['fnames'][0]
            log.info("Loading original movie: %s", movie_path)
            from imageio.v3 import imread
            self.original_movie = imread(movie_path)
            self.dims = (
                self.original_movie.shape[1:]
                if self.original_movie.ndim == 3
                else self.original_movie.shape
            )
            log.info("Movie shape: %s", str(self.original_movie.shape))
        except Exception as exc:
            log.warning("Could not load original movie: %s", exc)

    # ------------------------------------------------------------------
    # Viewer setup
    # ------------------------------------------------------------------
    def _setup_viewer(self) -> None:
        """Create the napari viewer and load the first stage."""
        info = self._entry.info
        self.viewer = napari.Viewer(
            title=f"CNMF Debug Viewer -- {info['name']}",
        )

        if self.original_movie is not None:
            self.viewer.add_image(
                self.original_movie,
                name="Original Movie",
                opacity=0.7,
                colormap='gray',
            )

        self._display_stage()
        self._bind_keys()
        self._bind_mouse()
        self.print_stage_info()

    # ------------------------------------------------------------------
    # Stage display
    # ------------------------------------------------------------------
    def _display_stage(self) -> None:
        """Display the currently-loaded stage. Removes old CNMF layers first."""
        # Remove previous CNMF layers (keep "Original Movie")
        to_remove = [
            lyr.name for lyr in self.viewer.layers
            if lyr.name != "Original Movie"
        ]
        for name in to_remove:
            try:
                self.viewer.layers.remove(name)
            except Exception:
                pass

        matrices = self._matrices
        A = matrices.get('A')
        if A is None or A.ndim < 2:
            log.warning("No valid A matrix for stage '%s'", self.current_stage)
            return

        # Infer image dimensions if not yet known
        if self.dims is None:
            n_pixels = A.shape[0]
            dim = int(np.sqrt(n_pixels))
            if dim * dim == n_pixels:
                self.dims = (dim, dim)
            else:
                log.error(
                    "Cannot infer image dims from A shape %s "
                    "(not square -- supply original movie)", str(A.shape),
                )
                return

        n_components = A.shape[1]
        log.info(
            "Loading %d components for stage '%s'",
            n_components, self.current_stage,
        )

        A_dense = dense(A)

        # Reshape using Fortran order (CaImAn stores pixels column-major)
        d1, d2 = self.dims
        A_spatial = A_dense.reshape(d1, d2, n_components, order='F')

        # ROI label layer (vectorised)
        roi_labels = create_roi_labels(A_spatial)
        self.viewer.add_labels(
            roi_labels,
            name=f"ROIs ({self.current_stage})",
            opacity=0.6,
        )

        # Max projection of spatial footprints
        max_proj = np.max(A_spatial, axis=2)
        self.viewer.add_image(
            max_proj,
            name=f"Max Projection ({self.current_stage})",
            opacity=0.8,
            visible=True,
            colormap='hot',
        )

        # Average projection of spatial footprints
        avg_proj = np.mean(A_spatial, axis=2)
        self.viewer.add_image(
            avg_proj,
            name=f"Avg Projection ({self.current_stage})",
            opacity=0.8,
            visible=False,
            colormap='viridis',
        )

        # Update title
        self.viewer.title = (
            f"CNMF Debug Viewer  |  Run {self.store.current_run_id}  |  "
            f"Phase {self.store.current_phase}  |  {self._entry.info['name']} "
            f"({n_components} components)"
        )

    # ------------------------------------------------------------------
    # Stage switching
    # ------------------------------------------------------------------
    def switch_stage(self, stage_name: str) -> None:
        """Switch to *stage_name*, lazily loading data and freeing the old."""
        if stage_name not in self.store:
            log.warning("Stage '%s' not available", stage_name)
            return
        if stage_name == self.current_stage:
            return

        self.store.unload(self.current_stage)
        self.current_stage = stage_name
        self.store._current_stage_name = stage_name
        self.store.load(self.current_stage)

        self._display_stage()
        self.print_stage_info()

    def _reload_current(self) -> None:
        """Reload after a run or phase switch.

        Policy B: always reset to best_initial_stage (final if present, else
        last stage in pipeline order). DO NOT preserve previous stage name.

        Also sweep-unloads every StageEntry across the whole store so the
        "(loaded)" marker reflects exactly the currently-displayed stage
        and stale matrices from prior visits don't sit in RAM.
        """
        # Sweep: unload everything that's loaded across all runs/phases
        for run_id, phases in self.store.runs.items():
            for phase_stages in phases.values():
                for entry in phase_stages.values():
                    if entry.is_loaded:
                        entry.unload()

        stages_now = list(self.store)
        if not stages_now:
            log.warning("_reload_current: no stages in current selection.")
            return

        # Policy B: always reset to best_initial_stage
        self.current_stage = self.store.best_initial_stage()
        self.store._current_stage_name = self.current_stage

        self.store.load(self.current_stage)
        self._display_stage()
        self.print_stage_info()

    # ------------------------------------------------------------------
    # Info display
    # ------------------------------------------------------------------
    def print_stage_info(self) -> None:
        """Print current stage statistics to the console."""
        entry = self._entry
        info = entry.info
        matrices = self._matrices

        print(f"\n{'=' * 60}")
        print(f"STAGE: {info['name'].upper()}")
        print(f"{'=' * 60}")
        print(f"Components : {get_n_components(matrices)}")
        print(f"Frames     : {get_n_frames(matrices)}")

        b = matrices.get('b')
        if b is not None and b.ndim >= 2:
            print(f"Background : {b.shape[1]} spatial components")

        meta = entry.metadata or {}
        if meta:
            print("Metadata:")
            for k, v in meta.items():
                print(f"  {k}: {v}")

        # Coarse-to-fine "you are here" map: runs -> phases -> stages.

        # All runs
        print("\nRuns (F1=prev, F2=next):")
        for run_id in self.store.available_runs():
            marker = ">> " if run_id == self.store.current_run_id else "   "
            print(f"  {marker}{run_id}")

        # Phases in the current run
        print("\nPhases in this run (F3=prev, F4=next):")
        for phase in self.store.available_phases():
            marker = ">> " if phase == self.store.current_phase else "   "
            print(f"  {marker}{phase}")

        # Stages in the current phase
        print("\nStages in this phase (F5=prev, F6=next, Ctrl+1..9 = jump):")
        for i, (sname, sentry) in enumerate(self.store.items(), start=1):
            marker = ">> " if sname == self.current_stage else "   "
            loaded = "(loaded)" if sentry.is_loaded else ""
            print(f"  {marker}{i}) {sentry.info['name']} {loaded}")

        print(
            "\nKeys: F1/F2 run | F3/F4 phase | F5/F6 stage | "
            "Ctrl+1..9 jump | S info | I component | SPACE = analyze ROI"
        )
        print(
            f"Run {self.store.current_run_id}  |  Phase {self.store.current_phase}"
        )

    # ------------------------------------------------------------------
    # Key bindings
    # ------------------------------------------------------------------
    def _bind_keys(self) -> None:
        # Navigation is paired prev/next, ordered coarse-to-fine scope:
        # runs (F1/F2) -> phases (F3/F4) -> stages (F5/F6). All circular.

        # F1 / F2: previous / next run (circular)
        @self.viewer.bind_key('F1', overwrite=True)
        def _prev_run(viewer):
            target = self.store.previous_run()
            if target is None:
                log.info("No runs available.")
                return
            if self.store.switch_run(target):
                log.info("Switched to run: %s", target)
                self._reload_current()

        @self.viewer.bind_key('F2', overwrite=True)
        def _next_run(viewer):
            target = self.store.next_run()
            if target is None:
                log.info("No runs available.")
                return
            if self.store.switch_run(target):
                log.info("Switched to run: %s", target)
                self._reload_current()

        # F3 / F4: previous / next phase (circular within current run)
        @self.viewer.bind_key('F3', overwrite=True)
        def _prev_phase(viewer):
            target = self.store.previous_phase()
            if target is None:
                log.info("No phases available.")
                return
            if self.store.switch_phase(target):
                log.info("Switched to phase: %s", target)
                self._reload_current()

        @self.viewer.bind_key('F4', overwrite=True)
        def _next_phase(viewer):
            target = self.store.next_phase()
            if target is None:
                log.info("No phases available.")
                return
            if self.store.switch_phase(target):
                log.info("Switched to phase: %s", target)
                self._reload_current()

        # F5 / F6: previous / next stage (circular within current phase)
        @self.viewer.bind_key('F5', overwrite=True)
        def _prev_stage(viewer):
            target = self.store.previous_stage()
            if target is None:
                log.info("No stages in current phase.")
                return
            self.switch_stage(target)

        @self.viewer.bind_key('F6', overwrite=True)
        def _next_stage(viewer):
            target = self.store.next_stage()
            if target is None:
                log.info("No stages in current phase.")
                return
            self.switch_stage(target)

        # Ctrl+1..Ctrl+9: direct jump to Nth stage in current phase
        for n in range(1, 10):
            key = f'Control-{n}'
            @self.viewer.bind_key(key, overwrite=True)
            def _jump_to(viewer, _n=n, _key=key):
                stages_now = list(self.store)
                idx = _n - 1
                if idx >= len(stages_now):
                    log.info("%s: no stage at position %d (current phase has %d stages)",
                             _key, _n, len(stages_now))
                    return
                target = stages_now[idx]
                self.switch_stage(target)

        # Existing info / interaction keys (unchanged):
        @self.viewer.bind_key('s', overwrite=True)
        def _info(viewer):
            self.print_stage_info()

        @self.viewer.bind_key('i', overwrite=True)
        def _comp_info(viewer):
            self._show_component_info()

        @self.viewer.bind_key('space', overwrite=True)
        def _space(viewer):
            pos = viewer.cursor.position
            if len(pos) >= 2:
                y, x = int(pos[-2]), int(pos[-1])
                self._analyze_roi_at(x, y)

    # ------------------------------------------------------------------
    # Mouse bindings
    # ------------------------------------------------------------------
    def _bind_mouse(self) -> None:
        """Bind click handler to ROI labels layer (deferred until layer exists)."""
        def _setup():
            time.sleep(0.5)
            roi_layer = self._find_roi_layer()
            if roi_layer is None:
                return

            @roi_layer.mouse_drag_callbacks.append
            def _on_click(layer, event):
                if event.type == 'mouse_press':
                    coords = layer.world_to_data(event.position)
                    if len(coords) >= 2:
                        y, x = int(coords[-2]), int(coords[-1])
                        self._analyze_roi_at(x, y)
                        yield
                while event.type == 'mouse_move':
                    yield

            log.info("Click handler attached to ROI layer")

        threading.Thread(target=_setup, daemon=True).start()

    # ------------------------------------------------------------------
    # ROI analysis
    # ------------------------------------------------------------------
    def _find_roi_layer(self):
        for layer in self.viewer.layers:
            if 'ROIs' in layer.name:
                return layer
        return None

    def _analyze_roi_at(self, x: int, y: int) -> None:
        """Look up the ROI label at (x, y) and analyse it."""
        roi_layer = self._find_roi_layer()
        if roi_layer is None:
            log.warning("No ROI layer found")
            return

        h, w = roi_layer.data.shape
        if not (0 <= y < h and 0 <= x < w):
            log.warning("Position (%d, %d) out of bounds (%d x %d)", x, y, w, h)
            return

        roi_id = roi_layer.data[y, x]
        if roi_id > 0:
            ComponentPlotter.plot_debug_component(
                comp_id=roi_id - 1,
                matrices=self._matrices,
                stage_name=self._entry.info['name'],
                dims=self.dims,
            )
        else:
            log.info("No ROI at (%d, %d)", x, y)

    # ------------------------------------------------------------------
    # Info helper
    # ------------------------------------------------------------------
    def _show_component_info(self) -> None:
        """Show a matplotlib figure with top component activity summary."""
        C = self._matrices.get('C')
        if C is None or C.ndim < 2:
            log.warning("No C matrix available")
            return

        n = C.shape[0]
        stage_name = self._entry.info['name']

        ComponentPlotter.plot_component_overview(
            C=C,
            stage_name=stage_name,
            n_top=15,
        )
