"""Who makes money trading against this book, and why? (Kalshi BTC perp vs Binance, Nov 12-17)

Run after l10_reference_tape.py, l11_bbo_tape.py and l12_binance_grid.py. Everything is before
fees. Spread crossing is a real trading cost and is always included where stated.

Sections (one results file each, in results/who_wins/):
  A  leadlag.csv         Does another market move first? Kalshi midpoint vs Binance futures/spot
                         at 100 ms lags, and vs Kalshi's own published reference index.
  B  markouts.csv        When a resting order is filled, what is it worth later? (maker markout)
  C  slow_taker.csv      Can someone who sees Binance late profit by taking on Kalshi?
  D  resting_orders.csv  Is there a distance from the midpoint where a slow resting order pays?
  E  predictability.csv  Book imbalance (plain) vs the Binance gap for the next 1-10 s.
  F  summary.json        Headline numbers, including Reeb-graph split seconds vs Binance moves.
"""
import json
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/tda-btc-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from l01_snapshots import CACHE, RESULTS, START

OUT = RESULTS.parent / "who_wins"
S_NS = int(START.timestamp()) * 10**9
DAY_SLOTS = 864_000                 # 100 ms slots per day; Nov 11 is excluded from every statistic
HOUR_SLOTS = 36_000
SKIP_SLOTS = 100                    # first 10 s of each hour: receipt times lag during file rotation
HORIZONS = [0.1, 0.5, 1, 5, 10, 30, 60, 300]
RNG = np.random.default_rng(20261118)
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK, MUTED = "#0b0b0b", "#52514e"


def boot_ci(values, weights, hours, draws=1000):
    """95% interval for a weighted mean, resampling whole UTC hours (moves cluster in time)."""
    ids, inv = np.unique(hours, return_inverse=True)
    num = np.bincount(inv, weights * values)
    den = np.bincount(inv, weights)
    pick = RNG.integers(len(ids), size=(draws, len(ids)))
    counts = np.apply_along_axis(np.bincount, 1, pick, minlength=len(ids))
    est = (counts @ num) / (counts @ den)
    return np.quantile(est, [0.025, 0.975])


def load():
    k = np.load(CACHE / "bbo_100ms.npz")
    b = np.load(CACHE / "binance_100ms.npz")
    bid, ask = k["bid"].astype(float), k["ask"].astype(float)
    valid = k["valid"] & (bid > 0) & (ask > bid)
    mid = np.where(valid, (bid + ask) / 2, np.nan)
    slots = np.arange(len(mid))
    use = (slots >= DAY_SLOTS) & (slots % HOUR_SLOTS >= SKIP_SLOTS) & valid
    return dict(bid=bid, ask=ask, mid=mid, lmid=np.log(mid) * 1e4, use=use,
                fut=np.log(b["fut"]) * 1e4, spot=np.log(b["spot"]) * 1e4)


def lead_lag(d):
    dk = np.diff(d["lmid"])
    ok = d["use"][1:] & d["use"][:-1]
    rows = []
    for venue in ("fut", "spot"):
        dv = np.diff(d[venue])
        for lag in range(-5, 11):
            x = np.roll(dv, lag)
            m = ok & np.roll(ok, lag) & np.isfinite(dk) & np.isfinite(x)
            rows.append(dict(leader=f"binance_{venue}", lag_ms=100 * lag, corr=np.corrcoef(dk[m], x[m])[0, 1]))
    # Kalshi's own reference index, once per second (l10). Positive lag: the index moves after Kalshi.
    tape = pd.read_parquet(CACHE / "reference_tape.parquet").groupby("t").last()
    n = len(d["lmid"]) // 10
    ref = np.full(n, np.nan)
    ref[tape.index.to_numpy()] = tape.ref_tick.to_numpy()
    lref = np.log(pd.Series(ref).ffill().to_numpy()) * 1e4
    kmid = d["lmid"][9::10][:n]
    use1 = d["use"][9::10][:n]
    dr, dm = np.diff(lref), np.diff(kmid)
    ok1 = use1[1:] & use1[:-1]
    for lag in range(-3, 4):
        x = np.roll(dr, -lag)
        m = ok1 & np.roll(ok1, -lag) & np.isfinite(dm) & np.isfinite(x)
        rows.append(dict(leader="kalshi_vs_its_index", lag_ms=-1000 * lag, corr=np.corrcoef(dm[m], x[m])[0, 1]))
    # Share of 1 s Kalshi variance explained by Binance futures in the same and previous second.
    f1 = d["fut"][9::10][:n]
    y, x0, x1 = dm[1:], np.diff(f1)[1:], np.diff(f1)[:-1]
    m = ok1[1:] & np.isfinite(y) & np.isfinite(x0) & np.isfinite(x1)
    X = np.c_[x0[m], x1[m], np.ones(m.sum())]
    beta = np.linalg.lstsq(X, y[m], rcond=None)[0]
    r2 = 1 - np.var(y[m] - X @ beta) / np.var(y[m])
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "leadlag.csv", index=False)
    return out, dict(one_second_r2_on_binance_futures=r2, beta_same_second=beta[0], beta_previous_second=beta[1])


