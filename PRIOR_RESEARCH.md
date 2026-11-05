# What Previous TDA Research Has Found

Prepared October 14, 2026. A short synthesis of selected research reviewed for this project, with an emphasis on financial applications. Findings are author-reported; we have not independently replicated them. This is a selective overview, not a systematic review.

**Main finding:** TDA has helped researchers characterize meaningful structures and has improved some predictive models. In finance, the reviewed evidence supports describing market changes and investigating conditional forecasting gains. It does not establish a general advantage for return prediction or our proposed liquidity features.

## Findings beyond finance

These applications illustrate what a useful topological result can look like.

- **Neuroscience:** Gardner et al. (2022) used persistent cohomology to find toroidal structure in grid-cell population activity. Coordinates related to animal position, and the structure persisted across environments and behavioral states. This supported a particular model of how the neural network represents position. [Paper](https://www.nature.com/articles/s41586-021-04268-7)
- **Materials:** Hiraoka et al. (2016) used persistence diagrams to identify hierarchical rings and cavities in disordered atomic arrangements. Their silica-glass analysis connected ring structures to diffraction characteristics. The analytical payoff was an interpretation of physical organization. [Paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC4932931/)
- **Image analysis:** Hu et al. (2019) incorporated a topological loss into neural-network segmentation. They reported improvements on topology-relevant metrics, addressing errors such as broken connections that affect few pixels but substantially change structure. [Paper](https://arxiv.org/abs/1906.05404)

These successes concern identifiable scientific structures or task requirements. They provide reasons to investigate topology, while leaving its usefulness for a new financial question open.

## Findings in finance

### Market stress and changing relationships

**Gidea and Katz (2017 preprint, 2018 journal)** analyzed rolling clouds of four US index returns using persistent homology and landscape summaries. Those summaries changed around the dot-com and global financial crises. However, increasing-variance simulations also produced rising norms. The study supports sensitivity to changing market geometry, with scale as an important alternative explanation. Its selected historical episodes do not establish a calibrated prospective crash alarm. [Landscapes of Crashes](https://arxiv.org/abs/1703.04385)

**Gidea (2017)** studied rolling correlation networks of stocks and observed changes in persistence diagrams around the 2007–08 crisis. This demonstrates a way to summarize dependence across thresholds. Because the construction derives from correlations, its output remains a summary of the input correlation matrix. The study does not validate a peer-based return-reversal strategy. [Financial networks paper](https://arxiv.org/abs/1701.06081)

**Gidea et al. (2018 preprint, 2020 journal)** used delay embeddings, landscapes, and clustering to characterize cryptocurrency behavior around the 2017–18 boom and crash. Historical regime separation used price and return information alongside topology, so the results do not isolate a forecasting benefit from topology alone. [Cryptocurrency transitions paper](https://arxiv.org/abs/1809.00695)

### Forecasting and investment decisions

**Souto (2023)** added persistence-derived diagram-change features to realized-volatility forecasting models. Reported gains depended on model and period, with stronger evidence in neural models and turbulent periods. Some full-sample comparisons with simpler HAR models were not statistically significant. This is a useful precedent for testing incremental forecasting value against established models. [Full paper](https://www.newswise.com/pdf_docs/170055790161323_1-s2.0-S2405918823000235-main.pdf)

**de Jesus Jr. et al. (2025)** added delay-embedding persistence summaries to N-BEATS and compared alternative feature sets across 32 scenarios. TDA achieved the lowest reported MAE in 18 scenarios and RMSE in 19. These are positive, conditional forecasting results. They do not establish uniform superiority or trading profitability; a replication should audit preprocessing and chronological evaluation. [Forecasting paper](https://link.springer.com/article/10.1007/s00521-024-10787-x)

**Baitinger and Flegel (2021)** reported an out-of-sample investment strategy using a persistent-homology turbulence indicator that outperformed strategies using other turbulence indicators. This is a relevant positive investment precedent. Our review accessed the publisher abstract and previews, so the full timing, tuning, and execution assumptions remain unaudited here. [Turbulence strategy paper](https://link.springer.com/article/10.1007/s11408-020-00377-x)

### Order flow and liquidity

**Labyad (2018)** applied topology to LOBSTER order-message data to study relationships among stocks and order types. This establishes prior work in market microstructure. Its descriptive construction differs from our proposed price-by-time depth field and does not validate depth-recovery prediction or execution performance. [Oxford thesis](https://www.maths.ox.ac.uk/system/files/media/S%20Labyad.pdf)

## How to interpret the evidence

| Question | Assessment from the selected studies |
|---|---|
| Can topology describe meaningful organization? | Yes, with concrete examples in several fields. |
| Do financial topological summaries change around stress? | Repeated historical examples support this; advance-warning reliability needs separate validation. |
| Can TDA improve a financial model? | Some studies report gains, conditional on the construction, target, model, and evaluation. |
| Does this establish an advantage for our three ideas? | No. Each proposed use still needs its own comparison. |

A persistent feature is not a significance test or an economic mechanism. TDA transforms information already present in its inputs. Its practical value must come from useful measurement, interpretation, compression, or learning behavior. Comparisons should include relevant alternatives such as clustering, volatility and spectral features, or conventional depth and order-flow measurements.

## Implications for our explorations

These are our interpretations, rather than findings established by the cited papers. 

- **Equity peers:** investigate whether inspecting a labeled hierarchy across scales and dates improves peer interpretation or residual analysis. Correlation-derived H0 is single linkage, so ordinary hierarchical clustering is an essential comparison.
- **BTC:** existing work justifies a replication and feature-interpretation study. Establish what the features respond to before making a predictive claim.
- **Liquidity:** the source grid gives structures a tangible interpretation, but the reviewed evidence does not establish the usefulness or novelty of our annotated merge-tree proposal.

The [full evidence review](literature/financial_tda_review_2026-10-12.md) retains additional studies, including newer and negative findings, source-access limitations, and methodological concerns. The [current project scope](START_HERE.md) remains separate from these literature findings.
