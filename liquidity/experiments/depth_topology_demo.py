"""Synthetic depth rasters: matched summaries, different cubical topology.

Run with an environment containing numpy, scipy, and matplotlib:
    python depth_topology_demo.py

This educational example computes Betti numbers at depth thresholds. It is
not a general persistence-pairing library and implements no merge-tree
algorithm. All arrays are synthetic; no predictive financial claim is made.

Each included pixel is a closed square. Diagonal contacts therefore connect
components (8-neighbor connectivity). In a finite planar union of squares,
chi = V - E + F = beta_0 - beta_1; beta_2 is zero.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import ndimage


OUTPUT_DIR = Path(__file__).resolve().parent


def closed_cell_betti(mask: np.ndarray) -> dict[str, int]:
    """Exact counts for a finite two-dimensional union of closed unit squares."""
    if mask.ndim != 2:
        raise ValueError("This routine supports only two-dimensional rasters.")
    pixels = np.argwhere(mask)
    vertices: set[tuple[int, int]] = set()
    edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for raw_i, raw_j in pixels:
        i, j = int(raw_i), int(raw_j)
        vertices.update(((i, j), (i + 1, j), (i, j + 1), (i + 1, j + 1)))
        edges.update(
            (
                ((i, j), (i + 1, j)),
                ((i, j + 1), (i + 1, j + 1)),
                ((i, j), (i, j + 1)),
                ((i + 1, j), (i + 1, j + 1)),
            )
        )
    _, beta_0 = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))
    chi = len(vertices) - len(edges) + len(pixels)
    beta_1 = int(beta_0) - chi
    assert beta_1 >= 0
    return {
        "beta_0": int(beta_0),
        "beta_1": beta_1,
        "euler_characteristic": chi,
        "vertices": len(vertices),
        "edges": len(edges),
        "squares": len(pixels),
    }


def threshold_curve(depth: np.ndarray) -> list[dict]:
    """Descending superlevels, including empty and full-domain states."""
    values = sorted(map(float, np.unique(depth)), reverse=True)
    thresholds = [values[0] + 1.0, *values, values[-1] - 1.0]
    return [
        {"depth_threshold": q, **closed_cell_betti(depth >= q)}
        for q in thresholds
    ]


def make_fields() -> dict[str, np.ndarray]:
    stable = np.ones((12, 9))
    stable[[2, 9], :] = 8
    fragmented = np.ones((12, 9))
    for j in range(9):
        fragmented[[2, 9] if j % 2 == 0 else [5, 6], j] = 8

    ring = np.ones((7, 9))
    ring[1, 1:8] = 8
    ring[5, 1:8] = 8
    ring[1:6, 1] = 8
    ring[1:6, 7] = 8
    open_gap = ring.copy()
    open_gap[1, 4] = 1
    open_gap[6, 4] = 8
    return {
        "stable_bands": stable,
        "fragmented_patches": fragmented,
        "enclosed_pocket": ring,
        "open_gap": open_gap,
    }


def matched_summaries(a: np.ndarray, b: np.ndarray) -> dict[str, bool]:
    price = np.arange(a.shape[0])[:, None]
    return {
        "same_current_snapshot": bool(np.array_equal(a[:, -1], b[:, -1])),
        "same_total_depth_at_every_time": bool(np.array_equal(a.sum(0), b.sum(0))),
        "same_whole_window_depth_histogram": bool(
            np.array_equal(np.sort(a.ravel()), np.sort(b.ravel()))
        ),
        "same_first_price_moment_at_every_time": bool(
            np.array_equal((price * a).sum(0), (price * b).sum(0))
        ),
    }


def main() -> None:
    fields = make_fields()
    stable_match = matched_summaries(fields["stable_bands"], fields["fragmented_patches"])
    ring_match = matched_summaries(fields["enclosed_pocket"], fields["open_gap"])
    assert all(stable_match.values())
    assert all(value for key, value in ring_match.items() if "first_price" not in key)
    expected = {
        "stable_bands": (2, 0),
        "fragmented_patches": (14, 0),
        "enclosed_pocket": (1, 1),
        "open_gap": (1, 0),
    }
    details = {}
    for name, depth in fields.items():
        counts = closed_cell_betti(depth >= 8)
        assert (counts["beta_0"], counts["beta_1"]) == expected[name]
        curve = threshold_curve(depth)
        # Reversing time preserves this cubical filtration's Betti curves.
        assert curve == threshold_curve(depth[:, ::-1])
        assert closed_cell_betti(depth >= 1)["beta_0"] == 1
        assert closed_cell_betti(depth >= 1)["beta_1"] == 0
        details[name] = {
            "array_price_by_time": depth.astype(int).tolist(),
            "superlevel_threshold_curve": curve,
            "time_reversal_has_identical_curve": True,
        }

    payload = {
        "synthetic_only": True,
        "construction": "Closed-square cubical superlevel sets of displayed depth D; equivalent to sublevel sets of -D.",
        "axes": "Rows are abstract price bins; columns are successive past observation times.",
        "adjacency": "Closed squares share corners: 8-neighbor components.",
        "limitations": [
            "No market data or prediction experiment.",
            "No general persistence pairing or merge-tree algorithm is implemented.",
            "Betti curves do not specify merger ancestry.",
            "Depth-threshold persistence is not duration in seconds.",
            "Ordinary turnover, duration, and gap statistics can also distinguish these examples.",
            "Only enclosure is detected by H1; boundary-connected gaps need not produce holes.",
        ],
        "matched_summaries": {"stable_vs_fragmented": stable_match, "enclosed_vs_open": ring_match},
        "fields": details,
    }
    (OUTPUT_DIR / "depth_topology_demo.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
    fig = plt.figure(figsize=(15, 9), facecolor="#f8fafc")
    grid = fig.add_gridspec(
        2, 3, width_ratios=(1, 1, 1.02), left=0.055, right=0.965,
        bottom=0.20, top=0.85, hspace=0.43, wspace=0.25
    )
    labels = {
        "stable_bands": "Stable bands",
        "fragmented_patches": "Fragmented patches",
        "enclosed_pocket": "Enclosed pocket",
        "open_gap": "Open gap",
    }
    for index, (name, depth) in enumerate(fields.items()):
        row, col = divmod(index, 2)
        ax = fig.add_subplot(grid[row, col])
        image = ax.imshow(
            depth, origin="lower", cmap="Blues", vmin=1, vmax=8,
            aspect="auto", interpolation="nearest"
        )
        ax.set_title(labels[name], loc="left", weight="bold", pad=12, color="#142b43")
        ax.set_xlabel("Past observations → current")
        ax.set_ylabel("Price bin")
        ax.set_xticks([0, 4, 8], ["0", "4", "8"])
        ax.set_yticks([0, depth.shape[0] - 1])
        ax.set_xticks(np.arange(-0.5, depth.shape[1], 1), minor=True)
        ax.set_yticks(np.arange(-0.5, depth.shape[0], 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=0.7, alpha=0.85)
        ax.tick_params(which="minor", bottom=False, left=False)
        b0, b1 = expected[name]
        ax.text(
            0.02, 0.015, f"At threshold 8:  H₀ = {b0},  H₁ = {b1}",
            transform=ax.transAxes, va="bottom", ha="left", fontsize=10,
            bbox={"facecolor": "white", "alpha": 0.92, "edgecolor": "none", "pad": 4}
        )
        for spine in ax.spines.values():
            spine.set_edgecolor("#a5b4c3")

    explanation = [
        (
            "Same summaries; different connectivity",
            "Matched at every observation:\n"
            "• Total displayed depth\n"
            "• First price moment\n\n"
            "Also matched:\n"
            "• Whole-window depth histogram\n"
            "• Current book snapshot\n\n"
            "For 1 < threshold ≤ 8, there are\n"
            "2 versus 14 connected regions.\n"
            "At threshold 1, both become one."
        ),
        (
            "An enclosed hole differs from an open gap",
            "Matched:\n"
            "• Total depth at every observation\n"
            "• Whole-window depth histogram\n"
            "• Current book snapshot\n\n"
            "Moving one high-depth cell opens\n"
            "the ring. H₁ changes from 1 to 0.\n\n"
            "An important gap need not form a\n"
            "topological hole. Boundary and\n"
            "source location matter."
        ),
    ]
    for row, (title, body) in enumerate(explanation):
        ax = fig.add_subplot(grid[row, 2])
        ax.axis("off")
        ax.text(0, 1.02, title, va="top", weight="bold", fontsize=11, color="#142b43")
        ax.text(0, 0.885, body, va="top", fontsize=10.7, linespacing=1.3, color="#34465b")

    fig.suptitle(
        "Synthetic depth fields: what cubical topology sees",
        x=0.055, y=0.967, ha="left", fontsize=21, weight="bold", color="#142b43"
    )
    fig.text(
        0.055, 0.908,
        "Include cells whose depth is at least the threshold. Dark cells have depth 8; light cells have depth 1.",
        ha="left", fontsize=11.5, color="#34465b"
    )
    color_ax = fig.add_axes((0.06, 0.091, 0.23, 0.016))
    colorbar = fig.colorbar(image, cax=color_ax, orientation="horizontal", ticks=[1, 8])
    colorbar.set_label("Synthetic displayed quantity", fontsize=10, labelpad=2)
    fig.text(
        0.34, 0.092,
        "Closed cells connect at corners. Time reversal leaves these curves unchanged.\n"
        "Threshold persistence measures depth contrast, not seconds or order identity.",
        va="center", fontsize=10, color="#34465b", linespacing=1.5
    )
    fig.text(
        0.055, 0.016,
        "Educational fixture only • Ordinary turnover and gap statistics also distinguish these fields • No forecasting claim or merge-tree algorithm",
        fontsize=9.3, color="#596d83"
    )
    fig.savefig(OUTPUT_DIR / "depth_topology_demo.png", dpi=170, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(json.dumps({
        "outputs": ["depth_topology_demo.png", "depth_topology_demo.json"],
        "threshold_8_betti": expected,
        "all_assertions_passed": True,
    }))


if __name__ == "__main__":
    main()