def trades_with_markouts(d):
    t = pd.read_parquet(CACHE / "trades_bbo.parquet")
    t = t[(t.book_valid == 1) & (t.block == 0)].copy()
    t["order"] = ((t.exchange_ms.diff() != 0) | (t.taker_buy.diff() != 0)).cumsum()
    t["order_contracts"] = t.groupby("order").size_100.transform("sum") / 100
    slot = ((t.received_ns.to_numpy() - S_NS) // 10**8).astype(int)
    keep = d["use"][slot]
    t, slot = t[keep].copy(), slot[keep]
    side = np.where(t.taker_buy == 1, 1.0, -1.0)
    m0 = (t.bid_tick + t.ask_tick).to_numpy() / 2
    price = t.price_tick.to_numpy()
    t["side"] = side
    t["edge_bp"] = side * (price - m0) / m0 * 1e4
    n = len(d["mid"])
    for h in HORIZONS:
        k = (t.received_ns.to_numpy() + int(h * 1e9) - S_NS) // 10**8
        later = d["mid"][np.clip(k, 0, n - 1)]
        t[f"mo_{h:g}"] = np.where(k < n, side * (price - later) / m0 * 1e4, np.nan)  # maker's view
    # Binance futures move in the 300 ms before the trade's 100 ms slot (known before the trade).
    prior = d["fut"][np.clip(slot - 1, 0, n - 1)] - d["fut"][np.clip(slot - 4, 0, n - 1)]
    agree = np.sign(prior) * side
    t["binance_300ms"] = np.select([agree > 0, agree < 0], ["with Binance", "against Binance"], "Binance flat")
    t["hour"] = slot // HOUR_SLOTS
    t["day"] = 11 + slot // DAY_SLOTS
    t["weight"] = t.size_100 / 100
    return t


def markouts(t):
    groups = [("all trades", np.ones(len(t), bool))]
    groups += [(g, (t.binance_300ms == g).to_numpy()) for g in ("with Binance", "Binance flat", "against Binance")]
    size_bins = [0, 50, 200, 1000, 5000, np.inf]
    labels = ["<50", "50-200", "200-1k", "1k-5k", "5k+"]
    sizes = pd.cut(t.order_contracts, size_bins, labels=labels, right=False)
    groups += [(f"order {s} contracts", (sizes == s).to_numpy()) for s in labels]
    total = t.weight.sum()
    rows = []
    for name, m in groups:
        g = t[m]
        row = dict(group=name, prints=len(g), volume_share=g.weight.sum() / total,
                   edge_bp=np.average(g.edge_bp, weights=g.weight))
        for h in HORIZONS:
            c = f"mo_{h:g}"
            ok = g[c].notna()
            row[c] = np.average(g[c][ok], weights=g.weight[ok])
            if h in (0.1, 1, 60):
                row[c + "_lo"], row[c + "_hi"] = boot_ci(g[c][ok].to_numpy(), g.weight[ok].to_numpy(), g.hour[ok].to_numpy())
        rows.append(row)
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "markouts.csv", index=False)
    s = t[t.mo_1.notna()]
    daily = s.groupby(["day", "binance_300ms"]).apply(
        lambda g: np.average(g.mo_1, weights=g.weight), include_groups=False).unstack()
    daily["all trades"] = s.groupby("day").apply(lambda g: np.average(g.mo_1, weights=g.weight), include_groups=False)
    daily.to_csv(OUT / "markouts_daily_1s.csv")
    return out, daily


