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

    vix = pd.read_csv(VIX_FILE, index_col="date", parse_dates=True)["close"].reindex(dates)

    return Panel(
        dates=dates, symbols=symbols,
        returns=returns[symbols].to_numpy(), market=returns["SPY"].to_numpy(),
        open_raw=prices["raw", "o"], close_raw=prices["raw", "c"],
        open_adj=prices["all", "o"], close_adj=prices["all", "c"],
        sectors=universe["sector_snapshot"].to_numpy(), vix=vix.to_numpy(),
    )
