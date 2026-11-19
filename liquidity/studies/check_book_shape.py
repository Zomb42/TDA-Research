"""Independent spot checks of derived ladders, flows, coordinates and discrete band ages."""
from collections import Counter, defaultdict
from decimal import Decimal
import gzip
import json
import sys

import numpy as np
import pyarrow.parquet as pq
from scipy.ndimage import label

from l01_snapshots import CACHE, LEVEL_FIELDS, RESULTS, ROOT, SOURCE
from l02_describe import GRID_CACHE
from l03_band_age import band_cases, verify_tracker

sys.path.insert(0, str(ROOT / "market_data"))
from audit_btc_archive import decimal_book


def check_interval(hour, begin, end):
    name = hour + "-00-00Z"
    table = pq.read_table(CACHE / (name+".parquet")).slice(begin, end-begin).to_pylist()
    book, epoch, seq = {}, 0, -1
    ready, interrupted = False, False
    second = 0
    flows = defaultdict(lambda: [0, 0, 0])
    deltas = trades = 0
    with gzip.open(SOURCE / "kalshi_perp" / (name+".jsonl.gz"), "rt") as stream:
        anchor = json.loads(next(stream))["book_anchor"]
        book = decimal_book(anchor)
        epoch, seq, ready = anchor["epoch"], anchor["seq"], True
        for line in stream:
            row = json.loads(line)
            stamp = row["received_at"]
            minute, sec = int(stamp[14:16]), int(stamp[17:19])
            now = minute*60+sec
            while second < min(now, end):
                if second >= begin:
                    saved = table[second-begin]
                    stored = dict(zip(saved[LEVEL_FIELDS[0]], zip(*(saved[k] for k in LEVEL_FIELDS[1:])), strict=True))
                    expected = {}
                    for side, direction in (("bid", -1), ("ask", 1)):
                        for price, size in book.get(side, {}).items():
                            key = direction*int(price*10000)
                            expected[key] = (int(size*100), *flows[key])
                    expected.update({key: (0, *val) for key, val in flows.items() if key not in expected})
                    assert stored == expected, (hour, second, "levels or flows")
                    assert saved["book_seq"] == seq and saved["epoch"] == epoch
                    assert saved["trade_count"] == trades and saved["delta_count"] == deltas
                    assert int(saved["end_utc"].timestamp()) % 3600 == (second+1) % 3600
                    bb = int(max(book["bid"])*10000) if ready and book["bid"] else 0
                    ba = int(min(book["ask"])*10000) if ready and book["ask"] else 0
                    assert (bb, ba) == (saved["best_bid_tick"], saved["best_ask_tick"])
                    assert saved["complete"] == bool(ready and bb and ba and not interrupted)
                    assert saved["crossed_or_locked"] == bool(ba and bb >= ba)
                second += 1
                flows.clear()
                trades = deltas = 0
                interrupted = not ready
            if second == end:
                return end-begin
            c = row.get("control")
            msg = row.get("message", {})
            kind = msg.get("type")
            payload = msg.get("msg", {})
            if c in ("connected", "gap_start"):
                ready, interrupted, book = False, True, {}
            elif kind == "orderbook_snapshot":
                book = decimal_book(payload)
                epoch, seq = row["epoch"], msg["seq"]
                ready, interrupted = True, True
            elif kind == "orderbook_delta":
                side, price, delta = payload["side"], Decimal(payload["price"]), Decimal(payload["delta"])
                book[side][price] = book[side].get(price, 0) + delta
                if not book[side][price]:
                    del book[side][price]
                key = (-1 if side == "bid" else 1)*int(price*10000)
                flows[key][0 if delta >= 0 else 1] += int(abs(delta)*100)
                seq = msg["seq"]
                deltas += 1
            elif kind == "trade":
                key = (-1 if payload["taker_side"] == "ask" else 1)*int(Decimal(payload["price"])*10000)
                flows[key][2] += int(Decimal(payload["count"])*100)
                trades += 1
    raise ValueError("Window extends beyond input")


def slow_ages(rows, t):
    # Reference method labels each 1-D slice independently, then walks its components backward.
    cur, n = label(rows[t])
    results = {}
    for group in range(1, n+1):
        here = cur == group
        branch_age = 0
        for i in range(t-1, -1, -1):
            prior = label(rows[i])[0]
            parents = set(prior[here]) - {0}
            if len(parents) != 1:
                break
            there = prior == parents.pop()
            if len(set(cur[there]) - {0}) != 1:
                break
            here, cur = there, prior
            branch_age += 1
        cur = label(rows[t])[0]
        for b in np.flatnonzero(cur == group):
            lows = np.flatnonzero(~rows[:t+1, b])
            results[b] = (t-(lows[-1]+1 if len(lows) else 0), branch_age)
    return results


def main():
    verify_tracker()
    checks = {f"{h}/{b}-{e}":check_interval(h,b,e) for h,b,e in [
        ("2026-11-11T00", 0, 120), ("2026-11-12T08", 3045, 3070), ("2026-11-17T23", 2880, 3000)]}
    with np.load(GRID_CACHE) as data:
        grid, valid = data["grid"], data["valid"]
    offset = 86400 + 12*3600
    ref = Counter()
    for s in (0, 1):
        cut = np.quantile(grid[:86399, s][valid[:86399]], .90)
        depth = grid[offset:offset+720, s]
        points = np.arange(59, len(depth)-60, 60)
        eligible = depth >= cut
        cases = band_cases(depth, valid[offset:offset+720], cut, points, s)
        for t in points:
            ages = slow_ages(eligible, t)
            observed = cases[cases.t == t]
            assert set(observed["bin"]) == set(ages)
            for r in observed.itertuples():
                assert (r.bin_age_s, r.branch_age_s) == ages[r.bin]
                assert r.outcome == eligible[t+60, r.bin]
                assert r.continuous == all(eligible[t:t+61, r.bin])
                labels = label(eligible[t])[0]
                reached = labels == labels[r.bin]
                for row in eligible[t+1:t+61]:
                    labels = label(row)[0]
                    reached = np.isin(labels, list(set(labels[reached]) - {0}))
                assert r.connected == reached[r.bin]
                window = eligible[t:t+61].copy()
                for b in range(window.shape[1]):
                    hits = np.flatnonzero(window[:, b])
                    for left, right in zip(hits, hits[1:]):
                        if right-left <= 5:
                            window[left:right, b] = True
                labels = label(window[0])[0]
                reached = labels == labels[r.bin]
                for row in window[1:]:
                    labels = label(row)[0]
                    reached = np.isin(labels, list(set(labels[reached]) - {0}))
                assert r.bridged == reached[r.bin]
                ref["independent_band_age_endpoint_and_path_checks"] += 1
    report = dict(decimal_replay_seconds=checks, **ref, synthetic_graph_checks="passed",
                  inputs="Unsmoothed native levels; integer price and contract quantities; UTC receipt clock")
    (RESULTS / "verification.json").write_text(json.dumps(report, indent=2)+"\n")
    print(report)


if __name__ == "__main__":
    main()