def slow_taker(d):
    """Signal: Binance futures moved at least X bp more than Kalshi in the last 100 ms.
    Take on Kalshi L slots later at the best quote; value at the midpoint 1 s later and at the
    far quote 1 s later (a full round trip). At most one trade per second."""
    bid, ask, mid, lm, fut = d["bid"], d["ask"], d["mid"], d["lmid"], d["fut"]
    n = len(mid)
    gap = np.r_[np.nan, np.diff(fut) - np.diff(lm)]
    rows = []
    for x in (1, 2, 3, 5):
        sig = np.where(gap >= x, 1, np.where(gap <= -x, -1, 0))
        sig[~d["use"]] = 0
        cand = np.flatnonzero(sig)
        keep, last = [], -99
        for c in cand:
            if c - last >= 10:
                keep.append(c)
                last = c
        c = np.array(keep)
        for lat in (0, 1, 2, 5):
            e = np.minimum(c + lat, n - 1)
            x1 = np.minimum(e + 10, n - 1)
            ok = d["use"][e] & d["use"][x1]
            dirn = sig[c][ok]
            e, x1, hours = e[ok], x1[ok], (c[ok] // HOUR_SLOTS)
            fill = np.where(dirn > 0, ask[e], bid[e])
            vs_mid = dirn * (mid[x1] - fill) / mid[e] * 1e4
            round_trip = dirn * (np.where(dirn > 0, bid[x1], ask[x1]) - fill) / mid[e] * 1e4
            spread = (ask[e] - bid[e]) / mid[e] * 1e4
            lo, hi = boot_ci(vs_mid, np.ones(len(vs_mid)), hours)
            rows.append(dict(threshold_bp=x, latency_ms=100 * lat, trades=len(e), pnl_vs_mid_1s_bp=vs_mid.mean(),
                             lo95=lo, hi95=hi, pnl_round_trip_1s_bp=round_trip.mean(),
                             spread_at_entry_bp=np.median(spread)))
    out = pd.DataFrame(rows)
    out["typical_spread_bp"] = np.nanmedian(((ask - bid) / mid * 1e4)[d["use"]])
    out.to_csv(OUT / "slow_taker.csv", index=False)
    return out


def resting_orders(d):
    """Every 10 s, rest a fixed-price buy d bp below and a sell d bp above the midpoint for up to 60 s.
    'through': filled only if a trade prints beyond our price (sure fill regardless of queue).
    'touch': filled if a trade prints at our price (optimistic: assumes we are first in the queue).
    Markout at 60 s after the fill, relative to our price."""
    t = pd.read_parquet(CACHE / "trades_bbo.parquet")
    bid, ask, mid = d["bid"], d["ask"], d["mid"]
    n, w = len(mid), 600
    slot = (t.received_ns.to_numpy() - S_NS) // 10**8
    sell = t.taker_buy.to_numpy() == 0
    price = t.price_tick.to_numpy().astype(float)
    lowest = np.full(n, np.inf)
    np.minimum.at(lowest, slot[sell], price[sell])
    highest = np.full(n, -np.inf)
    np.maximum.at(highest, slot[~sell], price[~sell])
    dec = np.arange(DAY_SLOTS + SKIP_SLOTS, n - w - 700, 100)
    dec = dec[d["use"][dec]]
    lo_path = np.minimum.accumulate(np.lib.stride_tricks.sliding_window_view(lowest, w)[dec + 1], axis=1)
    hi_path = np.maximum.accumulate(np.lib.stride_tricks.sliding_window_view(highest, w)[dec + 1], axis=1)
    m0, hours = mid[dec], dec // HOUR_SLOTS
    rows = []
    for dist in (0.5, 1, 2, 5, 10, 15, 20, 25):
        for rule in ("through", "touch"):
            mos, hrs = [], []
            for sgn in (1, -1):
                if sgn == 1:
                    p = np.minimum(np.floor(m0 * (1 - dist / 1e4)), bid[dec])
                    hit = lo_path < p[:, None] if rule == "through" else lo_path <= p[:, None]
                else:
                    p = np.maximum(np.ceil(m0 * (1 + dist / 1e4)), ask[dec])
                    hit = hi_path > p[:, None] if rule == "through" else hi_path >= p[:, None]
                filled = hit.any(axis=1)
                k = np.minimum(hit.argmax(axis=1) + dec + 1 + 600, n - 1)
                mo = sgn * (mid[k] - p) / m0 * 1e4
                ok = filled & np.isfinite(mo)
                mos.append(mo[ok])
                hrs.append(hours[ok])
            mo, hr = np.concatenate(mos), np.concatenate(hrs)
            lo, hi = boot_ci(mo, np.ones(len(mo)), hr)
            row = dict(distance_bp=dist, fill_rule=rule, orders=2 * len(dec), fill_rate=len(mo) / (2 * len(dec)),
                       markout_60s_bp=mo.mean(), lo95=lo, hi95=hi, pnl_per_order_bp=mo.sum() / (2 * len(dec)))
            for day, v in pd.Series(mo).groupby(11 + hr // 24):
                row[f"nov{day}"] = v.mean()
            rows.append(row)
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "resting_orders.csv", index=False)
    return out


def predictability(d):
    """Linear fits of the next H seconds of Kalshi midpoint change at each whole second.
    Fit on Nov 12-14, score R^2 on Nov 15-17 (out of sample)."""
    z = np.load(CACHE / "midpoint_grid.npz")
    g = z["grid"]
    n = len(g)
    e = 10 * np.arange(n) + 9                      # 100 ms slot at the end of second s
    near_bid, near_ask = g[:, 0, :5].sum(1), g[:, 1, :5].sum(1)
    imbalance = (near_bid - near_ask) / np.maximum(near_bid + near_ask, 1)
    lm, fut = d["lmid"], d["fut"]

    def back(x, lag):
        return x[e] - x[np.maximum(e - lag, 0)]
    gaps = [back(fut, L) - back(lm, L) for L in (1, 3, 10)]
    rows = []
    for h in (1, 5, 10):
        y = lm[np.minimum(e + 10 * h, len(lm) - 1)] - lm[e]
        ok = d["use"][e] & d["use"][np.minimum(e + 10 * h, len(lm) - 1)] & np.isfinite(y)
        for c in gaps:
            ok &= np.isfinite(c)
        day = e // DAY_SLOTS + 11
        fit, test = ok & (day <= 14), ok & (day >= 15)
        for name, cols in [("book imbalance within 5 bp", [imbalance]), ("Binance gap (100, 300, 1000 ms)", gaps),
                           ("both", [imbalance] + gaps)]:
            X = np.column_stack(cols + [np.ones(n)])
            beta = np.linalg.lstsq(X[fit], y[fit], rcond=None)[0]
            resid = y[test] - X[test] @ beta
            rows.append(dict(horizon_s=h, features=name, r2_out_of_sample=1 - np.mean(resid**2) / np.var(y[test])))
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "predictability.csv", index=False)
    return out


