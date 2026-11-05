"""Independent expanded-panel data checks and descriptive coverage figures."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    out = parser.parse_args().dataset.resolve()
    manifest = json.loads((out / "manifest.json").read_text())
    selection = json.loads((out / "selection_audit.json").read_text())
    plan = json.loads((out / "collection_plan.json").read_text())
    universe = pd.read_csv(out / "universe.csv")
    symbols = universe.symbol.tolist()
    equities = universe.loc[universe.role.eq("equity"), "symbol"].tolist()
    assert len(equities) == 200 and len(symbols) == 201 and universe.symbol.is_unique
    assert hashlib.sha256((out / "universe.csv").read_bytes()).hexdigest() == selection["universe_sha256"]
    assert hashlib.sha256((out / "collection_plan.json").read_bytes()).hexdigest() == selection["plan_sha256"]
    text = (out / "ivv_holdings_source.csv").read_text(encoding="utf-8-sig")
    header = next(i for i, line in enumerate(text.splitlines()) if line.startswith("Ticker,Name,"))
    holdings = pd.read_csv(io.StringIO(text), skiprows=header, dtype=str)
    holdings = holdings.loc[holdings["Asset Class"].eq("Equity")].copy()
    holdings["symbol"] = holdings.Ticker.str.replace(" ", ".", regex=False)
    holdings["value"] = holdings["Market Value"].str.replace(",", "", regex=False).astype(float)
    with gzip.open(out / "alpaca_active_assets.json.gz", "rt") as stream:
        assets = {r["symbol"]: r for r in json.load(stream)}
    holdings = holdings.loc[holdings.symbol.map(lambda s: s in assets and assets[s]["status"] == "active" and assets[s]["tradable"] and assets[s]["class"] == "us_equity")]
    expected = holdings.sort_values(["value", "symbol"], ascending=[False, True]).head(200).symbol.tolist()
    assert set(expected) == set(equities)
    calendar = sorted(r["date"] for r in json.loads((out / "calendar.json").read_text()))
    session_index = pd.DatetimeIndex(calendar, name="date")
    checks = {"top_200_selection_independently_reproduced": True,
              "universe_and_collection_plan_hashes_match": True}
    modes = {}; pages_audit = {}
    for mode in ["raw", "all"]:
        bars = pd.read_csv(out / f"bars_{mode}.csv", parse_dates=["date"])
        assert not bars.duplicated(["symbol", "date"]).any()
        assert set(bars.symbol) == set(symbols) and bars.date.isin(session_index).all()
        values = bars[["o", "h", "l", "c", "v"]].to_numpy()
        assert np.isfinite(values).all() and (values[:, :4] > 0).all() and (values[:, 4] >= 0).all()
        assert (bars.l <= bars[["o", "c"]].min(axis=1)).all()
        assert (bars.h >= bars[["o", "c"]].max(axis=1)).all()
        close = pd.read_csv(out / f"close_{mode}.csv", index_col="date", parse_dates=True)
        pivot = bars.pivot(index="date", columns="symbol", values="c").reindex(index=session_index, columns=symbols)
        assert close.index.equals(session_index)
        assert np.allclose(close[symbols], pivot, equal_nan=True)
        pages = sorted(out.glob(f"response_{mode}_*.json.gz"))
        count, previous_token = 0, None
        response_keys = set()
        for i, path in enumerate(pages):
            with gzip.open(path, "rt") as stream:
                page = json.load(stream)
            params, response = page["params"], page["response"]
            assert params.get("page_token") == previous_token
            assert params["adjustment"] == mode and params["feed"] == "sip" and params["timeframe"] == "1Day"
            assert params["asof"] == plan["symbol_asof"] and set(params["symbols"].split(",")) == set(symbols)
            for symbol, rows in (response.get("bars") or {}).items():
                for bar in rows:
                    timestamp = pd.Timestamp(bar["t"])
                    day = timestamp.tz_convert("America/New_York").strftime("%Y-%m-%d")
                    key = (symbol, day)
                    assert key not in response_keys
                    response_keys.add(key)
                count += len(rows)
            previous_token = response.get("next_page_token")
            assert previous_token or i == len(pages)-1
        assert previous_token is None and count == len(bars)
        assert response_keys == set(zip(bars.symbol, bars.date.dt.strftime("%Y-%m-%d")))
        pages_audit[mode] = {"pages": len(pages), "bars": count}
        modes[mode] = (bars, close)
    raw, close_raw = modes["raw"]
    adjusted, close = modes["all"]
    assert set(zip(raw.symbol, raw.date)) == set(zip(adjusted.symbol, adjusted.date))
    simple = pd.read_csv(out / "returns_simple.csv", index_col="date", parse_dates=True)
    logs = pd.read_csv(out / "returns_log.csv", index_col="date", parse_dates=True)
    expected_simple = close / close.shift(1) - 1
    expected_log = np.log(close / close.shift(1))
    assert simple.index.equals(session_index) and logs.index.equals(session_index)
    assert simple.notna().equals(expected_simple.notna()) and logs.notna().equals(expected_log.notna())
    assert np.allclose(simple, expected_simple, equal_nan=True, atol=1e-13)
    assert np.allclose(logs, expected_log, equal_nan=True, atol=1e-13)
    # Verify each contiguous segment's endpoint identity independently via logs.
    for symbol in symbols:
        present = close[symbol].notna()
        segment = (~present).cumsum()
        for _, group in close.loc[present, symbol].groupby(segment.loc[present]):
            if len(group) > 1:
                measured = logs.loc[group.index[1:], symbol].sum()
                assert np.isclose(measured, np.log(group.iloc[-1] / group.iloc[0]), atol=1e-10)
    coverage = pd.read_csv(out / "coverage.csv").set_index("symbol")
    for symbol in symbols:
        observed = close[symbol].dropna()
        missing = close[symbol].isna()
        if len(observed):
            first, last = observed.index[[0, -1]]
            leading = int(missing.loc[missing.index < first].sum())
            trailing = int(missing.loc[missing.index > last].sum())
            internal = int(missing.loc[(missing.index > first) & (missing.index < last)].sum())
            assert coverage.loc[symbol, "first_date"] == first.strftime("%Y-%m-%d")
            assert coverage.loc[symbol, "last_date"] == last.strftime("%Y-%m-%d")
        else:
            leading, trailing, internal = len(close), 0, 0
        assert coverage.loc[symbol, "bars"] == len(observed)
        for name, value in [("leading_missing", leading), ("trailing_missing", trailing), ("internal_missing", internal)]:
            assert coverage.loc[symbol, name] == value
    original = out.parent / "equity_daily_30_2016_2026-10-27"
    for name, digest in manifest["original_dataset_sha256_before"].items():
        assert hashlib.sha256((original / name).read_bytes()).hexdigest() == digest
    legacy = pd.read_csv(original / "universe.csv").query("role == 'equity'").symbol
    assert set(legacy) <= set(equities)
    flags = (simple.abs() > .25).stack()
    assert int(flags.sum()) == len(json.loads((out / "large_adjusted_return_flags.json").read_text()))
    # Metadata only: daily close times daily volume is a proxy, not exact trade dollars.
    recent = raw.loc[raw.date.isin(session_index[-60:]) & raw.symbol.isin(equities)].copy()
    recent["close_times_volume_usd"] = recent.c * recent.v
    liquidity = recent.groupby("symbol").agg(observed_sessions=("date", "size"),
        median_close_times_volume_usd=("close_times_volume_usd", "median"), median_raw_close=("c", "median"))
    liquidity.to_csv(out / "recent_60_session_liquidity_proxy.csv")
    sector = universe.loc[universe.role.eq("equity")].groupby("sector_snapshot").size().sort_values()
    sector.rename("stocks").to_csv(out / "sector_counts.csv")
    available = simple[equities].notna().sum(axis=1)
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), layout="constrained")
    axes[0].plot(available.index, available, color="#277da1", lw=1.4)
    axes[0].set_ylim(0, 210); axes[0].set_title("Observed adjacent-session returns")
    axes[0].set_ylabel("Equities with a usable daily return (of 200)")
    axes[0].set_xlabel("Date; no missing-value filling")
    axes[1].barh(sector.index, sector.values, color="#43aa8b")
    axes[1].set_xlabel("Selected stocks"); axes[1].set_title("Provider sector snapshot: October 27, 2026")
    fig.suptitle("Expanded dataset coverage | current-size-selected survivor sample\nCoverage is not historical eligibility; share classes are separate securities")
    fig.savefig(out / "coverage_and_sectors.png", dpi=160); plt.close(fig)
    checks.update(full_pagination_and_response_row_keys_verified=True,
        raw_adjusted_calendar_and_close_matrices_verified=True,
        positive_finite_ordered_ohlcv=True, all_returns_match_adjacent_observed_closes=True,
        contiguous_log_return_compounding=True, no_missing_history_imputation=True,
        all_coverage_counts_reproduced=True, all_original_30_retained=True,
        original_dataset_hashes_unchanged=True, large_return_flags_reproduced=True)
    report = {"checks": checks, "pages": pages_audit, "equities": len(equities), "sessions": len(calendar),
        "fully_observed_equities": int((coverage.loc[equities, "bars"] == len(calendar)).sum()),
        "equities_with_leading_missing": int((coverage.loc[equities, "leading_missing"] > 0).sum()),
        "equities_with_internal_missing": int((coverage.loc[equities, "internal_missing"] > 0).sum()),
        "internal_missing_equity_sessions": int(coverage.loc[equities, "internal_missing"].sum()),
        "equities_with_trailing_missing": int((coverage.loc[equities, "trailing_missing"] > 0).sum()),
        "valid_return_equities_first_observation": int(available.iloc[1]),
        "valid_return_equities_last_observation": int(available.iloc[-1]),
        "sectors": {str(k): int(v) for k, v in sector.items()},
        "price_adjustment_caveat": "all-adjusted vendor prices, not an audited action ledger",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out / "independent_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
