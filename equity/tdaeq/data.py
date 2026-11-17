"""Load the daily equity panel.

Everything is aligned to one list of trading dates. Row t of every array is
the same day. Stocks that listed after 2016 have NaN before their first day.
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
CURRENT = "equity_daily_expanded_2016_2026-11-09"
OLD_VINTAGE = "equity_daily_expanded_2016_2026-10-27"
VIX_FILE = REPO / "market_data/datasets/mean_reversion_context_2026-11-04/vix_daily.csv"

# Explore on dates before SPLIT, confirm once on dates from SPLIT onward.
SPLIT = pd.Timestamp("2024-01-01")
# A stock may be used on day t only if it has this many returns before t.
MIN_HISTORY = 272


@dataclass
class Panel:
    dates: pd.DatetimeIndex
    symbols: list
    returns: np.ndarray      # days x stocks, daily log returns (adjusted close to close)
    market: np.ndarray       # days, SPY daily log return
    market_open: np.ndarray  # days, SPY adjusted open
    market_close: np.ndarray # days, SPY adjusted close
    open_raw: np.ndarray     # days x stocks, unadjusted open
    close_raw: np.ndarray    # days x stocks, unadjusted close
    open_adj: np.ndarray     # days x stocks, split/dividend adjusted open
    close_adj: np.ndarray    # days x stocks, split/dividend adjusted close
    sectors: np.ndarray      # stocks, sector name (snapshot taken Oct 2026)
    vix: np.ndarray          # days, VIX close on that day (NaN if not available)

    def eligible(self, t, history=MIN_HISTORY):
        """Columns of the stocks that have a full `history` days before day t."""
        return np.flatnonzero(np.isfinite(self.returns[t - history:t]).all(axis=0))

    def is_later(self, t):
        return self.dates[t] >= SPLIT


def dataset_folder(vintage):
    for base in (REPO / "market_data/datasets", REPO / "_archive/data"):
        if (base / vintage).exists():
            return base / vintage
    raise FileNotFoundError(vintage)


def load_panel(vintage=CURRENT):
    folder = dataset_folder(vintage)
    universe = pd.read_csv(folder / "universe.csv").query("role == 'equity'").set_index("symbol")
    symbols = universe.index.tolist()
    returns = pd.read_csv(folder / "returns_log.csv", index_col="date", parse_dates=True).iloc[1:]
    dates = returns.index

    prices = {}
    for mode in ("raw", "all"):
        bars = pd.read_csv(folder / f"bars_{mode}.csv", usecols=["symbol", "date", "o", "c"],
                           parse_dates=["date"])
        for field in ("o", "c"):
            table = bars.pivot(index="date", columns="symbol", values=field)
            prices[mode, field] = table.reindex(index=dates, columns=symbols).to_numpy()
            if mode == "all":
                prices["spy", field] = table["SPY"].reindex(dates).to_numpy()

    vix = pd.read_csv(VIX_FILE, index_col="date", parse_dates=True)["close"].reindex(dates)

    return Panel(
        dates=dates, symbols=symbols,
        returns=returns[symbols].to_numpy(), market=returns["SPY"].to_numpy(),
        market_open=prices["spy", "o"], market_close=prices["spy", "c"],
        open_raw=prices["raw", "o"], close_raw=prices["raw", "c"],
        open_adj=prices["all", "o"], close_adj=prices["all", "c"],
        sectors=universe["sector_snapshot"].to_numpy(), vix=vix.to_numpy(),
    )


def load_bar_fields(panel, fields=("h", "l", "v", "vw"), symbols=None, vintage=CURRENT):
    """Extra daily fields, split/dividend adjusted, each days x stocks and aligned to the panel.

    h = high, l = low, v = shares traded, vw = volume-weighted average price.
    Pass symbols=["SPY"] to get the same fields for the market (one column).
    """
    bars = pd.read_csv(dataset_folder(vintage) / "bars_all.csv", usecols=["symbol", "date", *fields],
                       parse_dates=["date"])
    return {field: bars.pivot(index="date", columns="symbol", values=field)
            .reindex(index=panel.dates, columns=symbols or panel.symbols).to_numpy() for field in fields}


INTRADAY = "equity_intraday_2017_2026-11-09"


def load_intraday(panel, vintage=INTRADAY):
    """Prices around the close, each days x stocks and aligned to the panel (NaN where missing).

    Times are counted back from that day's close (16:00, or 13:00 on a half day):

      price_30, price_20, price_10   last traded price 30, 20 and 10 minutes before the close
      vwap_30, vwap_20, vwap_10      average traded price from the open up to that time
      last_trade                     last traded price in regular hours, just before the closing auction

    "spy_..." holds the same for SPY (one value per day). Prices are unadjusted,
    so only compare them with other prices from the same day (e.g. panel.close_raw).
    Built from the raw files by market_data/download_equity_intraday.py and cached.

    A stock-day is left missing (NaN) unless every bar is present: all 30-minute
    bars from the open to 30 minutes before the close, and all three 10-minute
    bars after that. About 0.2% of stock-days fail, mostly on six days when the
    data provider's feed has holes in the last half hour. Filling those from an
    earlier price would make a stale price look like a late-day move.
    """
    import gzip
    import json
    from zoneinfo import ZoneInfo

    folder = dataset_folder(vintage)
    files = sorted((folder / "raw" / "last_half_hour").glob("*.json.gz"))
    cache = folder / "compiled_v2.npz"                    # v2: incomplete stock-days are missing
    if cache.exists():
        saved = np.load(cache)
        if int(saved["files"]) == len(files):
            return {key: saved[key] for key in saved.files if key != "files"}
    names = ["price_30", "price_20", "price_10", "vwap_30", "vwap_20", "vwap_10", "last_trade"]
    column = {symbol: i for i, symbol in enumerate(panel.symbols)}
    row = {str(day.date()): t for t, day in enumerate(panel.dates)}
    out = {name: np.full(panel.returns.shape, np.nan) for name in names}
    out.update({f"spy_{name}": np.full(len(panel.dates), np.nan) for name in names})
    for path in files:
        day = path.name[:10]
        early_path = folder / "raw" / "half_hours" / path.name
        if day not in row or not early_path.exists():
            continue
        late, early = json.load(gzip.open(path)), json.load(gzip.open(early_path))
        close = pd.Timestamp(f"{day} {late['close']}", tz=ZoneInfo("America/New_York")).tz_convert("UTC")
        open_ = pd.Timestamp(f"{day} {late['open']}", tz=ZoneInfo("America/New_York")).tz_convert("UTC")
        expected = round((close - open_).total_seconds() / 1800) - 1      # 30-minute bars before the last half hour
        for symbol, bars in late["bars"].items():
            before = early["bars"].get(symbol, [])
            if not before or (symbol not in column and symbol != "SPY"):
                continue
            regular = [bar for bar in bars if pd.Timestamp(bar["t"]) < close]
            if len(before) != expected or len(regular) != 3:
                continue                                   # incomplete: leave missing
            value = sum(bar["v"] * bar["vw"] for bar in before)
            shares = sum(bar["v"] for bar in before)
            price = before[-1]["c"]
            got = {"price_30": price, "vwap_30": value / shares}
            for bar in bars:
                minutes = round((pd.Timestamp(bar["t"]) - close).total_seconds() / 60)
                if minutes >= 0:
                    break                                  # the closing auction and after-hours trades
                value, shares, price = value + bar["v"] * bar["vw"], shares + bar["v"], bar["c"]
                if minutes == -30:
                    got.update(price_20=price, vwap_20=value / shares)
                elif minutes == -20:
                    got.update(price_10=price, vwap_10=value / shares)
            got["last_trade"] = price
            for name, number in got.items():
                if symbol == "SPY":
                    out[f"spy_{name}"][row[day]] = number
                else:
                    out[name][row[day], column[symbol]] = number
    np.savez_compressed(cache, files=len(files), **out)
    return out
