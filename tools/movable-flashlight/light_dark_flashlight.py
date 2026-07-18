#!/usr/bin/env python3
"""Full-frame light/dark differencing + 10-frame temporal stacking.

Deliberately NOT the tracked-bright-blob pipeline used by nullspace/
tournament/sector12 — this looks at EVERY pixel, both brightening and
darkening, frame-to-frame, across the whole frame, not gated to a residual
above a threshold near one moving object.

For each 10-frame sliding window [i, i+9]:
  - net_signed  = frame[i+9] - frame[i]              (drift over the window;
                                                        + = lightened, - = darkened)
  - accum_abs   = sum(|frame[k+1]-frame[k]|, k=i..i+8) (any activity, either
                                                        direction, accumulated)
  - min_proj    = per-pixel minimum over frames i..i+9 (persistent-dark
                                                        excursion projection)

Then, per window, mean activity/net-drift is computed separately for the
left third / center third / right third of the frame, across the ENTIRE
video (not a sample), to directly test a specific left-side-of-frame claim
quantitatively. A companion spatial-stability check reports, for the window
of peak left-third activity, whether the active pixel columns are the same
across widely separated windows (fixed-in-sensor-space => lens/sensor
artifact candidate) or drift over time (=> scene-content candidate).

Output: one HBP receipt (full time series + peak-window summaries) plus a
curated set of PNG heatmaps for the highest-activity windows and a uniform
temporal sample, so a human can look directly at the pixels.

Geometry/pixel measurement only. fire=0, physical_claim=0, authenticity=UNRESOLVED.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_track import gray_to_array, load_stream  # noqa: E402
from hbp import CLAIMS_GATE, hbp_row, sha256_file, write_hbp_hbi  # noqa: E402

SCHEMA = "ASOLARIA-VIDEO-LIGHT-DARK-FLASHLIGHT-V1"
WINDOW = 10
TOP_N_RENDER = 12
UNIFORM_SAMPLE = 10


def region_slices(width: int) -> dict[str, slice]:
    third = width // 3
    return {
        "left": slice(0, third),
        "center": slice(third, 2 * third),
        "right": slice(2 * third, width),
    }


def render_window_png(
    path: Path,
    raw_first: np.ndarray,
    raw_last: np.ndarray,
    net_signed: np.ndarray,
    accum_abs: np.ndarray,
    min_proj: np.ndarray,
    title: str,
) -> None:
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.2))
    fig.suptitle(title, fontsize=10)

    axes[0].imshow(raw_last, cmap="gray", vmin=0, vmax=255)
    axes[0].set_title("last raw frame in window", fontsize=9)

    vmax = max(1.0, float(np.abs(net_signed).max()))
    im1 = axes[1].imshow(net_signed, cmap="RdBu_r", vmin=-vmax, vmax=vmax)
    axes[1].set_title("net signed drift\n(red=lightened, blue=darkened)", fontsize=9)
    plt.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)

    im2 = axes[2].imshow(accum_abs, cmap="inferno")
    axes[2].set_title("accumulated |change|\n(any direction, 9 diffs)", fontsize=9)
    plt.colorbar(im2, ax=axes[2], fraction=0.046, pad=0.04)

    im3 = axes[3].imshow(min_proj, cmap="gray", vmin=0, vmax=255)
    axes[3].set_title("min-intensity projection\n(darkest value seen, 10 frames)", fontsize=9)

    for ax in axes:
        ax.set_xticks([])
        ax.set_yticks([])
        w = raw_last.shape[1]
        third = w // 3
        ax.axvline(third, color="cyan", linewidth=0.6, alpha=0.6)
        ax.axvline(2 * third, color="cyan", linewidth=0.6, alpha=0.6)

    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    stream = args.corpus / f"{args.source_id}.pgmstream"
    slices_hbp = args.corpus / f"{args.source_id}-SLICES.hbp"
    frames, meta = load_stream(stream, slices_hbp)
    num_frames = len(frames)
    height, width = frames[0].shape
    regions = region_slices(width)

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    frames_dir = output / "frames"
    frames_dir.mkdir(exist_ok=True)

    num_windows = num_frames - WINDOW + 1
    target_pts = [float(meta[i]["target_pts"]) for i in range(num_frames)]

    left_activity = np.zeros(num_windows)
    center_activity = np.zeros(num_windows)
    right_activity = np.zeros(num_windows)
    left_net = np.zeros(num_windows)
    center_net = np.zeros(num_windows)
    right_net = np.zeros(num_windows)
    window_start_pts = np.zeros(num_windows)

    left_col_argmax_history: list[int] = []

    for w in range(num_windows):
        window_frames = frames[w : w + WINDOW]
        diffs = [window_frames[k + 1] - window_frames[k] for k in range(WINDOW - 1)]
        accum_abs = np.sum([np.abs(d) for d in diffs], axis=0)
        net_signed = window_frames[-1] - window_frames[0]

        left_activity[w] = accum_abs[:, regions["left"]].mean()
        center_activity[w] = accum_abs[:, regions["center"]].mean()
        right_activity[w] = accum_abs[:, regions["right"]].mean()
        left_net[w] = net_signed[:, regions["left"]].mean()
        center_net[w] = net_signed[:, regions["center"]].mean()
        right_net[w] = net_signed[:, regions["right"]].mean()
        window_start_pts[w] = target_pts[w]

        left_col_profile = accum_abs[:, regions["left"]].mean(axis=0)
        left_col_argmax_history.append(int(np.argmax(left_col_profile)))

    # Spatial-stability check: is the peak-activity column WITHIN the left
    # third stable across time (sensor/lens-fixed) or does it drift (scene)?
    argmax_arr = np.array(left_col_argmax_history)
    argmax_std = float(argmax_arr.std())
    argmax_mean = float(argmax_arr.mean())

    top_indices = np.argsort(-left_activity)[:TOP_N_RENDER]
    uniform_indices = np.linspace(0, num_windows - 1, UNIFORM_SAMPLE, dtype=int)
    render_indices = sorted(set(top_indices.tolist()) | set(uniform_indices.tolist()))

    rows = [
        hbp_row(
            "FLASHLIGHTHDR",
            schema=SCHEMA,
            source_id=args.source_id,
            total_frames=num_frames,
            window=WINDOW,
            num_windows=num_windows,
            width=width,
            height=height,
            region_thirds="left,center,right",
            technique="net_signed_drift+accumulated_abs_diff+min_intensity_projection",
            **CLAIMS_GATE,
        )
    ]

    for w in range(num_windows):
        rows.append(
            hbp_row(
                "WINDOWSTAT",
                index=w,
                start_pts=f"{window_start_pts[w]:.3f}",
                left_activity=f"{left_activity[w]:.4f}",
                center_activity=f"{center_activity[w]:.4f}",
                right_activity=f"{right_activity[w]:.4f}",
                left_net=f"{left_net[w]:.4f}",
                center_net=f"{center_net[w]:.4f}",
                right_net=f"{right_net[w]:.4f}",
                left_peak_col_within_third=left_col_argmax_history[w],
            )
        )

    peak_w = int(np.argmax(left_activity))
    rows.append(
        hbp_row(
            "SPATIALSTABILITY",
            metric="left_third_peak_column_across_all_windows",
            mean_col=f"{argmax_mean:.2f}",
            std_col=f"{argmax_std:.2f}",
            third_width=width // 3,
            interpretation_if_low_std="candidate_fixed_sensor_or_lens_artifact",
            interpretation_if_high_std="candidate_moving_scene_content",
        )
    )
    rows.append(
        hbp_row(
            "PEAKWINDOW",
            index=peak_w,
            start_pts=f"{window_start_pts[peak_w]:.3f}",
            left_activity=f"{left_activity[peak_w]:.4f}",
            center_activity=f"{center_activity[peak_w]:.4f}",
            right_activity=f"{right_activity[peak_w]:.4f}",
            left_over_center_ratio=f"{(left_activity[peak_w] / max(center_activity[peak_w], 1e-9)):.4f}",
            left_over_right_ratio=f"{(left_activity[peak_w] / max(right_activity[peak_w], 1e-9)):.4f}",
        )
    )

    mean_left, mean_center, mean_right = left_activity.mean(), center_activity.mean(), right_activity.mean()
    rows.append(
        hbp_row(
            "WHOLEVIDEOSUMMARY",
            mean_left_activity=f"{mean_left:.4f}",
            mean_center_activity=f"{mean_center:.4f}",
            mean_right_activity=f"{mean_right:.4f}",
            left_elevated_vs_center=mean_left > mean_center,
            left_elevated_vs_right=mean_left > mean_right,
            left_over_center_ratio_whole_video=f"{(mean_left / max(mean_center, 1e-9)):.4f}",
            left_over_right_ratio_whole_video=f"{(mean_left / max(mean_right, 1e-9)):.4f}",
        )
    )

    png_shas = []
    for idx in render_indices:
        window_frames = frames[idx : idx + WINDOW]
        diffs = [window_frames[k + 1] - window_frames[k] for k in range(WINDOW - 1)]
        accum_abs = np.sum([np.abs(d) for d in diffs], axis=0)
        net_signed = window_frames[-1] - window_frames[0]
        min_proj = np.min(np.stack(window_frames), axis=0)
        is_top = idx in top_indices.tolist()
        png_path = frames_dir / f"window-{idx:04d}-{'TOP' if is_top else 'sample'}.png"
        render_window_png(
            png_path,
            window_frames[0],
            window_frames[-1],
            net_signed,
            accum_abs,
            min_proj,
            f"{args.source_id} window {idx} @ t={window_start_pts[idx]:.1f}s"
            f" (left_activity={left_activity[idx]:.2f}, rank={'TOP-' + str(list(top_indices).index(idx) + 1) if is_top else 'sample'})",
        )
        png_sha = sha256_file(png_path)
        png_shas.append(png_sha)
        rows.append(
            hbp_row(
                "RENDEREDWINDOW",
                index=idx,
                start_pts=f"{window_start_pts[idx]:.3f}",
                left_activity=f"{left_activity[idx]:.4f}",
                is_top_activity=is_top,
                png=png_path.relative_to(output).as_posix(),
                png_sha256=png_sha,
            )
        )

    # Whole-video timeline chart
    fig, ax = plt.subplots(figsize=(13, 4))
    ax.plot(window_start_pts, left_activity, label="left third", linewidth=1.3)
    ax.plot(window_start_pts, center_activity, label="center third", linewidth=1.3)
    ax.plot(window_start_pts, right_activity, label="right third", linewidth=1.3)
    ax.set_xlabel("window start time (s)")
    ax.set_ylabel("accumulated |change| (mean per pixel, 10-frame window)")
    ax.set_title(f"{args.source_id}: left/center/right activity across the ENTIRE video")
    ax.legend()
    ax.grid(alpha=0.25)
    timeline_path = output / "timeline-left-center-right.png"
    fig.tight_layout()
    fig.savefig(timeline_path, dpi=130)
    plt.close(fig)
    timeline_sha = sha256_file(timeline_path)
    rows.append(
        hbp_row(
            "TIMELINECHART",
            png=timeline_path.relative_to(output).as_posix(),
            png_sha256=timeline_sha,
        )
    )

    rows.append(
        hbp_row(
            "FLASHLIGHTFTR",
            source_id=args.source_id,
            windows_rendered=len(render_indices),
            top_n=TOP_N_RENDER,
            uniform_sample=UNIFORM_SAMPLE,
            **CLAIMS_GATE,
        )
    )

    hbp, hbi = write_hbp_hbi(output / f"FLASHLIGHT-{args.source_id}", rows, SCHEMA)
    print(
        hbp_row(
            "FLASHLIGHTPASS",
            source_id=args.source_id,
            windows=num_windows,
            rendered=len(render_indices),
            left_elevated_vs_center=mean_left > mean_center,
            left_elevated_vs_right=mean_left > mean_right,
            spatial_stability_std=f"{argmax_std:.2f}",
            hbp_sha256=sha256_file(hbp),
            hbi_sha256=sha256_file(hbi),
            **CLAIMS_GATE,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
