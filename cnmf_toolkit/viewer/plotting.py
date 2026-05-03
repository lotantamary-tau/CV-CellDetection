"""
Matplotlib plotting for CNMF component analysis.

The :class:`ComponentPlotter` provides static methods that produce
2×3 analysis figures for individual components.  Both the debug-stage
viewer and the HDF5 fallback viewer share this code.
"""

from __future__ import annotations

import numpy as np

import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt


class ComponentPlotter:
    """Reusable matplotlib component analysis plots."""

    # ------------------------------------------------------------------
    # Debug-stage component analysis (A, C, S, YrA)
    # ------------------------------------------------------------------
    @staticmethod
    def plot_debug_component(
        comp_id: int,
        matrices: dict,
        stage_name: str,
        dims: tuple | None,
    ) -> None:
        """
        Plot spatial footprint, temporal trace, deconvolved spikes,
        residual, statistics, and mean A*C reconstruction.
        """
        from .image_utils import dense

        A = matrices.get('A')
        C = matrices.get('C')
        if A is None or C is None or A.ndim < 2 or C.ndim < 2:
            return
        if comp_id >= A.shape[1] or comp_id >= C.shape[0]:
            return

        spatial = dense(A)[:, comp_id]
        temporal = C[comp_id, :]

        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle(f"Component {comp_id} -- {stage_name}", fontsize=16)

        # Spatial footprint
        ax = axes[0, 0]
        if dims:
            ax.imshow(spatial.reshape(dims, order='F'), cmap='viridis')
        else:
            ax.plot(spatial)
        ax.set_title("Spatial Footprint")

        # Temporal trace
        ax = axes[0, 1]
        ax.plot(temporal)
        ax.set_title("Temporal Trace")
        ax.set_xlabel("Frame")
        ax.set_ylabel("Activity")

        # Deconvolved spikes (S)
        ax = axes[0, 2]
        S = matrices.get('S')
        if S is not None and comp_id < S.shape[0]:
            ax.plot(S[comp_id, :], color='green', linewidth=0.8)
            ax.set_title("Deconvolved (S)")
            ax.set_xlabel("Frame")
        else:
            ax.set_title("Deconvolved (N/A)")
            ax.axis('off')

        # Residual (YrA)
        ax = axes[1, 0]
        YrA = matrices.get('YrA')
        if YrA is not None and comp_id < YrA.shape[0]:
            ax.plot(YrA[comp_id, :], color='gray', linewidth=0.8)
            ax.set_title("Residual (YrA)")
            ax.set_xlabel("Frame")
        else:
            ax.set_title("Residual (N/A)")
            ax.axis('off')

        # Statistics text
        ax = axes[1, 1]
        spatial_max = np.max(spatial)
        spatial_area = int(np.sum(spatial > 0.1 * spatial_max))
        stats = (
            f"Component ID : {comp_id}\n"
            f"Stage        : {stage_name}\n"
            f"Max spatial  : {spatial_max:.4f}\n"
            f"Active pixels: {spatial_area}\n"
            f"Max temporal : {np.max(temporal):.3f}\n"
            f"Std temporal : {np.std(temporal):.3f}\n"
            f"Range        : {np.ptp(temporal):.3f}"
        )
        ax.text(
            0.1, 0.5, stats, transform=ax.transAxes, fontsize=10,
            verticalalignment='center', fontfamily='monospace',
            bbox=dict(boxstyle="round", facecolor='wheat'),
        )
        ax.set_title("Statistics")
        ax.axis('off')

        # A*C mean reconstruction
        ax = axes[1, 2]
        if dims:
            recon = (spatial * np.mean(temporal)).reshape(dims, order='F')
            im = ax.imshow(recon, cmap='viridis')
            ax.set_title("A*C Mean Reconstruction")
            plt.colorbar(im, ax=ax, shrink=0.6)
        else:
            ax.plot(spatial * np.mean(temporal), color='green')
            ax.set_title("A*C (1D)")

        plt.tight_layout()
        plt.show()

    # ------------------------------------------------------------------
    # HDF5 component analysis (A_spatial, C, Yr)
    # ------------------------------------------------------------------
    @staticmethod
    def plot_hdf5_component(
        A_spatial, C, Yr, idx: int, d1: int, d2: int,
    ) -> None:
        """
        Matplotlib analysis plot for an HDF5-loaded component.

        Shows spatial footprint, A*C mean, raw vs CNMF traces, scatter,
        quality metrics bar chart, and activity histogram.
        """
        spatial = A_spatial[:, :, idx]
        trace_c = C[idx]

        mask = spatial > 0
        pix = np.where(mask.flatten(order='F'))[0]
        trace_y = Yr[pix].mean(axis=0) if len(pix) else np.zeros_like(trace_c)
        corr = np.corrcoef(trace_y, trace_c)[0, 1] if len(trace_c) > 1 else 0

        fig, axes = plt.subplots(2, 3, figsize=(16, 9))
        fig.suptitle(f"Component {idx}  --  corr={corr:.3f}", fontsize=16)

        axes[0, 0].imshow(spatial, cmap='hot')
        axes[0, 0].set_title("Spatial")

        axes[0, 1].imshow(spatial * np.mean(trace_c), cmap='viridis')
        axes[0, 1].set_title("A*C Mean")

        t = np.arange(len(trace_c))
        axes[0, 2].plot(t, trace_y, label='Raw (Y)', alpha=0.8)
        axes[0, 2].plot(t, trace_c, label='CNMF (C)')
        axes[0, 2].legend()
        axes[0, 2].set_title("Traces")

        axes[1, 0].scatter(
            trace_y, trace_c, c=t, cmap='viridis', s=15, alpha=0.6,
        )
        axes[1, 0].set_title(f"Scatter  r={corr:.3f}")
        axes[1, 0].set_xlabel("Y")
        axes[1, 0].set_ylabel("C")

        metrics = {
            'Correlation': corr,
            'SNR est.': np.mean(trace_c) / (np.std(trace_c) + 1e-8),
            'Peak/Base': np.ptp(trace_c) / (np.mean(trace_c) + 1e-8),
            'Spatial Max': np.max(spatial),
        }
        axes[1, 1].bar(
            metrics.keys(), metrics.values(),
            color=['#E74C3C', '#3498DB', '#F39C12', '#27AE60'],
        )
        axes[1, 1].set_title("Quality Metrics")
        axes[1, 1].tick_params(axis='x', rotation=30)

        axes[1, 2].hist(
            trace_c, bins=30, color='#E74C3C', edgecolor='k', lw=0.5,
        )
        axes[1, 2].axvline(np.mean(trace_c), ls='--', color='blue', label='mean')
        axes[1, 2].legend()
        axes[1, 2].set_title("Activity Distribution")

        plt.tight_layout()
        plt.show()

    # ------------------------------------------------------------------
    # Component overview (top-N activity summary)
    # ------------------------------------------------------------------
    @staticmethod
    def plot_component_overview(
        C,
        stage_name: str,
        n_top: int = 15,
    ) -> None:
        """
        Show a summary figure of component activity for the current stage.

        Top row: bar chart of max activity per component (top N highlighted).
        Bottom row: temporal traces of the top N components stacked.
        """
        n = C.shape[0]
        max_act = np.max(C, axis=1)
        mean_act = np.mean(C, axis=1)
        std_act = np.std(C, axis=1)
        top_ids = np.argsort(max_act)[::-1][:n_top]

        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        fig.suptitle(f"Component Overview — {stage_name} ({n} components)",
                     fontsize=16, fontweight='bold')

        # (0,0) Bar chart of all component max activity
        ax = axes[0, 0]
        colors = ['#E74C3C' if i in top_ids else '#BDC3C7'
                  for i in range(n)]
        ax.bar(range(n), max_act, color=colors, width=1.0)
        ax.set_xlabel("Component ID")
        ax.set_ylabel("Max Activity")
        ax.set_title(f"All Components (top {n_top} in red)")

        # (0,1) Sorted max activity + SNR estimate
        ax = axes[0, 1]
        snr = mean_act / (std_act + 1e-10)
        ax.scatter(max_act, snr, s=12, alpha=0.6, c='#3498DB')
        for cid in top_ids[:5]:
            ax.annotate(str(cid), (max_act[cid], snr[cid]),
                        fontsize=8, color='red')
        ax.set_xlabel("Max Activity")
        ax.set_ylabel("SNR (mean/std)")
        ax.set_title("Activity vs SNR")

        # (1,0) Top-N traces stacked
        ax = axes[1, 0]
        offset = 0
        for rank, cid in enumerate(top_ids):
            trace = C[cid, :]
            trace_norm = trace / (np.max(np.abs(trace)) + 1e-10)
            ax.plot(trace_norm + offset, linewidth=0.7,
                    label=f"#{cid}" if rank < 5 else None)
            ax.text(-10, offset + 0.5, str(cid), fontsize=7, ha='right',
                    color='gray')
            offset += 1.2
        ax.set_xlabel("Frame")
        ax.set_ylabel("Component (stacked)")
        ax.set_title(f"Top {n_top} Traces")
        ax.set_yticks([])

        # (1,1) Table of top components
        ax = axes[1, 1]
        ax.axis('off')
        table_data = []
        for rank, cid in enumerate(top_ids, 1):
            table_data.append([
                f"{rank}",
                f"{cid}",
                f"{max_act[cid]:.3f}",
                f"{mean_act[cid]:.3f}",
                f"{std_act[cid]:.3f}",
                f"{snr[cid]:.2f}",
            ])
        table = ax.table(
            cellText=table_data,
            colLabels=["Rank", "ID", "Max", "Mean", "Std", "SNR"],
            loc='center',
            cellLoc='center',
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.0, 1.3)
        ax.set_title(f"Top {n_top} Components", pad=20)

        plt.tight_layout()
        plt.show()
