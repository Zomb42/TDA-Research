"""Point clouds of book states: is there shape beyond a blob, and does window shape forecast?

Design (fixed before the rolling results were seen, November 18, 2026):
Each second is one point: log(1 + depth in $1k) in five distance bands per side (0-2, 2-5,
5-10, 10-20, 20-25 bp), standardised by November 11 means and standard deviations (10 numbers).
A first look with all fifty 1-bp bins was indistinguishable from a Gaussian blob, so this coarse
version is used throughout.

Part 1, global shape. 2,000 seconds at least 30 s apart, from Nov 11 and from Nov 12-17.
Persistent homology (Vietoris-Rips, ripser): H0 = clumps, H1 = loops. Null: Gaussian points with
the same mean and covariance (three seeds). Plain competitor for clumps: k-means silhouette.

Part 2, rolling windows. Non-overlapping 5-minute windows (300 one-second points each).
TDA features: H0 total persistence, H1 total persistence, H1 largest persistence.
Plain twins: total variance of the window's points, path length (sum of step distances),
diameter (largest distance between two points), and mean total depth.
Targets for the next 5 minutes: log realised variance of Kalshi's midpoint (100 ms steps), and
the volume-weighted 1 s markout of fills at the best quote (the market maker's result).
Baseline: log realised variance this window, the previous hour, and Binance futures this window;
log mean spread; log trade count; hour of day (sine and cosine).
Fit Nov 12-14, score Nov 15-17 with least squares on standardised features; intervals resample
whole hours. Decisive row: baseline + twins + TDA against baseline + twins.
"""
import numpy as np
import pandas as pd
from ripser import ripser
from scipy.spatial.distance import pdist
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from l02_describe import GRID_CACHE
from l13_who_wins import OUT, S_NS, boot_ci, load, trades_with_markouts

EDGES = [0, 2, 5, 10, 20, 25]
WIN = 300
RNG = np.random.default_rng(20261118)


def band_states():
    z = np.load(GRID_CACHE)
    g, valid = z["grid"], z["valid"]
    B = np.concatenate([np.log1p(g[:, s, a:b].sum(1, keepdims=True) / 1000)
                        for s in (0, 1) for a, b in zip(EDGES[:-1], EDGES[1:])], axis=1)
    cal = np.flatnonzero(valid[:86400])
    Z = (B - B[cal].mean(0)) / B[cal].std(0)
    return Z, valid, g


def diagram_summary(P):
    dg = ripser(P, maxdim=1)["dgms"]
    h0 = dg[0][:-1, 1]
    h1 = dg[1][:, 1] - dg[1][:, 0]
    return h0, h1


def global_shape(Z, valid):
    rows = []
    for label, lo, hi in [("Nov 11", 0, 86400), ("Nov 12-17", 86400, len(Z))]:
        cand = np.arange(lo, hi, 30)
        cand = cand[valid[cand] & (cand % 3600 >= 10)]
        P = Z[RNG.choice(cand, 2000, replace=False)]
        clouds = [("book states", P)] + [(f"Gaussian null {i}", np.random.default_rng(i).multivariate_normal(
            P.mean(0), np.cov(P.T), len(P))) for i in range(3)]
        for name, Q in clouds:
            h0, h1 = diagram_summary(Q)
            rows.append(dict(sample=label, cloud=name, h0_top=np.sort(h0)[-1], h0_5th=np.sort(h0)[-5],
                             h1_count=len(h1), h1_max=h1.max(), h1_total=h1.sum(),
                             silhouette_k2=silhouette_score(Q, KMeans(2, n_init=5, random_state=0).fit_predict(Q))))
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "book_cloud_global.csv", index=False)
    return out


