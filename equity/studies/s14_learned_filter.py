"""H2. The paper's Remark 3.2: learn the curve that the barcode is taken of.

Study 13 took the barcode of the price path itself. Zeng et al. (2021, Remark 3.2)
suggest learning the function that is swept instead. Here a small network reads
each stock's day (5-minute price path and 5-minute volume, open to 3:40 pm),
outputs one curve, and the 1D-sweep barcode of that curve (valleys and peaks)
feeds the forecast. The barcode's bar lengths are differences of two entries of
the curve (topology.path_pairs), so the network can be trained through them.

Three models, same inputs, same training, same target (the move from 3:50 pm to
the next open against peers, as a rank within the day):

  Learned curve + barcode     curve = price path + learned correction; 8 soft
                              "bumps" per side turn the bars into numbers
  Learned curve, no barcode   same curve, summarized by plain numbers instead
                              (mean, spread, highest, lowest, last, last hour)
  Plain features only         the 11 plain path measures of study 13

All three also see the 11 plain measures. Trained on earlier years, scored on
the next two: 2021-22, 2023-24, 2025-26. Two random starts averaged.

    conda run -n tda python equity/studies/s14_learned_filter.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import torch
from torch import nn

from s04_peer_reversal_book import exposures_for
from s08_path_shape import centred_ranks
from s11_late_day_characterize import tables
from s13_intraday_barcode import PLAIN, prepare
from tdaeq import data, evaluate, plots, portfolio, signals, topology

STUDY = "s14_learned_filter"
BLOCKS = [(2021, 2022), (2023, 2024), (2025, 2026)]
MODELS = ["Learned curve + barcode", "Learned curve, no barcode", "Plain features only"]
torch.set_num_threads(8)


class Model(nn.Module):
    def __init__(self, kind, n_plain, bumps=8):
        super().__init__()
        self.kind = kind
        self.conv = nn.Sequential(nn.Conv1d(2, 8, 5, padding=2), nn.Tanh(), nn.Conv1d(8, 1, 1))
        nn.init.zeros_(self.conv[2].weight); nn.init.zeros_(self.conv[2].bias)     # starts as the plain price path
        if kind == "Learned curve + barcode":
            self.centres = nn.Parameter(torch.stack([torch.linspace(-1, 1, bumps), torch.linspace(0.05, 0.8, bumps)], 1)
                                        .repeat(2, 1).reshape(2, bumps, 2))
            self.width = nn.Parameter(torch.full((2, bumps, 2), -1.0))
            n_shape = 2 * bumps + 2
        elif kind == "Learned curve, no barcode":
            n_shape = 6
        else:
            n_shape = 0
        self.head = nn.Linear(n_plain + n_shape, 1)

    def curve(self, x):
        return x[:, 0] + self.conv(x)[:, 0]

    def barcode_features(self, f):
        feats = []
        for side, g in enumerate((f, -f)):
            g_end = g - g[:, -1:]
            pairs = [topology.path_pairs(row) for row in g_end.detach().numpy()]
            width = max(1, max(len(p) for p in pairs))
            birth = torch.zeros(len(pairs), width, dtype=torch.long)
            death = torch.zeros(len(pairs), width, dtype=torch.long)
            mask = torch.zeros(len(pairs), width)
            for k, p in enumerate(pairs):
                if p:
                    birth[k, :len(p)] = torch.tensor([b for b, _ in p])
                    death[k, :len(p)] = torch.tensor([d for _, d in p])
                    mask[k, :len(p)] = 1
            level = torch.gather(g_end, 1, birth)
            length = (torch.gather(g_end, 1, death) - level) * mask
            c, w = self.centres[side], torch.exp(self.width[side])
            bump = torch.exp(-((level[:, :, None] - c[None, None, :, 0]) / w[None, None, :, 0]) ** 2
                             - ((length[:, :, None] - c[None, None, :, 1]) / w[None, None, :, 1]) ** 2)
            feats.append((bump * length[:, :, None] * mask[:, :, None]).sum(1))
            feats.append(length.sum(1, keepdim=True))
        return torch.cat(feats, 1)

    def forward(self, x, plain):
        if self.kind == "Plain features only":
            return self.head(plain)[:, 0]
        f = self.curve(x)
        if self.kind == "Learned curve + barcode":
            shape = self.barcode_features(f)
        else:
            shape = torch.stack([f.mean(1), f.std(1), f.max(1).values, f.min(1).values, f[:, -1] - f[:, 0], f[:, -1] - f[:, -13]], 1)
        return self.head(torch.cat([plain, shape], 1))[:, 0]


def fit_predict(kind, x, plain, y, train, test, seed, epochs=6, batch=2048):
    torch.manual_seed(seed)
    model = Model(kind, plain.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)
    idx = np.flatnonzero(train)
    rng = np.random.default_rng(seed)
    for _ in range(epochs):
        rng.shuffle(idx)
        for start in range(0, len(idx), batch):
            b = idx[start:start + batch]
            loss = ((model(x[b], plain[b]) - y[b]) ** 2).mean()
            opt.zero_grad(); loss.backward(); opt.step()
    with torch.no_grad():
        t = np.flatnonzero(test)
        return np.concatenate([model(x[t[s:s + 8192]], plain[t[s:s + 8192]]).numpy() for s in range(0, len(t), 8192)])


def main():
    np.seterr(invalid="ignore", divide="ignore")
    panel = data.load_panel()
    state = signals.build_state(panel)
    intraday, outcomes, _, sigma = tables(panel, state)
    outcome = outcomes["3:50 pm to next open"]
    d = prepare(panel, state, intraday, outcome, sigma)
    t_all, i_all = d["t"], d["i"]
    target = outcome[t_all, i_all]
    peer_target = np.full(len(t_all), np.nan)
    for t in np.unique(t_all):
        k = np.flatnonzero(t_all == t)
        peer_target[k] = signals.minus_group_mean(target[k], state.group[t, i_all[k]])
    use = np.flatnonzero(np.isfinite(peer_target) & np.isfinite(d["signal_vs_peers"]))
    use = use[np.argsort(t_all[use], kind="stable")]
    tt, ii, yy = t_all[use], i_all[use], peer_target[use]
    days = np.unique(tt)
    plain = np.vstack([centred_ranks(np.column_stack([d[k][use][tt == t] for k in PLAIN])) for t in days])
    y_rank = np.concatenate([centred_ranks(yy[tt == t][:, None])[:, 0] for t in days])
    path = d["path"][use]
    volume = np.log(d["volume"][use] / d["volume"][use].mean(1, keepdims=True))
    x = np.stack([path, np.hstack([np.zeros((len(use), 1)), volume])], 1)
    x = np.clip(x, -10, 10)
    year = panel.dates.year.to_numpy()[tt]
    X, P, Y = (torch.tensor(a, dtype=torch.float32) for a in (x, plain, y_rank))
    print(f"{len(use):,} stock-days, {len(days)} days")

    preds = {m: np.full(len(use), np.nan) for m in MODELS}
    for first, last in BLOCKS:
        train, test = year < first, (year >= first) & (year <= last)
        for m in MODELS:
            preds[m][test] = np.mean([fit_predict(m, X, P, Y, train, test, seed) for seed in (0, 1)], axis=0)
            print(f"  {first}-{last} {m}: done", flush=True)
    preds["Rule: bet against the signal vs peers"] = -plain[:, PLAIN.index("signal_vs_peers")]

    test_days = np.unique(tt[year >= BLOCKS[0][0]])
    later = panel.dates[test_days] >= data.SPLIT
    rows, book = [], {}
    for name, p in preds.items():
        ic = np.array([evaluate.rank_ic(p[tt == t], yy[tt == t]) for t in test_days])
        r = []
        for t in test_days:
            k = np.flatnonzero(tt == t)
            bet = np.full(panel.returns.shape[1], np.nan)
            bet[ii[k]] = -p[k]
            stocks = np.flatnonzero(np.isfinite(bet) & np.isfinite(sigma[t]))
            stocks, columns = exposures_for("TDA peer groups", state, t, stocks)
            h, _ = portfolio.neutral_book(bet[stocks], columns, 1 / sigma[t, stocks] ** 2)
            r.append(np.nansum(h * outcome[t, stocks]))
        book[name] = np.array(r)
        mean, low, high = evaluate.mean_ci(ic, block=5)
        s, sl, sh = evaluate.sharpe_ci(book[name], block=10)
        rows.append({"forecast": name, "days": len(test_days), "rank_correlation": mean, "ic_low": low, "ic_high": high,
                     "book_bps_per_day": book[name].mean() * 1e4, "book_sharpe": s, "sharpe_low": sl, "sharpe_high": sh})
    table = pd.DataFrame(rows)
    gains = []
    for a, b in (("Learned curve + barcode", "Learned curve, no barcode"), ("Learned curve + barcode", "Plain features only"),
                 ("Learned curve + barcode", "Rule: bet against the signal vs peers")):
        diff, low, high = evaluate.sharpe_difference_ci(book[a], book[b], block=10)
        gains.append({"comparison": f"{a} minus {b}", "book_sharpe_difference": diff, "low": low, "high": high})
    gains = pd.DataFrame(gains)
    out = plots.folder(STUDY)
    table.to_csv(out / "scores.csv", index=False)
    gains.to_csv(out / "differences.csv", index=False)
    pd.set_option("display.width", 250)
    print(table.round(4).to_string(index=False))
    print(gains.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
