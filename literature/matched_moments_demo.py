"""Synthetic illustration: equal mean/covariance do not fix point-cloud shape.

This is not financial evidence or a forecasting experiment. Run in conda tda.
"""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ripser import ripser


def whiten(points):
    centered = points - points.mean(axis=0)
    values, vectors = np.linalg.eigh(np.cov(centered, rowvar=False))
    return centered @ vectors @ np.diag(1 / np.sqrt(values)) @ vectors.T


def main():
    rng = np.random.default_rng(19)
    n = 240
    angle = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = np.c_[np.cos(angle), np.sin(angle)] + rng.normal(0, .015, (n, 2))
    disk_angle = rng.uniform(0, 2 * np.pi, n)
    radius = np.sqrt(rng.uniform(0, 1, n))
    disk = np.c_[radius * np.cos(disk_angle), radius * np.sin(disk_angle)]
    clouds = {"Ring": whiten(ring), "Filled disk": whiten(disk)}
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), layout="constrained")
    metrics = {}
    for col, (name, cloud) in enumerate(clouds.items()):
        assert np.allclose(cloud.mean(axis=0), 0, atol=1e-12)
        assert np.allclose(np.cov(cloud, rowvar=False), np.eye(2), atol=1e-12)
        diagram = ripser(cloud, maxdim=1)["dgms"][1]
        axes[0, col].scatter(*cloud.T, s=10, alpha=.8, color=["#265a8d", "#c06933"][col])
        axes[0, col].set(title=name + ": mean = 0, covariance = I",
                         xlim=(-2.25, 2.25), ylim=(-2.25, 2.25), xlabel="Coordinate 1", ylabel="Coordinate 2")
        axes[0, col].set_aspect("equal")
        axes[1, col].scatter(diagram[:, 0], diagram[:, 1], s=22, color=["#265a8d", "#c06933"][col])
        axes[1, col].plot([0, 2.8], [0, 2.8], ls="--", color="#888888", lw=1)
        longest = float(np.max(diagram[:, 1] - diagram[:, 0]))
        axes[1, col].set(title=f"H1 persistence: longest interval = {longest:.2f}",
                         xlabel="Birth (Euclidean distance)", ylabel="Death (Euclidean distance)",
                         xlim=(0, 2.8), ylim=(0, 2.8))
        axes[1, col].set_aspect("equal")
        metrics[name] = {"n": n, "mean": cloud.mean(axis=0).tolist(),
                         "covariance": np.cov(cloud, rowvar=False).tolist(),
                         "longest_H1_interval": longest}
    fig.suptitle("Matching mean and covariance leaves different geometry", fontsize=16)
    fig.supxlabel("Synthetic demonstration only. Other nonlinear statistics can also distinguish these clouds.", fontsize=10)
    out = Path(__file__).parent
    fig.savefig(out / "matched_moments_demo.png", dpi=160)
    (out / "matched_moments_demo.json").write_text(json.dumps(metrics, indent=2) + "\n")
    plt.close(fig)
    print(json.dumps({name: data["longest_H1_interval"] for name, data in metrics.items()}))


if __name__ == "__main__":
    main()
