"""G5. Would small changes to the arbitrary settings make the late-day strategy better?

Two versions of the strategy, both cash and SPY-beta neutral inside every peer group:

  A (default, before costs)  signal at 3:40 pm, buy or sell at the 3:50 price,
                             sell at the next open (studies 10-11, Sharpe 2.21)
  B (after fees)             signal at 3:50 pm, closing-auction order in,
                             opening-auction order out, charged the measured fee
                             (0.278 bps on every dollar sold; study 12)

    conda run -n tda python equity/studies/s16_tuning.py        # version A
    conda run -n tda python equity/studies/s16_tuning.py B      # version B

The settings were chosen once and never tuned. The grid, fixed before looking:

  average      the average price the 3:50 price is compared with:
               since the open (current) / last 4 hours / last 2 hours / last hour
  form         raw move (current) / divided by the stock's volatility /
               rank within the day / extremes clipped at 3 standard deviations
  weights      1 / variance (current) / 1 / volatility / equal
  peers        history 252 days (current) or 126; smallest group 2 (current), 3 or 5
  ungrouped    stocks with no peer left out (current) / traded, hedged in their sector

6 x 4 x 4 x 3 x 2 = 576 versions, each run over all of 2017-2026.

Picking the version with the best 10-year Sharpe and quoting that Sharpe would
be optimistic: with 576 tries, some win by luck. So the 10 years are used three ways:

  1. Sensitivity: every version's 10-year Sharpe. Is the current setting on a
     broad plateau, or does one direction clearly help everywhere?
  2. Walk-forward: each year from 2019, pick the version that was best on all
     earlier years, trade it that year. The joined record is what tuning would
     really have earned.
  3. Interleaved years: pick on odd years, score on even years, and the reverse,
     so every one of the 10 years is scored by a choice that never saw it.
"""
import gzip
import itertools
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from s08_path_shape import centred_ranks
from s12_late_day_costs import SEC_FEE_BPS
from tdaeq import data, evaluate, factors, plots, portfolio, signals

STUDY = "s16_tuning"
AVERAGES = {"since the open": None, "last 4 hours": 240, "last 2 hours": 120, "last hour": 60}
FORMS = ["raw move", "divided by volatility", "rank", "clipped at 3 sd"]
WEIGHTS = ["1 / variance", "1 / volatility", "equal"]
PEERS = [(252, 2), (252, 3), (252, 5), (126, 2), (126, 3), (126, 5)]          # (history days, smallest group)
UNGROUPED = ["left out", "sector hedge"]
DEFAULT = ("since the open", "raw move", "1 / variance", (252, 2), "left out")
NAMES = ["average", "form", "weights", "peers", "ungrouped"]


def averages(panel):
    """Average traded price from each window start to 10 and 20 minutes before the close. Cached."""
    cache = plots.folder(STUDY) / "averages.npz"
    if cache.exists():
        return dict(np.load(cache))
    folder = data.dataset_folder(data.INTRADAY) / "raw"
    column = {s: i for i, s in enumerate(panel.symbols)}
    row = {str(d.date()): t for t, d in enumerate(panel.dates)}
    out = {f"{a}|{m}": np.full(panel.returns.shape, np.nan) for a in AVERAGES for m in (10, 20)}
    for path in sorted((folder / "last_half_hour").glob("*.json.gz")):
        late = json.load(gzip.open(path))
        early = json.load(gzip.open(folder / "half_hours" / path.name))
        t = row.get(late["date"])
        if t is None:
            continue
        close = pd.Timestamp(f"{late['date']} {late['close']}", tz="America/New_York").tz_convert("UTC")
        for symbol, bars in late["bars"].items():
            i = column.get(symbol)
            if i is None:
                continue
            timed = [(round((pd.Timestamp(b["t"]) - close).total_seconds() / 60), b)
                     for b in early["bars"].get(symbol, []) + bars]
            for a, minutes_back in AVERAGES.items():
                for m in (10, 20):
                    use = [b for start, b in timed if start <= -m - 10 and (minutes_back is None or start >= -minutes_back)]
                    shares = sum(b["v"] for b in use)
                    if shares > 0:
                        out[f"{a}|{m}"][t, i] = sum(b["v"] * b["vw"] for b in use) / shares
    np.savez_compressed(cache, **out)
    return out


