"""One shared look for every figure, and where each study saves its output."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS = Path(__file__).resolve().parents[1] / "results"

# Fixed colour order. A series keeps its colour in every figure of a study.
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
SERIES = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED]
GRAY = "#898781"        # context that is not a series (noise, reference lines)
INK, INK_SOFT, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK_SOFT, "axes.titlecolor": INK,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.labelsize": 9.5, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "xtick.color": GRAY, "ytick.color": GRAY, "xtick.labelcolor": INK_SOFT,
    "ytick.labelcolor": INK_SOFT, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "lines.linewidth": 2, "lines.markersize": 6, "font.size": 10,
    "legend.frameon": False, "legend.fontsize": 9, "figure.dpi": 110, "savefig.dpi": 160,
})


def folder(study):
    out = RESULTS / study
    out.mkdir(parents=True, exist_ok=True)
    return out


def save(fig, study, name):
    path = folder(study) / name
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path

