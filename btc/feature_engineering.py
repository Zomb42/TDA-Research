"""Descriptive BTC delay geometry, fixed conventional baselines, and controls.

No labels, forecasting model, or trading-performance claims. Uses past windows
only. Run in conda tda; defaults are a declared learning specification.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/tda-btc-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from ripser import ripser

ROOT = Path(__file__).resolve().parents[1]
SPEC = dict(window_returns=288, stride_bars=288, embedding_dimension=3,
            lag_bars=3, bar_minutes=5, max_points=128, distance="Euclidean",
            filtration="Vietoris-Rips", max_homology_dimension=1,
            normalization="center and population-standardize the return window before embedding",
            point_selection="128 deterministic evenly spaced delay vectors, including endpoints",
            zero_variance="all-zero normalized signal; no division by zero",
            scope="descriptive; no future labels or model fitting")


def embedding(x, lag=3, dimension=3, max_points=128):
    n = len(x) - lag * (dimension - 1)
    if n < 3:
        raise ValueError("Not enough observations")
    # Coordinate j is x[t + j*lag]. All coordinates lie within the past window.
    cloud = np.column_stack([x[j * lag:j * lag + n] for j in range(dimension)])
    # Keep reversal symmetry in the subsample, including even and odd n.
    indices = np.unique(np.rint(np.linspace(0, n - 1, min(n, max_points))).astype(int))
    return cloud[indices]


def diagram_summary(cloud):
    diagrams = ripser(cloud, maxdim=1)["dgms"]
    result = {}
    for dim, diagram in enumerate(diagrams):
        finite = diagram[np.isfinite(diagram[:, 1])]
        life = finite[:, 1] - finite[:, 0]
        life = life[life > 0]
        result[f"h{dim}_finite_intervals"] = len(life)
        result[f"h{dim}_max_lifetime"] = float(life.max()) if len(life) else 0.0
        result[f"h{dim}_total_lifetime"] = float(life.sum())
        result[f"h{dim}_essential_intervals"] = int((~np.isfinite(diagram[:, 1])).sum())
    return result, diagrams


def conventional(x):
    centered = x - x.mean()
    power = np.abs(np.fft.rfft(centered)) ** 2
    power[0] = 0
    total = power.sum()
    probabilities = power[power > 0] / total if total else np.array([])
    denom = np.dot(centered, centered)
    result = dict(mean_return_bps=float(x.mean()), realized_vol_bps=float(np.sqrt(np.sum(x*x))),
                  return_std_bps=float(x.std()), max_abs_return_bps=float(np.abs(x).max()),
                  largest_squared_return_share=float(np.max(x*x) / np.sum(x*x)) if np.sum(x*x) else 0.0,
                  dominant_spectral_power_share=float(power.max() / total) if total else 0.0,
                  spectral_entropy=float(-(probabilities * np.log(probabilities)).sum()) if total else 0.0)
    for lag in (1, 3, 12):
        # Fixed-denominator sample ACF, not Pearson correlation on shifted subsets.
        result[f"acf_{lag}"] = float(np.dot(centered[:-lag], centered[lag:]) / denom) if denom else 0.0
    return result


def features(x):
    x = np.asarray(x, dtype=float)
    if not np.isfinite(x).all():
        raise ValueError("Nonfinite return input")
    result = conventional(x)
    scale = x.std()
    normalized = (x - x.mean()) / scale if scale > 1e-12 else np.zeros_like(x)
    diagrams = {}
    for name, signal in [("raw_bps", x), ("shape", normalized)]:
        cloud = embedding(signal)
        summary, diagrams[name] = diagram_summary(cloud)
        result.update({f"{name}_{key}": value for key, value in summary.items()})
    return result, diagrams


def controls(out):
    rng = np.random.default_rng(20261029)
    t = np.arange(288)
    sine = np.sin(2 * np.pi * t / 24)
    signals = {"oscillation": sine, "oscillation_x3": 3*sine,
               "oscillation_shuffled": rng.permutation(sine), "oscillation_reversed": sine[::-1],
               "gaussian": rng.normal(size=288), "single_jump": np.eye(1, 288, 144).ravel(),
               "variance_burst": rng.normal(size=288) * np.where((t >= 96) & (t < 144), 4, 0.5),
               "constant": np.zeros(288)}
    # Equal population standard deviation for confound comparisons; retain x3.
    for key in signals:
        if key not in ("oscillation_x3", "constant"):
            s = signals[key]
            signals[key] = (s - s.mean()) / s.std()
    signals["oscillation_x3"] = 3 * signals["oscillation"]
    rows = []
    for name, signal in signals.items():
        row, _ = features(signal)
        rows.append(dict(control=name, **row))
    table = pd.DataFrame(rows).set_index("control")
    table.to_csv(out / "controls.csv")
    original = table.loc["oscillation"]
    tripled = table.loc["oscillation_x3"]
    reversed_ = table.loc["oscillation_reversed"]
    scale_error = abs(tripled.raw_bps_h1_max_lifetime - 3*original.raw_bps_h1_max_lifetime)
    shape_error = abs(tripled.shape_h1_max_lifetime - original.shape_h1_max_lifetime)
    reverse_error = abs(reversed_.shape_h1_max_lifetime - original.shape_h1_max_lifetime)
    assert scale_error < 1e-5 and shape_error < 1e-5 and reverse_error < 1e-5
    assert table.loc["constant", "shape_h1_max_lifetime"] == 0
    fig, axes = plt.subplots(3, 3, figsize=(12, 9))
    for ax, (name, signal) in zip(axes.flat, signals.items()):
        cloud = embedding(signal / signal.std() if signal.std() else signal)
        ax.scatter(cloud[:, 0], cloud[:, 1], c=np.arange(len(cloud)), s=8, cmap="viridis")
        ax.set_title(f"{name}\nH1 max={table.loc[name, 'shape_h1_max_lifetime']:.3f}", fontsize=10)
        ax.set_xlabel("return at t (window std units)")
        ax.set_ylabel("return at t+15 min")
    axes.flat[-1].axis("off")
    fig.suptitle("2D projection of each 3D delay cloud; color follows sampled time", fontsize=13)
    fig.tight_layout()
    fig.savefig(out / "controls.png", dpi=150)
    plt.close(fig)
    return dict(raw_scale_x3_error=scale_error, normalized_scale_error=shape_error,
                reversal_error=reverse_error, constant_loop_lifetime=0,
                interpretation="Shape responds to temporal arrangement but cannot generally identify time direction.")


def build_table(bars, window=288, stride=288):
    bars = bars.sort_values("open_time").reset_index(drop=True)
    # First diff is undefined; do not cross gaps or manufacture a return.
    returns = np.diff(np.log(bars.close.to_numpy(dtype=float))) * 10000
    rows = []
    for end in range(window, len(returns) + 1, stride):
        start = end - window
        source = bars.iloc[start:end + 1]
        if not (np.diff(source.open_time.to_numpy()) == 300000).all():
            continue
        row, _ = features(returns[start:end])
        rows.append(dict(window_start_utc=str(source.available_at_utc.iloc[0]),
                         feature_time_utc=str(source.available_at_utc.iloc[-1]),
                         **row, quote_volume_usdt=float(source.quote_volume.iloc[1:].sum()),
                         taker_buy_volume_share=float(source.taker_buy_volume.iloc[1:].sum() / source.volume.iloc[1:].sum())
                         if source.volume.iloc[1:].sum() else 0.0))
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bars", type=Path, default=ROOT / "market_data/datasets/btc_binance_2024_2026-10-27/bars_5m.parquet")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "experiments/initial_features")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "specification.json").write_text(json.dumps(SPEC, indent=2) + "\n")
    control_checks = controls(args.out)
    bars = pd.read_parquet(args.bars)
    table = build_table(bars)
    table.to_csv(args.out / "features_daily.csv", index=False)
    # Verify one earlier row is exactly the same when later prices are absent.
    earlier = build_table(bars.iloc[:578])
    np.testing.assert_allclose(earlier.select_dtypes("number"), table.iloc[:len(earlier)].select_dtypes("number"), rtol=0, atol=0)
    numeric = table.select_dtypes("number")
    assert np.isfinite(numeric.to_numpy()).all()
    correlations = numeric.corr(method="spearman")
    correlations.to_csv(args.out / "spearman_descriptive.csv")
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    dates = pd.to_datetime(table.feature_time_utc)
    axes[0].plot(bars.available_at_utc, bars.close, linewidth=0.6)
    axes[0].set_ylabel("BTCUSDT perp close")
    axes[1].plot(dates, table.raw_bps_h1_max_lifetime, label="longest H1 (bps distance)", linewidth=0.8)
    axes[1].plot(dates, table.return_std_bps, label="return std (bps)", linewidth=0.8)
    axes[1].legend()
    axes[1].set_ylabel("Raw scale")
    axes[2].plot(dates, table.shape_h1_max_lifetime, linewidth=0.8)
    axes[2].set_ylabel("Longest H1\n(window std units)")
    axes[2].set_xlabel("Window completion, UTC; daily nonoverlapping return windows")
    fig.suptitle("Descriptive BTC features: raw scale and standardized delay geometry")
    fig.tight_layout()
    fig.savefig(args.out / "real_features.png", dpi=150)
    plt.close(fig)
    # Equal-time examples selected in advance, not ranked by the feature.
    examples = {}
    for k in [0, len(table)//2, len(table)-1]:
        end = 288 + k*288
        x = np.diff(np.log(bars.close.iloc[end-288:end+1].to_numpy()))*10000
        _, dgms = features(x)
        examples[str(table.feature_time_utc.iloc[k])] = {
            name: [[pair.tolist() for pair in d if np.isfinite(pair).all()] for d in diagrams]
            for name, diagrams in dgms.items()}
    (args.out / "example_diagrams.json").write_text(json.dumps(examples, indent=2) + "\n")
    report = dict(feature_rows=len(table), first_feature_time=table.feature_time_utc.iloc[0],
                  last_feature_time=table.feature_time_utc.iloc[-1], controls=control_checks,
                  prefix_invariance_passed=True, all_numeric_values_finite=True,
                  input_sha256=hashlib.sha256(args.bars.read_bytes()).hexdigest(),
                  raw_h1_vs_std_spearman=float(correlations.loc["raw_bps_h1_max_lifetime", "return_std_bps"]),
                  shape_h1_vs_std_spearman=float(correlations.loc["shape_h1_max_lifetime", "return_std_bps"]),
                  scope="Exploratory feature interpretation only. All dates used here are viewed development data; no untouched holdout is claimed.")
    (args.out / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
