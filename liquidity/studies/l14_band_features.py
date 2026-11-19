"""Does the band graph add anything once Binance and plain book measures are known?

Design (fixed before results were seen, November 18, 2026):
- Decision every whole second. Fit on Nov 12-14, score on Nov 15-17. First 10 s of each hour,
  invalid seconds, and windows that touch them are excluded.
- Targets. Direction: Kalshi midpoint change over the next 1, 5, 10 s (bp).
  Size of moves: log(0.01 + realised variance) over the next 10 s and 60 s, where realised
  variance is the sum of squared 100 ms midpoint changes (bp^2).
- Baseline, direction: book imbalance within 5 bp; Binance gap over the last 100, 300, 1000 ms.
- Baseline, size: log past realised variance of Kalshi (10, 60, 300 s) and Binance futures
  (10, 60 s); |Binance gap| (100, 300, 1000 ms); log spread; log depth within 5 bp per side;
  hour of day (sine and cosine).
- Band features (Astra's discrete time-Reeb graph: 1-bp midpoint bins out to 25 bp, the frozen
  November 11 90th-percentile cutoff, no smoothing, bands linked across seconds when they share
  a bin). Per side: deaths, splits, births and merges in the last 5 s; current band count;
  mean age of current branches (log 1 + s). For direction they enter as ask minus bid.
- Plain twins (the same events without connectivity). Per side: bins that rose above or fell
  below the cutoff in the last 5 s; current high-bin count; |change in depth within 25 bp| over
  5 s (log). For direction they enter as ask minus bid.
- Model: ordinary least squares on standardised features (with ~250,000 fit seconds and at most
  ~30 features, a penalty would change nothing). Score: out-of-sample R^2 and the change in mean
  squared error, with 95% intervals from resampling whole hours of the scoring period.
- Decisive row: baseline + twins + band against baseline + twins.
"""
import numpy as np
import pandas as pd

from l01_snapshots import RESULTS
from l02_describe import GRID_CACHE
from l03_band_age import WEIGHTS, branch_starts, intervals
from l06_book_breaks import countbits, transition_arrays
from l13_who_wins import CACHE, DAY_SLOTS, OUT, boot_ci, load

CUT = pd.read_csv(RESULTS / "cutoffs.csv").query("quantile == 0.9").set_index("side").threshold_usd
WINDOW = 5


def trailing_sum(x, w):
    c = np.cumsum(np.r_[np.zeros((1,) + x.shape[1:]), x], axis=0)
    out = np.full(x.shape, np.nan)
    out[w:] = c[w + 1:] - c[1:-w]
    return out


def mean_branch_age(masks):
    n = len(masks)
    born_mean = np.full(n, np.nan)
    prev, born = 0, []
    for t in np.flatnonzero(np.r_[True, masks[1:] != masks[:-1]]):
        m = int(masks[t])
        born = branch_starts(prev, m, born, t)
        prev = m
        born_mean[t] = np.mean(born) if born else np.nan
    filled = pd.Series(born_mean).ffill().to_numpy()
    has = np.array([bool(m) for m in masks])
    return np.where(has, np.log1p(np.arange(n) - filled), 0.0)


def side_features(depth, valid, cut):
    masks = ((depth >= cut) & valid[:, None]).astype(np.uint32) @ WEIGHTS
    masks = masks.astype(np.int64)
    tr = np.zeros((len(masks), 6))
    tr[1:] = transition_arrays(masks[:-1], masks[1:])
    deaths = np.r_[0, countbits(tr[1:, 2].astype(np.int64))]
    splits = np.r_[0, countbits(tr[1:, 3].astype(np.int64))]
    births, merges = tr[:, 4], tr[:, 5]
    up = np.r_[0, countbits(masks[1:] & ~masks[:-1])]
    down = np.r_[0, countbits(masks[:-1] & ~masks[1:])]
    total = depth.sum(axis=1)
    band = dict(deaths=trailing_sum(deaths, WINDOW), splits=trailing_sum(splits, WINDOW),
                births=trailing_sum(births, WINDOW), merges=trailing_sum(merges, WINDOW),
                bands=np.array([len(intervals(int(m))) for m in masks], float), age=mean_branch_age(masks))
    twin = dict(bins_up=trailing_sum(up.astype(float), WINDOW), bins_down=trailing_sum(down.astype(float), WINDOW),
                high_bins=countbits(masks).astype(float),
                depth_change=np.log1p(np.abs(total - np.r_[np.full(WINDOW, np.nan), total[:-WINDOW]]) / 1000))
    return band, twin


def realised(lm, ends, steps, forward):
    d2 = np.r_[0, np.diff(lm)] ** 2
    c = np.r_[0, np.cumsum(np.nan_to_num(d2))]
    bad = np.r_[0, np.cumsum(~np.isfinite(d2))]
    lo, hi = (ends, ends + steps) if forward else (ends - steps, ends)
    lo, hi = np.clip(lo, 0, len(lm) - 1), np.clip(hi, 0, len(lm) - 1)
    rv = c[hi + 1] - c[lo + 1]
    return np.where(bad[hi + 1] - bad[lo + 1] == 0, np.log(0.01 + rv), np.nan)


