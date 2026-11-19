"""A slow, hedged trade: Kalshi against Binance when their usual price gap stretches.

Design (fixed before results, November 18, 2026). Fair value of Kalshi = Binance futures price
plus the trailing 60 s average of (Kalshi midpoint - Binance futures), in log bp.
  midpoint version:   enter when the midpoint is X bp from fair value (X = 1, 2, 3, 5).
  executable version: buy when Kalshi's ask is X bp below fair value, sell when its bid is X bp
                      above (X = 0.5, 1, 2, 3).
Checked once per second; enter after 200 ms or 1 s at Kalshi's quote, hedge at Binance's last
price (0.02 bp charged for Binance's spread), hold 10, 60 or 300 s, exit at Kalshi's quote.
One position at a time. Nothing is fitted. Before fees. Nov 12-17 with the l13 exclusions.
"""
import numpy as np
import pandas as pd

from l13_who_wins import DAY_SLOTS, OUT, boot_ci, load


def main():
    d = load()
    with np.errstate(divide="ignore", invalid="ignore"):
        lb, la = np.log(d["bid"]) * 1e4, np.log(d["ask"]) * 1e4
    lmid, fut, use = d["lmid"], d["fut"], d["use"]
    n = len(lmid)
    fair = pd.Series(lmid - fut).rolling(600, min_periods=300).mean().to_numpy() + fut
    signals = {"midpoint": lambda x: np.where(lmid - fair <= -x, 1, np.where(lmid - fair >= x, -1, 0)),
               "executable": lambda x: np.where(fair - la >= x, 1, np.where(lb - fair >= x, -1, 0))}
    thresholds = {"midpoint": (1, 2, 3, 5), "executable": (0.5, 1, 2, 3)}
    every_second = np.arange(n) % 10 == 9
    rows = []
    for version, make in signals.items():
        for x in thresholds[version]:
            sig = make(x)
            sig[~use | ~every_second] = 0
            cand = np.flatnonzero(sig)
            for delay in (2, 10):
                for hold in (100, 600, 3000):
                    trades, nxt = [], 0
                    for c in cand:
                        if c < nxt:
                            continue
                        e, out = c + delay, c + delay + hold
                        if out >= n or not (use[e] and use[out]):
                            continue
                        s = sig[c]
                        k_in, k_out = (la[e], lb[out]) if s > 0 else (lb[e], la[out])
                        trades.append((c, s * (k_out - k_in) - s * (fut[out] - fut[e]) - 0.02,
                                       s * (lmid[out] - lmid[e]) - s * (fut[out] - fut[e]), (la[e] - lb[e])))
                        nxt = out
                    if not trades:
                        continue
                    t = pd.DataFrame(trades, columns=["slot", "pnl", "pnl_at_mid", "spread"])
                    day = 11 + t.slot // DAY_SLOTS
                    lo, hi = boot_ci(t.pnl.to_numpy(), np.ones(len(t)), (t.slot // 36000).to_numpy())
                    rows.append(dict(version=version, threshold_bp=x, delay_ms=100 * delay, hold_s=hold / 10, trades=len(t),
                                     pnl_bp=t.pnl.mean(), lo95=lo, hi95=hi, pnl_before_spread_bp=t.pnl_at_mid.mean(),
                                     entry_spread_bp=t.spread.median(), nov12_14=t.pnl[day <= 14].mean(),
                                     nov15_17=t.pnl[day >= 15].mean(), win_rate=(t.pnl > 0).mean()))
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "gap_trade.csv", index=False)
    pd.set_option("display.width", 220)
    print(out.round(3).to_string())


if __name__ == "__main__":
    main()
