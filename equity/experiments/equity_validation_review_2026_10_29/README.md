# Equity validation and reporting review — October 29, 2026

Read [EQUITY_VALIDATION.md](../../EQUITY_VALIDATION.md) for the conclusions, aligned tables and graphs. This folder reconciles existing research; it contains no newly tuned strategy or revised historical returns.

- [Eight audit reruns](audit_reruns.json): isolated mirrors preserve original result files. [Runner](../revalidate_equity_research.py).
- [Legacy reconstruction](legacy_checks.json): original thirty-stock holdings, PC sensitivities, peer-pilot returns, hierarchy cuts, descriptive PCA and gross metrics. [Source](check_legacy_results.py).
- [Comparison checks](ledger_validation.json): shared return identities, reproduced performance metrics, forecast losses and notebook inventory. [Ledger/report generator](build_comparison_ledger.py).
- [Return metrics](canonical_return_metrics.csv): strategy, universe, fit window, period, dates, observations, gross return, realized risk and activity. Five explicitly named scopes; no comparison should silently switch them.
- [Risk-forecast metrics](canonical_risk_forecast_metrics.csv): predictive loss, kept separate from returns and realized portfolio volatility.
- [Common-calendar daily series](common_calendar_returns_and_equity.csv): same April 22, 2019–October 27, 2026 dates and starting capital for all current gates, with all flat days included and no 2024 reset.
- [Notebook inventory](notebook_output_inventory.csv): eleven executed notebooks, no saved errors; all fifty embedded PNGs match saved project images.

All reporting remains gross/pre-fee with zero cash-interest return. Existing datasets, source results and notebooks are preserved. Documentation changes make periods, policies and risk definitions explicit.