def run_peer_variant(panel, peers, signal_by_average, sigma, outcome, days, fee_bps):
    """Daily net returns of every version that uses this peer-group setting."""
    warnings.filterwarnings("ignore")
    window, smallest = peers
    state = signals.build_state(panel, window=window, plain_groups=None, min_cluster_size=smallest,
                                min_samples=1 if smallest == 2 else None)
    results = {}
    for average, form, weights, ungrouped in itertools.product(AVERAGES, FORMS, WEIGHTS, UNGROUPED):
        raw = signal_by_average[average]
        r = np.zeros(len(days))
        for k, t in enumerate(days):
            ok = (state.group[t] != signals.NOT_USED) & np.isfinite(raw[t]) & np.isfinite(sigma[t]) & np.isfinite(outcome[t])
            if ungrouped == "left out":
                ok &= state.group[t] >= 0
            stocks = np.flatnonzero(ok)
            if len(stocks) < 30:
                continue
            s = raw[t, stocks]
            if form == "divided by volatility":
                s = s / sigma[t, stocks]
            elif form == "rank":
                s = centred_ranks(s[:, None])[:, 0]
            elif form == "clipped at 3 sd":
                s = np.clip(s, s.mean() - 3 * s.std(), s.mean() + 3 * s.std())
            w = {"1 / variance": 1 / sigma[t, stocks] ** 2, "1 / volatility": 1 / sigma[t, stocks],
                 "equal": np.ones(len(stocks))}[weights]
            labels = state.group[t, stocks]
            labels = np.where(labels >= 0, labels, 10_000 + state.sector[stocks])
            columns = factors.group_exposures(labels, state.beta[t, stocks])
            held, _ = portfolio.neutral_book(s, columns, w)
            r[k] = held @ outcome[t, stocks] - np.abs(held).sum() * fee_bps * 1e-4
        results[(average, form, weights, peers, ungrouped)] = r
    return results


def pick_and_trade(returns, keys, years, train_years, test_years):
    """Choose the version with the best Sharpe on train_years; return its daily returns on test_years and its key."""
    train = np.isin(years, train_years)
    scores = [evaluate.sharpe(returns[key][train]) for key in keys]
    best = keys[int(np.nanargmax(scores))]
    return best, np.isin(years, test_years)


