# What would merge trees actually do for us?

Technical reference, October 12, 2026. Read [START_HERE.md](../START_HERE.md) for the agreed three-study scope and current decisions. This note explains candidate constructions and their limitations, not established trading signals.

## 1. A practical role: identify structures we can measure

A depth history contains many local peaks. Some are small fluctuations within a larger concentration; others are separated by genuinely thin regions. A merge tree organizes these peaks by the depth at which their regions connect. It can therefore support a repeatable way to identify candidate liquidity concentrations, simplify small branches, and attach measurements to the remaining structures.

The useful output is not merely “this book has a tree.” It might be:

> This window contains two prominent concentrations near the best quote. One extends across most of the observed window and reaches its current edge; the other is a brief, old episode.

That statement combines topology with information retained from the source data. Whether it predicts anything is a separate empirical question.

[TTK's scalar-field tutorial](https://topology-tool-kit.github.io/persistentHomologyDummies.html) demonstrates the established methodological idea: simplify scalar-field features using persistence and recover the geometry associated with tree structures. Applying that idea to displayed depth is our proposed experiment, not a financial result established by that tutorial.

## 2. The input and a numerical example

Use one side of one reconstructed book. Let `D(price bin, past time)` be displayed quantity, sampled over an already-observed window. At threshold `q`, retain the cells with `D >= q`; lower `q` from high depth to low depth. This is a superlevel construction on `D`, equivalently a sublevel construction on `-D`.

Suppose a region has a peak of 1,000 units. A nearby secondary peak reaches 800, and their regions connect at 750. The secondary branch's prominence is `800 - 750 = 50` units. It is a relatively shallow bump within a substantial common region.

Now keep those peak depths but lower the connecting depth to 100. The secondary branch's prominence becomes `800 - 100 = 700` units. This describes a much more distinct concentration, separated by a thin connection. It does **not** establish that either concentration is durable or executable when needed.

On a single price axis, this is closely related to ordinary peak prominence. A price–time field extends the construction to two-dimensional regions and their hierarchy. That is a reason to examine the representation, not proof it improves on conventional peak or image analysis.

## 3. Three possible uses

### A. Reduce a noisy depth map to identifiable concentrations

Counting every local maximum can treat small ripples as separate structures. A tree provides a hierarchy for keeping major branches while simplifying weaker ones. It avoids choosing one absolute “large wall” threshold at the beginning, although a simplification tolerance still has to be chosen and checked.

For example, 30 maxima might organize into three major branches with smaller subbranches. This supplies candidates to inspect, rather than a claim that three economically distinct agents or orders exist.

### B. Build features with explanations in the original book

| Candidate measurement | Interpretation | What the tree supplies and what must be added |
|---|---|---|
| Secondary-branch prominence | Depth contrast between a peak and its connection to a concentration born earlier in the filtration | Finite H0 pairing / branch decomposition; measured in depth units; filtration age is not chronological age |
| Component count as depth cutoff varies | Fragmentation of high-depth regions across thresholds | Betti-0 curve; does not retain full merger ancestry |
| Parent–child merger relationships | Which small concentrations belong to the same larger connected region | Merge hierarchy; more identity information than an unlabelled H0 diagram |
| Price width and occupied price–time area | How broad a selected concentration is | Source-region annotation at an explicitly stated level |
| Temporal span, last appearance, current-edge contact | Whether a selected region is recent and extends toward the observation time | Source timestamps and geometry, not persistence length |
| Distance to the best quote | Whether the region is near currently accessible prices | Source price coordinates and contemporaneous quote data |

A branch does not have one uniquely defined area. One reproducible convention is to inspect its component halfway between its peak and merge levels. Record that convention and compare another reasonable choice. Time span is not continuous availability at one fixed price: a connected region can move through price bins. Summing depth across time also gives quantity-times-duration, not additional executable inventory.

### C. Test a specific economic hypothesis

A possible hypothesis is that recent, prominent, broad concentrations are associated with more persistent near-quote depth than isolated spikes are. A test could compare future near-quote depth depletion over one fixed horizon, holding current depth, spread, and recent flow comparable. This is a proposal; it has not been tested here.

The essential comparison is a conventional model using depth, imbalance, changes in depth, gaps, and duration, versus the same model with a few tree-derived features. A descriptive study can come first: annotate several episodes and determine whether the tree is even summarizing the intended behavior.

An important negative result would be that ordinary run lengths and peak widths explain the same effects more simply. That still teaches when the TDA representation is useful and when it is unnecessary.

## 4. What the tree does not give us

**Topological persistence is depth contrast here, not seconds.** A very brief but tall spike can have a prominent branch. A long, flat concentration and a short one can have the same abstract tree.

The abstract tree also discards the direction of time and absolute price location. Reversing a window can exchange a build-up with a withdrawal while preserving its tree. Translating a structure in price can preserve the tree while changing its distance from the best quote. Source annotations are essential if those distinctions matter.

The tree does not identify individual orders, distinguish cancellation from execution without additional messages, establish hidden liquidity, infer trading intent, or establish subsequent mean reversion. Aggregated depth can remain similar while its constituent orders change completely.

Nor is a prominent feature automatically economically important. A tiny isolated peak may have high relative prominence while a large broad background contains more usable quantity. Retain ordinary depth and location measurements alongside topology.

There are mathematical constructions called [decorated merge trees](https://arxiv.org/abs/2103.15804) that combine component ancestry with additional homological information. Our proposal to attach price/time metadata is a simpler annotation scheme; it should not be conflated with implementing that paper's formal invariant.

## 5. A controlled example: same aggregate depth, different organization

The accompanying [script](../liquidity/experiments/depth_topology_demo.py), [figure](../liquidity/experiments/depth_topology_demo.png), and [results](../liquidity/experiments/depth_topology_demo.json) are synthetic educational controls. They do not use account data or demonstrate forecasting performance.

The first pair of fields has the same total depth at every time, the same depth histogram, the same first price moment at every time, and the same final snapshot. One contains two uninterrupted high-depth bands. The other breaks the high-depth material into fourteen separated regions. Their component hierarchies differ even though those aggregate summaries match. Ordinary turnover or run-length measurements also distinguish this pair; topology is not uniquely capable of doing so.

The second pair has the same histogram, timewise total depth, and final snapshot. One contains an enclosed low-depth pocket; the other opens that pocket to the exterior. This motivates H1 while showing a limitation: an economically relevant open gap need not create an H1 class.

The script computes connected-component counts and the Euler characteristic of closed-square unions at each distinct depth threshold. It **does not implement general persistence pairing or a merge-tree extraction algorithm**. In these two-level examples, the full intervals follow directly from the component/hole counts: features appear at depth 8 and merge/fill at depth 1. Equal birth values make the identity of the essential H0 branch arbitrary; the interval multiplicities are unambiguous.

## 6. Cubical persistence versus a merge tree

| Construction | What it contributes to this pilot |
|---|---|
| Cubical H0 persistence of `-D` | Birth and merger levels of high-depth components |
| Merge tree of `-D` | Which components merge into which; retain links to source regions |
| Cubical H1 persistence of `-D` | Enclosed low-depth pockets surrounded by high-depth cells |
| Cubical sublevel persistence of `D` | A different question: how low-depth regions appear and connect |

Conventions sometimes call the superlevel tree of `D` a **split tree**, or equivalently a join/merge tree of `-D`. State the filtration explicitly to avoid a naming dispute.

An H1 class is not automatically a liquidity barrier, trading signal, or arbitrage cycle. Boundary-connected low-depth regions are missed by ordinary H1. H0 and source-annotated merge structures may be easier to explain financially; H1 can remain an optional comparison.

[GUDHI's cubical API](https://gudhi.inria.fr/python/latest/cubical_complex_ref.html) supports grids supplied as top-dimensional cell values or vertex values. These define different filtrations. With top-dimensional closed square cells, diagonal contact connects components, so H0 agrees with 8-neighbor raster connectivity. Do not silently compare against a 4-neighbor implementation. Periodic boundaries would introduce artificial connections here.

Other representation choices to state: fixed-price versus quote-relative coordinates; bin width; physical-time versus event-time sampling; bid and ask separation; raw quantity versus normalization; and handling of missing data. Unknown observations are not zero depth. A moving or truncated window can change topology through its boundary alone. All windows used for a prediction must end at the feature timestamp.

## 7. Relationship to the three-study plan

The agreed framework and comparison protocol are maintained in [START_HERE.md](../START_HERE.md). This note supplies the depth construction and the weighted return-regression application that now frames the equity study. Options remain a possible later extension.

## 8. Equity peer structure and weighted return mean reversion

This is now the first pilot's working direction. Equity return panels avoid many problems of comparing contracts across strike, expiry, staleness, exercise style, and IV conventions. The question is whether TDA helps describe useful peer relationships for a controlled relative-return reversal study. An introductory options study does not inherently require an industrial volatility surface or optimized trinomial pricer, but options are deferred; authentic historical option quote/IV coverage is not yet established by the Alpaca probe.

The public weighted-regression construction uses cross-sectional returns `r`, an exposure matrix `X`, positive diagonal weights `W`, and a positive position scale `c`. With independent exposure columns:

```text
beta = (X' W X)^(-1) X' W r
e = r - X beta
h = -c W e
```

The normal equations imply `X' h = 0`. Group indicators make the fitted returns weighted group means; the contrarian positions buy relative underperformers and short outperformers. Inverse trailing variance is one possible weight. Raw residual positions `-e` do not generally inherit this neutrality under weighted regression. A complete set of group indicators already spans the intercept. Neutrality covers only specified exposures and does not prove that residual returns subsequently reverse. These identities are derived in [Kakushadze, *Mean-Reversion and Optimization*, §§2.4–2.7](https://arxiv.org/html/1408.2217v3).

TDA's proposed role is to investigate the peer hierarchy **before** evaluating relative-return deviations. Build a trailing similarity structure, retain asset labels, and examine whether the hierarchy defines interpretable and stable groups. Hold the regression fixed while comparing sector groups, another conventional linkage rule, and the H0 hierarchy. Examine residual behavior before adding a portfolio execution layer.

For a distance-threshold graph/Rips filtration, the H0 hierarchy is single linkage. This equivalence is a useful lesson, not a new topological clustering algorithm. See [Carlsson and Mémoli, *Characterization, Stability and Convergence of Hierarchical Clustering Methods*](https://www.jmlr.org/papers/v11/carlsson10a.html). A worthwhile question is whether retaining several scales or tracking membership stability adds interpretability beyond one cluster cut. A correlation-derived topology remains a summary of correlation, not newly recovered higher-order dependence.

Use historical information only to form groups and weights. Make the signal-observation and hypothetical-entry times explicit. Adjust prices consistently, handle missing observations, and distinguish a fixed educational basket from a historically investable universe. Position caps or clipping can break exact neutrality. Costs, borrow availability, and execution become necessary if the work advances to tradable performance claims.

Bibliographic note: the user referred to Kakushadze and Serur's *151 Trading Strategies*, especially §§3.9–3.10. [Springer's current listing labels the book retracted](https://link.springer.com/book/10.1007/978-3-030-02792-6?page=2). No explanation was verified in this review, and no inference about the reason is made. The independently published derivation linked above allows the regression mathematics to be checked directly.

No proprietary internship details or materials are needed for any of these proposed experiments.

## Optional extensions and useful negative controls

These are parked ideas, not additions to the initial scope:

- Source attribution: preserve links from summaries to observations; persistence images are not invertible and representative cycles may be nonunique. Test proposed explanations by perturbing source regions and matched controls.
- Compare Euler characteristic curves with separate H0/H1 summaries: components and holes can cancel in Euler characteristic. Compare cost, interpretation, and lost information.
- Temporal/zigzag or multiparameter methods should follow a demonstrated limitation of the simpler representation, rather than expand the pilot by default.
- A scalar price cloud on a line has no positive-dimensional ordinary Euclidean Rips homology; delay coordinates or another justified construction are needed for richer geometry.
- For all full circular delay vectors of a real length-N signal, squared distance is `2*C(0) - 2*C(j-i)`, where C is circular autocorrelation. Equal Fourier magnitudes therefore give identical Rips persistence in this particular construction. Short/local/noncircular embeddings need not behave that way. This is a useful negative control, not a new theorem; see [Perea–Harer](https://arxiv.org/abs/1307.6188).
- Under positive coordinate rescaling, Euclidean Rips birth/death scales rescale too; the full landscape L1 norm scales quadratically. Control amplitude before calling a change structural.