def split_seconds(d):
    split = pd.read_csv(RESULTS.parent / "refill" / "all_split_replays.csv").t.to_numpy()
    n = len(d["lmid"]) // 10
    f1 = d["fut"][9::10][:n]
    move = np.abs(np.r_[np.nan, np.diff(f1)])
    use = d["use"][9::10][:n] & np.r_[False, d["use"][9::10][:n][:-1]]
    return dict(split_seconds=len(split), split_share_binance_move_ge_1bp=float(np.nanmean(move[split] >= 1)),
                all_seconds_share_binance_move_ge_1bp=float(np.nanmean(move[use] >= 1)))


def style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color="#e6e5e1", lw=0.8)
    ax.set_axisbelow(True)


def figures(lead, mk, slow):
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    for i, venue in enumerate(["binance_fut", "binance_spot"]):
        s = lead[lead.leader == venue]
        ax.plot(s.lag_ms, s["corr"], color=COLORS[i], lw=2, marker="o", ms=4)
        peak = s.loc[s["corr"].idxmax()]
        ax.annotate({"binance_fut": "Binance futures", "binance_spot": "Binance spot"}[venue],
                    (peak.lag_ms, peak["corr"]), xytext=(12, -4 - 14 * i), textcoords="offset points", color=INK, fontsize=9)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xlabel("How much earlier Binance moved (ms)", color=INK)
    ax.set_ylabel("Correlation with Kalshi's\n100 ms midpoint change", color=INK)
    ax.set_title("Kalshi's price follows Binance about 100–200 ms later", loc="left", color=INK, fontsize=11)
    style(ax)
    fig.tight_layout()
    fig.savefig(OUT / "1_leadlag.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4))
    names = ["all trades", "with Binance", "Binance flat", "against Binance"]
    labels = {"all trades": "All trades", "with Binance": "Trade in direction of Binance's last 300 ms",
              "Binance flat": "Binance flat", "against Binance": "Trade against Binance's last 300 ms"}
    for i, name in enumerate(names):
        r = mk[mk.group == name].iloc[0]
        ys = [r[f"mo_{h:g}"] for h in HORIZONS]
        ax.plot(HORIZONS, ys, color=COLORS[i], lw=2, marker="o", ms=4)
        nudge = {"Binance flat": 6, "all trades": -6}.get(name, 0)
        ax.annotate(labels[name], (HORIZONS[-1], ys[-1]), xytext=(6, nudge), textcoords="offset points",
                    va="center", color=INK, fontsize=8.5)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xscale("log")
    ax.set_xticks(HORIZONS, ["0.1", "0.5", "1", "5", "10", "30", "60", "300"])
    ax.set_xlabel("Seconds after the fill", color=INK)
    ax.set_ylabel("Resting order's gain per contract (bp)", color=INK)
    ax.set_title("Resting orders lose within 0.1 s, mostly to trades that follow Binance", loc="left", color=INK, fontsize=11)
    style(ax)
    ax.set_xlim(0.08, 3000)
    fig.tight_layout()
    fig.savefig(OUT / "2_markouts.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    for i, x in enumerate((1, 2, 3, 5)):
        s = slow[slow.threshold_bp == x]
        ax.plot(s.latency_ms, s.pnl_vs_mid_1s_bp, color=COLORS[i], lw=2, marker="o", ms=5)
        ax.annotate(f"Binance ahead by ≥{x} bp", (s.latency_ms.iloc[-1], s.pnl_vs_mid_1s_bp.iloc[-1]),
                    xytext=(6, 0), textcoords="offset points", va="center", color=INK, fontsize=8.5)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xticks([0, 100, 200, 500], ["0\n(not reachable)", "100", "200", "500"])
    ax.set_xlim(-20, 760)
    ax.set_xlabel("Delay between the Binance move and our order on Kalshi (ms)", color=INK)
    ax.set_ylabel("Gain per trade after 1 s,\nvs midpoint, before fees (bp)", color=INK)
    ax.set_title("Following Binance pays only with no delay at all", loc="left", color=INK, fontsize=11)
    style(ax)
    fig.tight_layout()
    fig.savefig(OUT / "3_slow_taker.png", dpi=180)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = load()
    lead, fit = lead_lag(d)
    t = trades_with_markouts(d)
    mk, daily = markouts(t)
    slow = slow_taker(d)
    rest = resting_orders(d)
    pred = predictability(d)
    summary = dict(evaluation="Nov 12 00:00 - Nov 17 23:50 UTC, first 10 s of each hour excluded",
                   trades_scored=len(t), **fit, **split_seconds(d))
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float) + "\n")
    figures(lead, mk, slow)
    pd.set_option("display.width", 200)
    print(lead.pivot(index="lag_ms", columns="leader", values="corr").round(3))
    print(mk.round(3).to_string())
    print(daily.round(3))
    print(slow.round(3).to_string())
    print(rest.round(3).to_string())
    print(pred.round(4).to_string())
    print(json.dumps(summary, indent=2, default=float))


if __name__ == "__main__":
    main()