def main():
    np.seterr(invalid="ignore", divide="ignore")
    version = sys.argv[1] if len(sys.argv) > 1 else "A"
    folder = f"{STUDY}/{'A_before_costs' if version == 'A' else 'B_auction_after_fees'}"
    panel = data.load_panel()
    intraday = data.load_intraday(panel)
    avg = averages(panel)
    have = np.isfinite(intraday["vwap_10"])       # the loader leaves incomplete stock-days missing; so does the signal
    if not np.allclose(avg["since the open|10"][have], intraday["vwap_10"][have], rtol=1e-9):
        raise RuntimeError("the 'since the open' average does not match the loader")
    n = panel.returns.shape[1]
    to_next_open = np.vstack([panel.open_adj[1:] / panel.close_adj[:-1] - 1, np.full((1, n), np.nan)])
    if version == "A":     # signal at 3:40, bought or sold at the 3:50 price, sold at the next open, no costs
        minutes, fee = 20, 0.0
        outcome = (panel.close_raw / intraday["price_10"]) * (1 + to_next_open) - 1
    else:                  # signal at 3:50, closing auction in, opening auction out, measured fee
        minutes, fee = 10, SEC_FEE_BPS
        outcome = to_next_open
    sigma = np.maximum(pd.DataFrame(panel.returns).rolling(252).std(ddof=1).shift(1).to_numpy(), 1e-4)
    signal_by_average = {a: np.log(intraday[f"price_{minutes}"] / avg[f"{a}|{minutes}"]) for a in AVERAGES}
    base = signals.build_state(panel, plain_groups=None)
    ready = np.isfinite(intraday["price_10"]).sum(axis=1) >= 50
    days = np.flatnonzero(ready & (base.group != signals.NOT_USED).any(axis=1))
    days = days[days < len(panel.dates) - 1]
    dates = panel.dates[days]
    years = dates.year.to_numpy()
    out = plots.folder(folder)
    pd.set_option("display.width", 250)

    cache = out / "daily_net_returns.parquet"
    if cache.exists():
        frame = pd.read_parquet(cache)
    else:
        parts = Parallel(n_jobs=6)(delayed(run_peer_variant)(panel, peers, signal_by_average, sigma, outcome, days, fee)
                                   for peers in PEERS)
        merged = {k: v for part in parts for k, v in part.items()}
        frame = pd.DataFrame({" | ".join(map(str, k)): v for k, v in merged.items()}, index=dates)
        frame.to_parquet(cache)
    key = lambda k: " | ".join(map(str, k))
    keys = list(frame.columns)
    returns = {k: frame[k].to_numpy() for k in keys}
    default = key(DEFAULT)
    print(f"{len(keys)} versions, {len(days)} days, {dates[0].date()} to {dates[-1].date()}")

    # 1. sensitivity
    full = pd.DataFrame([dict(zip(NAMES, k.split(" | ")), key=k, sharpe=evaluate.sharpe(returns[k]),
                              sharpe_odd=evaluate.sharpe(returns[k][years % 2 == 1]),
                              sharpe_even=evaluate.sharpe(returns[k][years % 2 == 0]),
                              bps_per_day=returns[k].mean() * 1e4) for k in keys])
    full.to_csv(out / "all_versions.csv", index=False)
    d = full.set_index("key").loc[default]
    print(f"current setting: 10-year Sharpe {d.sharpe:.2f}; rank {int((full.sharpe > d.sharpe).sum()) + 1} of {len(full)}")
    print("10-year Sharpe across all versions: " + ", ".join(f"{q:.0%} {full.sharpe.quantile(q):.2f}" for q in (0.1, 0.25, 0.5, 0.75, 0.9))
          + f", best {full.sharpe.max():.2f}")
    print("top 10 versions over 10 years:")
    print(full.sort_values("sharpe", ascending=False).head(10)[NAMES + ["sharpe", "sharpe_odd", "sharpe_even"]].round(2).to_string(index=False))
    stable = full[["sharpe_odd", "sharpe_even"]].corr(method="spearman").iloc[0, 1]
    print(f"rank correlation of each version's Sharpe on odd years against even years: {stable:.2f}")

    one_at_a_time = []
    for name, values in zip(NAMES, (AVERAGES, FORMS, WEIGHTS, PEERS, UNGROUPED)):
        for v in values:
            k = list(DEFAULT)
            k[NAMES.index(name)] = v
            r = returns[key(k)]
            s, low, high = evaluate.sharpe_ci(r)
            diff, dl, dh = evaluate.sharpe_difference_ci(r, returns[default])
            one_at_a_time.append({"setting": name, "value": str(v), "sharpe": s, "low": low, "high": high,
                                  "minus_current": diff, "diff_low": dl, "diff_high": dh,
                                  "sharpe_odd_years": evaluate.sharpe(r[years % 2 == 1]),
                                  "sharpe_even_years": evaluate.sharpe(r[years % 2 == 0]),
                                  "median_over_all_other_settings": full[full[name] == str(v)].sharpe.median()})
    one_at_a_time = pd.DataFrame(one_at_a_time)
    one_at_a_time.to_csv(out / "one_at_a_time.csv", index=False)
    print(one_at_a_time.round(2).to_string(index=False))

    # 2. walk-forward and 3. interleaved years
    chosen, wf = [], np.full(len(days), np.nan)
    for y in range(2019, 2027):
        best, test = pick_and_trade(returns, keys, years, list(range(2017, y)), [y])
        wf[test] = returns[best][test]
        chosen.append({"method": "walk-forward", "scored_year": y, "chosen": best})
    inter = np.full(len(days), np.nan)
    odd, even = [y for y in range(2017, 2027) if y % 2], [y for y in range(2017, 2027) if not y % 2]
    for train, test_years in ((odd, even), (even, odd)):
        best, test = pick_and_trade(returns, keys, years, train, test_years)
        inter[test] = returns[best][test]
        chosen.append({"method": "interleaved", "scored_year": f"{'even' if test_years == even else 'odd'} years", "chosen": best})
    chosen = pd.DataFrame(chosen)
    chosen.to_csv(out / "chosen_versions.csv", index=False)
    print(chosen.to_string(index=False))

    rows = []
    hindsight = full.sort_values("sharpe").key.iloc[-1]
    wf_mask = years >= 2019
    for label, r, mask in (("Current setting, 2019-2026", returns[default], wf_mask),
                           ("Walk-forward tuned, 2019-2026", wf, wf_mask),
                           ("Current setting, 2017-2026", returns[default], np.ones(len(days), bool)),
                           ("Interleaved-years tuned, 2017-2026", inter, np.ones(len(days), bool)),
                           ("Best of 576 in hindsight, 2017-2026 (optimistic)", returns[hindsight], np.ones(len(days), bool))):
        s, low, high = evaluate.sharpe_ci(r[mask])
        perf = evaluate.performance(r[mask])
        row = {"version": label, "days": int(mask.sum()), "sharpe": s, "low": low, "high": high,
               "bps_per_day": perf["mean_bps"], "return_pct_per_year": perf["cagr_pct"], "max_drawdown_pct": perf["max_drawdown_pct"]}
        if "tuned" in label:
            diff, dl, dh = evaluate.sharpe_difference_ci(r[mask], returns[default][mask])
            row.update({"minus_current": diff, "diff_low": dl, "diff_high": dh})
        rows.append(row)
    verdict = pd.DataFrame(rows)
    verdict.to_csv(out / "tuned_against_current.csv", index=False)
    print(verdict.round(2).to_string(index=False))

    figure(folder, version, one_at_a_time, full, dates, {"Current setting": returns[default], "Walk-forward tuned (from 2019)": wf,
                                        "Interleaved-years tuned": inter, "Best of 576 in hindsight": returns[hindsight]})