def evaluate(y, blocks, fit, test, hours):
    rows, preds = [], {}
    for name, cols in blocks.items():
        X = np.column_stack(cols)
        mu, sd = X[fit].mean(0), X[fit].std(0)
        sd[sd == 0] = 1
        Z = np.c_[(X - mu) / sd, np.ones(len(X))]
        beta = np.linalg.lstsq(Z[fit], y[fit], rcond=None)[0]
        preds[name] = Z[test] @ beta
        rows.append(dict(model=name, features=X.shape[1],
                         r2_out_of_sample=1 - np.mean((y[test] - preds[name]) ** 2) / np.var(y[test])))
    out = pd.DataFrame(rows)
    err = {k: (y[test] - p) ** 2 for k, p in preds.items()}
    for a, b in [("baseline + twins + band", "baseline + twins"), ("baseline + band", "baseline"),
                 ("baseline + twins", "baseline")]:
        diff = err[a] - err[b]
        rel = diff / np.mean(err[b])
        lo, hi = boot_ci(rel, np.ones(len(rel)), hours[test])
        out.loc[out.model == a, ["pct_mse_change_vs", "vs_model", "lo95", "hi95"]] = [100 * rel.mean(), b, 100 * lo, 100 * hi]
    return out


def main():
    d = load()
    z = np.load(GRID_CACHE)
    grid, valid = z["grid"], z["valid"]
    n = len(grid)
    e = 10 * np.arange(n) + 9
    feats = {}
    for s, side in enumerate(("bid", "ask")):
        band, twin = side_features(grid[:, s], valid, CUT[side])
        feats.update({f"{side}_band_{k}": v for k, v in band.items()})
        feats.update({f"{side}_twin_{k}": v for k, v in twin.items()})
    # Explained share of each band feature by its twins (fit on all usable seconds, descriptive).
    lm, fut = d["lmid"], d["fut"]

    def back(x, lag):
        return x[e] - x[np.maximum(e - lag, 0)]
    gaps = [back(fut, L) - back(lm, L) for L in (1, 3, 10)]
    near_bid, near_ask = grid[:, 0, :5].sum(1), grid[:, 1, :5].sum(1)
    imbalance = (near_bid - near_ask) / np.maximum(near_bid + near_ask, 1)
    spread = np.log((d["ask"] - d["bid"])[e] / d["mid"][e] * 1e4)
    hour = (np.arange(n) // 3600) % 24
    vol_base = [realised(lm, e, 100, False), realised(lm, e, 600, False), realised(lm, e, 3000, False),
                realised(fut, e, 100, False), realised(fut, e, 600, False), *[np.abs(g) for g in gaps], spread,
                np.log1p(near_bid / 1000), np.log1p(near_ask / 1000), np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24)]
    band_names = ("deaths", "splits", "births", "merges", "bands", "age")
    twin_names = ("bins_up", "bins_down", "high_bins", "depth_change")
    signed_band = [feats[f"ask_band_{k}"] - feats[f"bid_band_{k}"] for k in band_names]
    signed_twin = [feats[f"ask_twin_{k}"] - feats[f"bid_twin_{k}"] for k in twin_names]
    all_band = [feats[f"{s}_band_{k}"] for s in ("bid", "ask") for k in band_names]
    all_twin = [feats[f"{s}_twin_{k}"] for s in ("bid", "ask") for k in twin_names]

    use = d["use"][e] & valid
    usable = use & (np.arange(n) % 3600 >= 310)  # trailing windows up to 300 s stay inside the hour's valid data
    missing = np.r_[0, np.cumsum(~use)]
    day = np.arange(n) // 86400 + 11
    hours = np.arange(n) // 3600
    rows, twin_r2 = [], []
    for k, band in zip(band_names, signed_band):
        ok = usable & np.isfinite(band) & np.all(np.isfinite(np.column_stack(signed_twin)), axis=1)
        X = np.c_[np.column_stack(signed_twin)[ok], np.ones(ok.sum())]
        r = band[ok] - X @ np.linalg.lstsq(X, band[ok], rcond=None)[0]
        twin_r2.append(dict(band_feature=f"ask minus bid {k}", share_explained_by_twins=1 - r.var() / band[ok].var()))
    targets = []
    for h in (1, 5, 10):
        y = lm[np.minimum(e + 10 * h, len(lm) - 1)] - lm[e]
        targets.append((f"direction, next {h} s", y, h, [imbalance] + gaps, signed_twin, signed_band))
    for h in (10, 60):
        targets.append((f"size of moves, next {h} s", realised(lm, e, 10 * h, True), h, vol_base, all_twin, all_band))
    for name, y, h, base, twin, band in targets:
        clean = usable & (missing[np.minimum(np.arange(n) + h + 1, n)] == missing[np.arange(n)])
        cols = base + twin + band
        ok = clean & np.isfinite(y) & np.all(np.isfinite(np.column_stack(cols)), axis=1) & (day >= 12)
        fit, test = ok & (day <= 14), ok & (day >= 15)
        blocks = {"baseline": base, "baseline + twins": base + twin, "baseline + band": base + band,
                  "baseline + twins + band": base + twin + band}
        res = evaluate(y, blocks, fit, test, hours)
        res.insert(0, "target", name)
        res["fit_seconds"], res["test_seconds"] = fit.sum(), test.sum()
        rows.append(res)
    out = pd.concat(rows, ignore_index=True)
    out.to_csv(OUT / "band_vs_plain.csv", index=False)
    pd.DataFrame(twin_r2).to_csv(OUT / "band_twin_overlap.csv", index=False)
    pd.set_option("display.width", 220)
    print(out.round(4).to_string())
    print(pd.DataFrame(twin_r2).round(3).to_string())


if __name__ == "__main__":
    main()
