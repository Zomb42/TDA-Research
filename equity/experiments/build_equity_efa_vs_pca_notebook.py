"""Build and execute the matched EFA/PCA research notebook without kernel sockets."""
from pathlib import Path
import os
import platform
import nbformat as nb
from IPython.core.interactiveshell import InteractiveShell
from IPython.utils.capture import capture_output
from traitlets.config import Config

ROOT = Path(__file__).resolve().parents[1]


def main():
    cells = [
        nb.v4.new_markdown_cell('''# EFA versus PCA: does changing the factor estimate help reversal?

October 29, 2026. **Result: no material improvement established.** EFA's later gross CAGR is 3.54% versus PCA's 3.37%; the paired daily mean difference is +0.065 bps, interval [−0.104,+0.263]. Future unexplained correlations and factor stability are almost unchanged. Reliable short-term reversal remains unconfirmed.

[Full intuitive findings](experiments/equity_efa_vs_pca/README.md) · [fixed specification](experiments/equity_efa_vs_pca/specification.json) · [source](experiments/equity_efa_vs_pca.py) · [running log](EQUITY_RESEARCH_LOG.md).

Same explicit SPY beta plus three additional factors, 120-session fit, signal, weighting, timing, and unit gross exposure. No TDA, gate, fees, factor-count search, or new download. These survivor stocks and historical dates have already been examined.'''),
        nb.v4.new_code_cell('''from pathlib import Path
import json
import numpy as np
import pandas as pd
from IPython.display import display, Image
cwd=Path.cwd()
candidates=[cwd,cwd/"TDA_Research",cwd/"Senior-Fall"/"TDA_Research",*cwd.parents]
project=next(p for p in candidates if (p/"START_HERE.md").is_file() and (p/"equity").is_dir())
out=project/"equity"/"experiments"/"equity_efa_vs_pca"
result=json.loads((out/"summary.json").read_text())
audit=json.loads((out/"independent_audit.json").read_text())
performance=pd.read_csv(out/"gross_performance.csv")
paired=pd.read_csv(out/"paired_comparisons.csv")
horizon=pd.read_csv(out/"horizon_summary.csv")
structural=pd.read_csv(out/"structural_summary.csv")
fitting=pd.read_csv(out/"fit_diagnostics.csv",parse_dates=["signal_date"])
assert all(result["checks"].values()) and all(audit["checks"].values())
print("Daily formations:",result["daily_dates"],"| periods:",result["daily_dates_by_period"])
print("Structural future blocks:",result["structural_blocks_by_period"])
print("EFA convergence iterations:",result["EFA_iterations"])
print("Local scikit-learn:",result["sklearn_version"])'''),
        nb.v4.new_markdown_cell('''## 1. What changes between PCA and EFA?

PCA finds directions capturing observed variation. EFA fits a covariance model with common latent factors plus different stock-specific noise variances. It might distinguish common and individual movement differently. Neither approach makes the residual mean-reverting or discovers named economic causes automatically.

Both use the same daily admitted stocks, requiring 272 complete prior returns. Both fit SPY and standardize the previous 120 residual observations. PCA takes three leading directions; EFA estimates three loadings plus a separate unique variance for each stock. Exposure rows are multiplied by the residual standard deviations to restore raw-return units, then combined with dollar and SPY-beta columns.

The signal remains that day's adjusted close-close log return. We use the same cross-sectional WLS and inverse prior **total-return** variance weights. Holdings are **minus W times the WLS residual**, normalized to unit gross. EFA unique variances do not replace W, and EFA posterior scores do not become a different signal.

Positions remain dollar neutral and estimated-SPY/three-factor neutral at formation, enter next raw daily-bar open, and exit that close. Coefficient labels/signs are arbitrary; rotating a fixed factor span does not change these constraints. Exact settings are frozen, not chosen by profit.'''),
        nb.v4.new_code_cell('''print(result["configuration"]["EFA"])
print("Unique-variance minimum across all fits:",fitting.unique_variance_min.min())
print("Unique-variance maximum across all fits:",fitting.unique_variance_max.max())
period=np.where(fitting.signal_date.ge("2024-01-01"),"later","development")
display(fitting.assign(period=period).groupby("period")["PCA_EFA_raw_subspace_overlap"].agg(["mean","median","min","max"]).round(4))
print("Subspace overlap 1 means identical spans, even if factors are rotated or renamed.")'''),
        nb.v4.new_markdown_cell('''## 2. Primary trading comparison: small difference, unresolved advantage

Every value is **gross/pre-fee**. Later means January 2024–October 27, 2026, with the same 708 executions as the original PCA run. The new PCA positions and point returns reproduce that run. Sixty-date paired block resamples acknowledge serial dependence; changing the seed changes interval endpoints, not the saved return series.

EFA later mean is +1.408 versus PCA +1.343 bps/day. The paired increment is only **+0.065 bps/day**, approximate95 interval **[−0.104,+0.263]**. CAGR changes from 3.37% to 3.54%, Sharpe from 0.89 to 0.93. Earlier, EFA is slightly worse. Both standalone means and both primary paired differences have intervals spanning zero.

The curves below start from the same capital separately in each period. They are the original daily portfolio without a learned on/off gate. A favorable point rank does not establish EFA superiority.'''),
        nb.v4.new_code_cell('''table=performance.copy()
table["CAGR_percent"]=table.gross_CAGR*100
display(table[["period","model","days","mean_daily_bps","mean_low","mean_high","CAGR_percent","sharpe_vs_zero","mean_effective_breadth"]].round(4))
display(paired.loc[paired.role.eq("primary"),["period","difference","point95_low","point95_high"]].round(5))
display(Image(filename=str(out/"01_gross_profit.png")))'''),
        nb.v4.new_markdown_cell('''## 3. Does EFA remove more future common movement or produce more stable factors?

Every twenty formation dates, freeze the past exposures and weights, then decompose the next twenty close-close return vectors by the same WLS. The average absolute residual correlation measures remaining pairwise co-movement. Future common-return coefficients are an **ex-post diagnostic**, never inputs to the trade. Those are WLS residuals, not directly EFA posterior unique errors.

For stability, compare the current three-column raw loading space with its previous diagnostic block on common stocks. The overlap ranges from zero to one and ignores arbitrary factor rotations/signs. Twenty future observations make individual correlations noisy, and overlapping estimation windows limit independent information.

Later absolute correlation is about **0.20614 PCA versus 0.20646 EFA**. Stability is **0.8765 versus 0.8802**. These differences are small; simultaneous paired intervals for both metrics span zero. Earlier EFA stability is slightly worse. Neither measure establishes a structural improvement or true economic factor identity.'''),
        nb.v4.new_code_cell('''display(structural.round(6))
display(paired.loc[paired.metric.isin(["future_abs_corr","subspace_stability"]),
    ["period","metric","count","difference","sim95_low","sim95_high"]].round(6))
display(Image(filename=str(out/"02_paired_comparisons.png")))
display(Image(filename=str(out/"04_factor_diagnostics.png")))'''),
        nb.v4.new_markdown_cell('''## 4. Do the residual moves reverse over 1, 5, or 20 sessions?

These are frozen initial sleeves, not twenty overlapping funded portfolios. All horizons use the same complete twenty-session event dates: 1,719 earlier and 689 later. Entry/exit are adjusted open/close marks. This differs from the full raw daily execution calendar, including omission of nineteen later tail dates. A different one-day event mean is not a contradiction.

The response slope compares the current residual with subsequent stock returns using the same weights. **Negative means reversal direction; positive means continuation direction.** All standalone slope and event-mean intervals span zero in both periods.

EFA's later event means are +0.968, +0.236, and −2.946 bps for 1/5/20 sessions. Its twenty-session mean is less negative than PCA's. Some twenty-session paired pointwise intervals exclude zero, but the declared three-horizon simultaneous bands do not. EFA's own twenty-session mean remains negative. This does not establish profitable mean reversion.'''),
        nb.v4.new_code_cell('''display(horizon.round(6))
display(paired.loc[paired.metric.str.startswith("event"),
    ["period","metric","difference","point95_low","point95_high","sim95_low","sim95_high"]].round(6))
display(Image(filename=str(out/"03_horizon_response.png")))'''),
        nb.v4.new_markdown_cell('''## 5. Checks and decision

All 2,446 EFA fits converged in 6–77 iterations. Their unique variances remain above the numerical floor. The independent audit reconstructs every portfolio and Gaussian training likelihood, refits thirteen windows, checks an independent EM update, and reconciles daily/event ledgers, future correlations, stability, metrics and uncertainty bands. The old PCA positions and results remain intact. These checks address implementation correctness, not a global optimum or the truth of the factor model.

The median later cross-method loading-space overlap is 0.970: the fitted three-dimensional spaces are usually closely aligned. That is consistent with a small implementation change; it does not give the factors an economic interpretation.

**Decision:** keep PCA as the existing baseline and EFA as a completed matched alternative. EFA does not materially alter the conclusion that short-term residual reversal is unconfirmed. No TDA gate, rotation/count search, or other experiment is inferred from the slightly higher later CAGR. The survivor universe, short rolling sample, already examined dates, fixed factor count, and noisy secondary diagnostics remain limitations.'''),
        nb.v4.new_code_cell('''for name, passed in audit["checks"].items():
    print(name,passed)
print("Daily formations independently checked:",audit["daily_formations_checked"])
print("Independent EFA refits:",audit["independent_EFA_refits"])
print("Maximum holding reconstruction difference:",audit["max_position_error"])
print("Maximum Gaussian loglikelihood difference:",audit["max_EFA_loglikelihood_error"])
assert all(audit["checks"].values())'''),
    ]
    notebook=nb.v4.new_notebook(cells=cells,metadata={"kernelspec":{"display_name":"TDA (conda)","language":"python","name":"tda"},
        "language_info":{"name":"python","version":platform.python_version()}})
    os.chdir(ROOT); cfg=Config(); cfg.HistoryManager.hist_file=":memory:"
    shell=InteractiveShell.instance(config=cfg)
    for cell in notebook.cells:
        if cell.cell_type!="code": continue
        count=shell.execution_count
        with capture_output() as captured: result=shell.run_cell(cell.source,store_history=True)
        if result.error_before_exec or result.error_in_exec: raise RuntimeError(str(result.error_before_exec or result.error_in_exec))
        cell.execution_count=count; cell.outputs=[]
        for name,text in [("stdout",captured.stdout),("stderr",captured.stderr)]:
            if text: cell.outputs.append(nb.v4.new_output("stream",name=name,text=text))
        for output in captured.outputs: cell.outputs.append(nb.v4.new_output("display_data",data=output.data,metadata=output.metadata))
    nb.validate(notebook); nb.write(notebook,ROOT/"equity_efa_vs_pca.ipynb")
    print("Executed",sum(c.cell_type=="code" for c in notebook.cells),"cells; embedded",
        sum("image/png" in o.get("data",{}) for c in notebook.cells if c.cell_type=="code" for o in c.outputs),"figures")


if __name__ == "__main__": main()
