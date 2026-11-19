"""Can a market maker on Kalshi survive by pulling quotes when Binance moves?

Design (fixed before results were seen, November 18, 2026):
- Our maker always rests a small order at Kalshi's best bid and best ask. Its fills are the real
  trades that printed at the pre-trade best quote, weighted by contracts (a small, constant share
  of the queue). Deeper prints are ignored. Fills are scored by markout (as in l13) at 1 s and 60 s.
- Filter: whenever Binance futures move at least X bp within one 100 ms window j, quotes are off
  during windows j+1+r ... j+3+r (300 ms), where r is our reaction delay in 100 ms steps.
  Trades in the window of the move itself are never protected.
- Variants: X = 0.5, 1, 2 bp; r = 0, 1, 2 (0, 100, 200 ms); pull both sides, or only the side a
  Binance move threatens (asks after a rise, bids after a fall).
- Primary: X = 1 bp, r = 1 (100 ms), threatened side only. The Binance signal needs roughly 75 ms
  to reach the US, so r = 0 is optimistic.
- Scored on Nov 12-17 with the l13 exclusions. Intervals resample whole hours.
- Limits: assumes our share of the queue is unchanged after we re-quote, and ignores fees.
"""
import numpy as np
import pandas as pd

from l13_who_wins import OUT, S_NS, boot_ci, load, trades_with_markouts


def main():
    d = load()
    t = trades_with_markouts(d)
    touch = np.where(t.side > 0, t.price_tick == t.ask_tick, t.price_tick == t.bid_tick)
    t = t[touch & t.mo_60.notna().to_numpy()].copy()
    slot = ((t.received_ns.to_numpy() - S_NS) // 10**8).astype(int)
    move = np.r_[np.nan, np.diff(d["fut"])]
    n = len(move)
    w, hours = t.weight.to_numpy(), t.hour.to_numpy()
    # The resting side that this taker hit: taker buy (side +1) hits our ask.
    resting_ask = t.side.to_numpy() > 0
    base = {h: np.average(t[f"mo_{h}"], weights=w) for h in (1, 60)}
    rows = [dict(threshold_bp=np.nan, reaction_ms=np.nan, sides="no filter", volume_kept=1.0,
                 kept_mo_1=base[1], kept_mo_60=base[60], avoided_mo_1=np.nan,
                 lo95=boot_ci(t.mo_1.to_numpy(), w, hours)[0], hi95=boot_ci(t.mo_1.to_numpy(), w, hours)[1],
                 total_1s_vs_unfiltered=1.0)]
    total_unfiltered = (t.mo_1 * w).sum()
    for x in (0.5, 1, 2):
        up = np.nan_to_num(move) >= x
        down = np.nan_to_num(move) <= -x
        for r in (0, 1, 2):
            # Quotes off in window k if a qualifying move happened in any of windows k-3-r ... k-1-r.
            def recent(flag):
                c = np.r_[0, np.cumsum(flag)]
                k = np.arange(n)
                lo, hi = np.clip(k - 3 - r, 0, n), np.clip(k - r, 0, n)
                return (c[hi] - c[lo]) > 0
            off_up, off_down = recent(up)[slot], recent(down)[slot]
            for sides in ("both sides", "threatened side"):
                if sides == "both sides":
                    off = off_up | off_down
                else:
                    off = (resting_ask & off_up) | (~resting_ask & off_down)
                keep = ~off
                k_mo1 = t.mo_1.to_numpy()[keep]
                lo, hi = boot_ci(k_mo1, w[keep], hours[keep])
                rows.append(dict(threshold_bp=x, reaction_ms=100 * r, sides=sides, volume_kept=w[keep].sum() / w.sum(),
                                 kept_mo_1=np.average(k_mo1, weights=w[keep]),
                                 kept_mo_60=np.average(t.mo_60.to_numpy()[keep], weights=w[keep]),
                                 avoided_mo_1=np.average(t.mo_1.to_numpy()[off], weights=w[off]) if off.any() else np.nan,
                                 lo95=lo, hi95=hi,
                                 total_1s_vs_unfiltered=(k_mo1 * w[keep]).sum() / total_unfiltered))
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "quote_filter.csv", index=False)
    pd.set_option("display.width", 200)
    print(f"Touch fills scored: {len(t):,}; share of all scored volume at the touch: see markouts.csv")
    print(out.round(3).to_string())


if __name__ == "__main__":
    main()
