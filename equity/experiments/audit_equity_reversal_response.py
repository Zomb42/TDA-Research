"""Independent endpoint, projection, aggregation and causality audit.

Run after equity_reversal_response.py. Reconstructs sampled formations from
prices without using the event-study's projection/geometry/stability helpers.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.spatial.distance import pdist

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/equity_reversal_response"
DATA = ROOT / "market_data/datasets/equity_daily_30_2016_2026-10-27"


def audit():
    stock = pd.read_csv(OUT / "stock_events.csv.gz", parse_dates=["signal_date"])
    daily = pd.read_csv(OUT / "daily_event_statistics.csv", parse_dates=["signal_date", "entry", "exit"])
    dates = pd.read_csv(OUT / "formation_dates.csv", parse_dates=["signal_date", "training_start", "training_end", "entry", "last_exit"])
    summary = pd.read_csv(OUT / "response_summary.csv")
    bins = pd.read_csv(OUT / "binned_response.csv")
    stability = pd.read_csv(OUT / "stability_response.csv")
    panel = pd.read_csv(DATA / "returns_log.csv", index_col="date", parse_dates=True).iloc[1:]
    universe = pd.read_csv(DATA / "universe.csv")
    symbols = universe.loc[universe.role.eq("equity"), "symbol"].tolist()
    names = universe.set_index("symbol").loc[symbols].research_group
    manual = pd.factorize(names, sort=False)[0]
    bars = pd.read_csv(DATA / "bars_all.csv", parse_dates=["date"])
    opening = bars.pivot(index="date", columns="symbol", values="o").reindex(index=panel.index, columns=symbols)
    closing = bars.pivot(index="date", columns="symbol", values="c").reindex(index=panel.index, columns=symbols)
    def from_past(frame, t, length, need_labels=False):
        history = frame[symbols].iloc[t-length:t].to_numpy()
        market = frame.SPY.iloc[t-length:t].to_numpy()
        fit = np.linalg.lstsq(np.column_stack([np.ones(length), market]), history, rcond=None)[0]
        r = history - np.column_stack([np.ones(length), market]) @ fit
        std = r.std(axis=0, ddof=1)
        normalized = (r - r.mean(axis=0)) / std
        labels = cut_tree(linkage(pdist(normalized.T / np.sqrt(length-1)), method="average"), n_clusters=[6])[:, 0]
        values, vectors = np.linalg.eigh(np.corrcoef(r, rowvar=False))
        pcs = std[:, None] * vectors[:, np.argsort(values)[::-1][:5]]
        sigma = np.maximum(history.std(axis=0, ddof=1), .0001)
        return labels, fit[1], pcs, sigma
    sampled = dates.iloc[np.unique(np.linspace(0, len(dates)-1, 13).astype(int))]
    errors = {"holding": 0., "signal": 0., "future": 0., "future_residual": 0., "stability": 0.}
    for record in sampled.itertuples():
        t = panel.index.get_loc(record.signal_date)
        labels, beta, pcs, sigma = from_past(panel, t, 120)
        # A truncated dataset gives the same formation; future values aren't needed.
        truncated = from_past(panel.iloc[:t+1], t, 120)
        for a, b in zip((labels, beta, pcs, sigma), truncated):
            assert np.allclose(a, b)
        other = [from_past(panel, t, 100)[0], from_past(panel, t, 140)[0], from_past(panel, t-5, 120)[0]]
        score = np.zeros(30)
        for j in range(30):
            base = set(np.flatnonzero(labels == labels[j])) - {j}
            for alt in other:
                peers = set(np.flatnonzero(alt == alt[j])) - {j}
                score[j] += len(base & peers) / len(base | peers) / 3 if base | peers else 1/3
        matrices = {"Manual6": np.column_stack([np.eye(6)[manual], beta]),
                    "Average6": np.column_stack([np.eye(6)[labels], beta]),
                    "PCA5": np.column_stack([np.ones(30), beta, pcs])}
        for model, exposure in matrices.items():
            w = 1 / sigma ** 2
            # Normal equations give an independent numerical implementation.
            projector = np.eye(30) - exposure @ np.linalg.solve(exposure.T @ (w[:, None] * exposure), exposure.T * w)
            residual = projector @ panel[symbols].iloc[t].to_numpy()
            dollars = -w * residual / abs(w * residual).sum()
            for h in [1, 5, 20]:
                saved = stock.loc[stock.signal_date.eq(record.signal_date) & stock.model.eq(model) & stock.horizon.eq(h)].set_index("symbol").loc[symbols]
                future = closing.iloc[t+h].to_numpy() / opening.iloc[t+1].to_numpy() - 1
                for key, actual, expected in [("holding", saved.initial_dollars, dollars),
                                              ("signal", saved.signal_residual, residual),
                                              ("future", saved.future_simple_return, future),
                                              ("future_residual", saved.future_relative_return, projector @ future)]:
                    errors[key] = max(errors[key], float(np.max(abs(np.asarray(actual)-expected))))
                if model == "Average6":
                    errors["stability"] = max(errors["stability"], float(np.max(abs(saved.peer_stability.to_numpy()-score))))
                assert np.max(abs(exposure.T @ dollars)) < 1e-10
    assert max(errors.values()) < 1e-9
    assert dates.signal_date.is_unique
    assert (dates.training_end < dates.signal_date).all() and (dates.signal_date < dates.entry).all()
    assert ((dates.entry < pd.Timestamp("2024-01-01")) == (dates.last_exit < pd.Timestamp("2024-01-01"))).all()
    assert (daily.groupby(["model", "horizon"]).size() == len(dates)).all()
    # Verify every event's attribution identity and every headline pooled ratio.
    grouped = stock.assign(pnl=stock.initial_dollars * stock.future_simple_return).groupby(["signal_date", "model", "horizon"]).pnl.sum()
    saved = daily.set_index(["signal_date", "model", "horizon"]).gross_return
    assert np.allclose(grouped.sort_index(), saved.sort_index(), atol=1e-12)
    for row in summary.itertuples():
        g = stock.loc[stock.period.eq(row.period) & stock.model.eq(row.model) & stock.horizon.eq(row.horizon)]
        slope = np.sum(g.signal_z * g.future_relative_return / g.prior_total_sigma) / np.sum(g.signal_z ** 2)
        assert np.isclose(slope, row.response_slope)
        f = daily.loc[daily.period.eq(row.period) & daily.model.eq(row.model) & daily.horizon.eq(row.horizon)]
        assert np.isclose(f.gross_return.mean() * 1e4, row.mean_gross_event_bps)
    for row in bins.itertuples():
        g = stock.loc[stock.period.eq(row.period) & stock.model.eq(row.model) & stock.horizon.eq(row.horizon) & stock.active & stock.signal_bin.eq(row.bin)]
        assert len(g) == row.stock_events and np.isclose(g.future_relative_return.mean() * 1e4, row.future_relative_bps)
    for row in stability.loc[~stability.stability_group.eq("high_minus_lower")].itertuples():
        g = stock.loc[stock.period.eq(row.period) & stock.model.eq("Average6") & stock.horizon.eq(row.horizon) & stock.active]
        g = g.loc[g.peer_stability.ge(.75) if row.stability_group == "high" else g.peer_stability.lt(.75)]
        assert len(g) == row.stock_events
        assert np.isclose(np.sum(g.signal_z * g.future_relative_return / g.prior_total_sigma) / np.sum(g.signal_z**2), row.response_slope)
    implementation = json.loads((OUT / "implementation_audit.json").read_text())
    for path, expected in implementation["protected_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected
    report = {"checks": {"thirteen_formation_dates_reconstructed_independently": True,
                          "truncating_future_does_not_change_formation": True,
                          "independent_peer_set_stability_reproduces": True,
                          "all_horizon_endpoints_reconstructed_at_sampled_dates": True,
                          "all_event_gross_contributions_reconcile": True,
                          "all_summary_slopes_and_gross_means_reproduce": True,
                          "all_bin_means_and_counts_reproduce": True,
                          "all_stability_subset_slopes_and_counts_reproduce": True,
                          "split_chronology_common_samples_and_protected_hashes_pass": True},
              "sampled_formation_dates": [str(d.date()) for d in sampled.signal_date],
              "max_absolute_independent_reconstruction_errors": errors,
              "all_model_horizon_slope_intervals_include_zero": bool(((summary.slope_low < 0) & (summary.slope_high > 0)).all()),
              "all_model_horizon_gross_intervals_include_zero": bool(((summary.gross_low < 0) & (summary.gross_high > 0)).all()),
              "all_high_minus_lower_stability_intervals_include_zero": bool(((stability.loc[stability.stability_group.eq("high_minus_lower"), "low"] < 0) & (stability.loc[stability.stability_group.eq("high_minus_lower"), "high"] > 0)).all())}
    (OUT / "independent_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    audit()