def figure(folder, version, one, full, dates, series):
    costs = "before costs" if version == "A" else "after fees"
    fig, (left, right) = plt.subplots(1, 2, figsize=(14, 5), layout="constrained", gridspec_kw={"width_ratios": [1, 1.2]})
    labels = [f"{s}: {v}" for s, v in zip(one.setting, one.value)][::-1]
    y = np.arange(len(one))
    rows = one.iloc[::-1]
    current = [v == str(DEFAULT[NAMES.index(s)]) for s, v in zip(rows.setting, rows.value)]
    left.errorbar(rows.sharpe, y, xerr=[rows.sharpe - rows.low, rows.high - rows.sharpe], fmt="none", ecolor=plots.AXIS, elinewidth=2)
    left.scatter(rows.sharpe, y, color=[plots.ORANGE if c else plots.BLUE for c in current], zorder=3, s=30)
    left.axvline(rows.sharpe[current].iloc[0], color=plots.ORANGE, lw=1, ls="--")
    left.set_yticks(y, labels, fontsize=8)
    left.grid(axis="y", visible=False)
    left.set_xlabel(f"10-year Sharpe {costs} (95% interval); orange = current setting")
    left.set_title("Change one setting at a time", fontsize=10)
    colors = [plots.ORANGE, plots.BLUE, plots.AQUA, plots.GRAY]
    for (name, r), color in zip(series.items(), colors):
        ok = np.isfinite(r)
        right.plot(dates[ok], np.cumsum(r[ok]) * 100, color=color, lw=1.6 if color != plots.GRAY else 1.2,
                   ls="-" if color != plots.GRAY else ":", label=name)
    right.axhline(0, color=plots.AXIS, lw=1)
    right.set_ylabel(f"Cumulative return {costs}, % (1x gross)")
    right.legend(loc="upper left")
    right.set_title("Does tuning pay when the choice cannot see the years it is scored on?", fontsize=10)
    title = ("version A: signal at 3:40, traded at 3:50, sold at the next open, before costs" if version == "A"
             else "version B: closing auction in, opening auction out, after fees")
    fig.suptitle(f"Tuning the late-day reversal, {title} (576 versions, 2017-2026)",
                 x=0.01, ha="left", fontweight="bold", fontsize=10)
    plots.save(fig, folder, "1_tuning.png")


if __name__ == "__main__":
    main()