def holes(Z, valid, g):
    """Seconds where at least one band is more than 4 standard deviations below normal (Nov 12-17)."""
    import json
    z = np.load(GRID_CACHE)
    mid2 = z["mid2"].astype(float)
    lm = np.log(np.where(mid2 > 0, mid2 / 2, np.nan)) * 1e4
    s = np.arange(len(Z))
    c = s[valid & (s >= 86400) & (s % 3600 >= 10)]
    low = Z[c].min(axis=1) < -4
    ev = c[low]
    first = np.r_[True, np.diff(ev) > 1]
    starts = ev[first]
    runs = np.diff(np.r_[np.flatnonzero(first), len(ev)])
    names = [f"{x} {a}-{b} bp" for x in ("bid", "ask") for a, b in zip(EDGES[:-1], EDGES[1:])]
    move60 = np.abs(np.r_[lm[60:] - lm[:-60], np.full(60, np.nan)])
    out = dict(share_of_seconds=float(low.mean()), episodes=int(len(starts)), median_episode_s=float(np.median(runs)),
               emptiest_band_counts=pd.Series(np.array(names)[Z[ev].argmin(axis=1)]).value_counts().head(4).to_dict(),
               median_abs_move_next_60s_after_hole_bp=float(np.nanmedian(move60[starts])),
               median_abs_move_next_60s_all_bp=float(np.nanmedian(move60[c])))
    (OUT / "book_cloud_holes.json").write_text(json.dumps(out, indent=2) + "\n")
    return out


