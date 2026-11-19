# BTC: the shape of the price path

The second of the project's three studies. It asks whether the *shape* of BTC's recent price path, measured with persistent homology, helps forecast volatility or returns. The order-book work that uses BTC data lives in [liquidity/](../liquidity/README.md).

- **Results: [RESULTS.md](RESULTS.md).** Shape features help a volatility forecast by about 1%, but only because they roughly measure how fat-tailed the last day was. Plain tail measures do twice as well, and with them included shape adds nothing. Return direction was not forecastable.
- **Data: [DATA.md](DATA.md)** covers every BTC dataset in the project, where it is, and how it was checked.
- **Code:** `studies/b01_shape_vs_volatility.py`, run with the `tda` Python. Results and figures are in `results/b01_shape_vs_volatility/`.

`ACTIVE_CAPTURE.json` points to the November 5 recording and is read by two `market_data/` scripts; keep it. Earlier pilots (October feature tests, the November 5 next-minute return test) and the old research log are in `_archive/btc_2026-11-18/` on this machine.