def window_features(Z, valid, g, d, t):
    n_win = len(Z) // WIN
    lm, fut = d["lmid"], d["fut"]
    d2k = np.r_[0, np.diff(lm)] ** 2
    d2b = np.r_[0, np.diff(fut)] ** 2
    spread = (d["ask"] - d["bid"]) / d["mid"] * 1e4
    touch = np.where(t.side > 0, t.price_tick == t.ask_tick, t.price_tick == t.bid_tick) & t.mo_1.notna().to_numpy()
    tt = t[touch]
    win_of_trade = ((tt.received_ns.to_numpy() - S_NS) // 10**9 // WIN).astype(int)
    mo_num = np.bincount(win_of_trade, tt.mo_1 * tt.weight, minlength=n_win)[:n_win]
    mo_den = np.bincount(win_of_trade, tt.weight, minlength=n_win)[:n_win]
    trades = np.bincount(((t.received_ns.to_numpy() - S_NS) // 10**9 // WIN).astype(int), minlength=n_win)[:n_win]
    depth_total = np.log1p(g.sum(axis=(1, 2)) / 1000)
    rows = []
    for w in range(n_win):
        s = slice(w * WIN, (w + 1) * WIN)
        q = slice(w * WIN * 10, (w + 1) * WIN * 10)
        ok = valid[s] & d["use"][q][9::10]
        if ok.mean() < 0.95:
            rows.append(dict(window=w, good=False))
            continue
        P = Z[s][ok]
        h0, h1 = diagram_summary(P)
        rows.append(dict(window=w, good=True, h0_total=h0.sum(), h1_total=h1.sum(), h1_max=h1.max() if len(h1) else 0,
                         variance=np.trace(np.cov(P.T)), path=np.linalg.norm(np.diff(P, axis=0), axis=1).sum(),
                         diameter=pdist(P).max(), depth=depth_total[s][ok].mean(),
                         rv=np.log(0.01 + np.nansum(d2k[q])), rv_binance=np.log(0.01 + np.nansum(d2b[q])),
                         spread=np.log(np.nanmean(spread[q])), trades=np.log1p(trades[w]),
                         markout=mo_num[w] / mo_den[w] if mo_den[w] > 0 else np.nan, volume=mo_den[w]))
    return pd.DataFrame(rows)


def evaluate(f):
    f = f.copy()
    f["rv_prev_hour"] = f.rv.rolling(12, min_periods=12).mean().shift(1)
    hour = (f.window * WIN // 3600) % 24
    f["sin"], f["cos"] = np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24)
    f["next_rv"], f["next_markout"] = f.rv.shift(-1), f.markout.shift(-1)
    f["next_good"] = f.good.shift(-1, fill_value=False)
    f["day"] = 11 + f.window * WIN // 86400
    base = ["rv", "rv_prev_hour", "rv_binance", "spread", "trades", "sin", "cos"]
    twins = ["variance", "path", "diameter", "depth"]
    tda = ["h0_total", "h1_total", "h1_max"]
    rows, overlap = [], []
    ok_all = f.good & f.next_good & f[base + twins + tda].notna().all(axis=1) & (f.day >= 12)
    for k in tda:
        m = ok_all
        X = np.c_[f.loc[m, twins].to_numpy(), np.ones(m.sum())]
        r = f.loc[m, k] - X @ np.linalg.lstsq(X, f.loc[m, k], rcond=None)[0]
        overlap.append(dict(tda_feature=k, share_explained_by_twins=1 - r.var() / f.loc[m, k].var()))
    for target in ("next_rv", "next_markout"):
        m = ok_all & f[target].notna()
        fit, test = m & (f.day <= 14), m & (f.day >= 15)
        preds = {}
        for name, cols in [("baseline", base), ("baseline + depth only", base + ["depth"]), ("baseline + twins", base + twins), ("baseline + TDA", base + tda),
                           ("baseline + twins + TDA", base + twins + tda)]:
            X = f[cols].to_numpy()
            mu, sd = X[fit].mean(0), X[fit].std(0)
            Zx = np.c_[(X - mu) / sd, np.ones(len(X))]
            w = f.volume.to_numpy() if target == "next_markout" else np.ones(len(f))
            sw = np.sqrt(w[fit])
            beta = np.linalg.lstsq(Zx[fit] * sw[:, None], f[target].to_numpy()[fit] * sw, rcond=None)[0]
            preds[name] = Zx[test] @ beta
            y = f[target].to_numpy()[test]
            rows.append(dict(target=target, model=name, windows_fit=int(fit.sum()), windows_test=int(test.sum()),
                             r2_out_of_sample=1 - np.mean((y - preds[name]) ** 2) / np.var(y)))
        y = f[target].to_numpy()[test]
        hours = (f.window.to_numpy()[test] * WIN) // 3600
        for a, b in [("baseline + twins + TDA", "baseline + twins"), ("baseline + TDA", "baseline"), ("baseline + twins", "baseline"),
                     ("baseline + depth only", "baseline")]:
            ea, eb = (y - preds[a]) ** 2, (y - preds[b]) ** 2
            rel = (ea - eb) / eb.mean()
            lo, hi = boot_ci(rel, np.ones(len(rel)), hours)
            rows.append(dict(target=target, model=f"{a} vs {b}", pct_mse_change=100 * rel.mean(), lo95=100 * lo, hi95=100 * hi))
    return pd.DataFrame(rows), pd.DataFrame(overlap)


def figure(Z, valid):
    import os
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/tda-btc-matplotlib")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from l13_who_wins import COLORS, INK, MUTED, style
    rng = np.random.default_rng(7)
    cand = np.arange(86400, len(Z), 30)
    cand = cand[valid[cand] & (cand % 3600 >= 10)]
    P = Z[rng.choice(cand, 2000, replace=False)]
    G = np.random.default_rng(0).multivariate_normal(P.mean(0), np.cov(P.T), len(P))
    vals, vecs = np.linalg.eigh(np.cov(P.T))
    axes2 = vecs[:, ::-1][:, :2]
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    for i, (name, Q) in enumerate([("Book states", P), ("Gaussian, same covariance", G)]):
        xy = (Q - P.mean(0)) @ axes2
        ax[0].scatter(xy[:, 0], xy[:, 1], s=4, color=COLORS[i], alpha=0.5, label=name, linewidths=0)
        h0 = np.sort(ripser(Q, maxdim=0)["dgms"][0][:-1, 1])[::-1][:30]
        ax[1].plot(np.arange(1, 31), h0, color=COLORS[i], lw=2, marker="o", ms=4, label=name)
    ax[0].set_xlabel("First principal direction", color=INK)
    ax[0].set_ylabel("Second principal direction", color=INK)
    ax[0].set_title("A dense core plus excursions where a band empties", loc="left", color=INK, fontsize=10.5)
    ax[1].set_yscale("log")
    ax[1].set_xlabel("Rank of clump (most isolated first)", color=INK)
    ax[1].set_ylabel("Distance at which the clump joins (log)", color=INK)
    ax[1].set_title("H0: isolated states far beyond the null", loc="left", color=INK, fontsize=10.5)
    for a in ax:
        style(a)
        a.legend(frameon=False, fontsize=8.5, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(OUT / "4_book_cloud.png", dpi=180)
    plt.close(fig)


def main():
    Z, valid, g = band_states()
    glob = global_shape(Z, valid)
    figure(Z, valid)
    print(holes(Z, valid, g))
    d = load()
    t = trades_with_markouts(d)
    f = window_features(Z, valid, g, d, t)
    f.to_csv(OUT / "book_cloud_windows.csv", index=False)
    res, overlap = evaluate(f)
    res.to_csv(OUT / "book_cloud_forecast.csv", index=False)
    overlap.to_csv(OUT / "book_cloud_twin_overlap.csv", index=False)
    pd.set_option("display.width", 220)
    print(glob.round(3).to_string())
    print(res.round(4).to_string())
    print(overlap.round(3).to_string())


if __name__ == "__main__":
    main()
