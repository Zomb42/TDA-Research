# TDA learning and local setup

**Use the existing `tda` Conda environment for this project** (user instruction, November 4, 2026): `conda activate tda`. Select its kernel in notebooks. Without shell activation, use `conda run --no-capture-output -n tda python ...`. On this Mac the interpreter is `/Users/derickshi/anaconda3/envs/tda/bin/python`; the separate ParaView/TTK launchers below manage their own bundled runtime.

For the current research plan, read [START_HERE.md](START_HERE.md). This guide contains setup and tutorial reference material, not additional project requirements.

Use [scikit_tda_tutorial.ipynb](scikit_tda_tutorial.ipynb) for the introductory constructions and explanations; [playground.ipynb](playground.ipynb) for synthetic experiments; and [topology_toolkit_intro.ipynb](topology_toolkit_intro.ipynb) for scalar fields, merge trees, Morse–Smale segmentation, and TTK. The playground's sports profiles are fictional geometry exercises, not a research direction.

## Open ParaView with TTK on this Mac

Double-click **ParaView TTK.app** in this folder or in your personal `~/Applications` folder. This Finder launcher opens ParaView 6.1.1 with the full TTK 1.4 plugin and the saved terrain/Morse–Smale demonstration. Launching it through macOS has been verified on this Mac. From Terminal, you can also run `sh "Open ParaView.command"` from this folder. The downloaded apps named `paraview.app` do not receive the required library paths when opened directly; use the launcher named **ParaView TTK**.

To compute the output files without opening the desktop app, run `sh ttk_assets/run_ttk.sh`. This now runs the original ParaView plugin pipeline successfully. The earlier `run_ttk_vtk.sh` remains available as a direct VTK alternative.

The outputs are `ttk_assets/results/diagram.vtu`, `critical_points.vtp`, `separatrices.vtp`, and `segmentation.vti`. Open them in ParaView to inspect the persistence pairs, critical points, separating curves, and labeled regions. The segmentation is VTK image data, so its extension is `.vti`.

Keep `~/ttk-binary`: the launchers use its TTK/ParaView packages and a separate Graphviz 15.1.1 build under `~/ttk-binary/compat`. `ttk_assets/ttk_env.sh` supplies the correct Python framework and library paths for each launch. No `.zshrc` edits or Conda activation are needed for these launchers. Opening the copied app under `/usr/local` directly does not apply these settings. See [runtime notes](ttk_assets/RUNTIME_NOTES.md) for the repair details.

## Run the notebooks

Open a notebook in VS Code, select **TDA (conda)** as its kernel, and run the cells from the top. The kernel is the Python process that executes the notebook and supplies its packages. If you restart it, rerun earlier cells to recreate their variables.

For terminal work, activate the environment with:

```sh
conda activate tda
```

The environment was cloned from `AlgoTrade` and is managed separately. It contains additional packages beyond those needed here. VS Code terminal auto activation is off, so select the notebook kernel and activate terminal environments explicitly.

## What can I do with these tools?

| Your question | Workflow | What you get |
|---|---|---|
| Does a point cloud have a persistent loop? | Coordinates → Ripser → Persim plot | Birth and death scales of H1 features |
| How does structure change as I add noise? | Repeat the experiment → compute diagrams → compare them | Changes in persistence and diagram distances |
| How different are two shapes? | Use comparable distances → compute diagrams → bottleneck matching | One measure of the difference between their topological summaries |
| Can shape help predict a label? | One cloud per example → diagrams → images → classifier | Predictions based on topological features |
| What changes when I add graph connections? | Choose an edge or path filtration → compute persistence | Changes in components and loops under that construction |
| Can I explore repeating patterns in a time series? | Build sliding windows → treat windows as points → compute persistence | A possible way to investigate cyclic structure; window design and validation are additional work |

These are tools for developing and evaluating hypotheses. A persistent feature can be interesting without proving a scientific claim. Compare against simpler summaries, such as distances, density, or ordinary graph statistics, to find out whether TDA adds useful information.

## The packages, in practical terms

**Ripser computes the topology.** Give it a point cloud or a distance matrix. Its output includes arrays of birth–death pairs, grouped by homology dimension. Use it when you want persistent homology of a Vietoris–Rips filtration. `Rips` is its class interface. [Ripser API](https://ripser.scikit-tda.org/en/latest/reference/stubs/ripser.ripser.html)

**Persim helps you use the output.** Plot diagrams, compare them with bottleneck distance, or turn them into representations such as persistence images and landscapes. A persistence image is a grid summarizing a diagram, not a picture of your original data. [Persistence images](https://persim.scikit-tda.org/en/latest/notebooks/Persistence%20images.html)

**TaDAsets creates practice data.** Shapes with known structure let you check your intuition before working with an unfamiliar dataset. In the tutorial, it produces samples from a circle.

**NumPy, SciPy, and Matplotlib support the workflow.** NumPy stores arrays; SciPy computes distances and shortest paths; Matplotlib displays the results. **Scikit-learn** supplies the classification machinery: data splitting, feature scaling, and logistic regression.

The original guide also mentions **Kepler Mapper**, which builds an exploratory graph from overlapping groups of data, and **CechMate**, which supports other filtration constructions. They are part of the broader scikit-tda ecosystem and are not used in these notebooks. Mapper graphs and persistence diagrams are different summaries. See the [original guide's package overview](https://docs.scikit-tda.org/en/latest/notebooks/scikit-tda%20Tutorial.html).

## A small example to keep in mind

Imagine dots sampled around a ring. At a very small connection distance, each dot is a separate component. Increase the threshold and neighboring dots connect. A loop appears once they connect around the ring. Increase it further and filled triangles eventually fill the loop.

Persistent homology records that loop's birth and death thresholds. If its diagram point is `(0.3, 1.6)`, it persists for `1.6 − 0.3 = 1.3` distance units. That pair describes a range of scales, not the loop's position or radius in the original picture.

| Term | Meaning |
|---|---|
| H0 | Connected components |
| H1 | Independent loops |
| H2 | Enclosed voids |
| Filtration | Shapes nested inside one another as a parameter increases |
| Birth / death | When a feature appears / disappears in that filtration |
| Persistence | Death minus birth for a finite interval |
| Betti number | Number of independent features of a given dimension at one scale |
| Infinite death | A feature survives the computed filtration; a cutoff may have stopped the calculation early |

The number of rows in a full persistence diagram counts intervals across scales. It is not the number of features present simultaneously at every scale.

## What do the persistence images mean?

A persistence image is a **heatmap of when topological features appear and how long they survive**. Our notebook uses H1 images, so the features being summarized are loops. Each image summarizes one entire point cloud.

Follow one loop through the conversion:

1. Ripser records its birth and death, for example `(0.3, 1.6)`.
2. Convert death to persistence: `1.6 − 0.3 = 1.3`. Its new coordinates are `(birth=0.3, persistence=1.3)`.
3. Place a smooth bump around that location. With our default settings, the bump is weighted by the feature's persistence, so longer intervals contribute more total weight.
4. Add the bumps from all the features. Integrate the combined surface over each grid cell to produce the pixel values.

The result tells you where the diagram's weighted contributions are concentrated. Smoothing lets nearby diagram points contribute to similar pixels, instead of abruptly assigning a point to just one bin. Pixel size and smoothing control how much detail is retained. [Persim's explanation and examples](https://persim.scikit-tda.org/en/latest/notebooks/Persistence%20images.html)

### Reading the axes and colors

| Part of the image | How to interpret it |
|---|---|
| Horizontal axis: birth | Farther right means features first appeared at larger connection distances. |
| Vertical axis: persistence | Higher means longer intervals between birth and death. |
| Colorbar | The numerical amount of weighted, smoothed contribution accumulated in a pixel. |
| Bright region | More contribution near those birth and persistence values. It may come from one strongly weighted feature, several overlapping features, or both. |
| Dark region | Less contribution in that region of the summary. |

The location of a bright patch describes **scales in the filtration**, not a location in the original scatter plot. A patch on the right does not mean a loop is on the right side of the point cloud. A single loop can contribute to many pixels, and several loops can overlap into one patch, so counting patches does not count loops. The colorbar is also not a probability or a confidence score.

For our `(0.3, 1.6)` example, expect a contribution centered near birth 0.3 and persistence 1.3. A shorter interval `(0.3, 0.4)` contributes near persistence 0.1, with less total weight under the default weighting. Smoothing spreads both contributions around their centers, and the plotted grid may capture only part of that spread.

In the notebook's **Noise image** and **Circles image**, ask: “Where are the contributions concentrated, and how does their strength differ?” The panels share a color scale, so the same color represents the same value. Noise can create loops too, and noise mixed with circles may obscure them. A brighter image alone does not establish that the cloud contains meaningful circles.

Compare images made with the same distance units, grid, weighting, and smoothing. A larger pixel covers more area and can accumulate more contribution, so pixel values from different resolutions are not directly interchangeable.

## Why use persistence images for machine learning?

**They turn a variable-length topological summary into a fixed-length list of numbers.** That makes the summary usable by the logistic regression model in this tutorial.

Suppose cloud A produces 4 H1 intervals and cloud B produces 11. Their diagrams contain different numbers of rows, and the rows have no natural one-to-one correspondence. A standard tabular classifier expects each example to have the same feature columns with the same meaning. Flattening the raw diagrams would not meet that requirement.

A shared image grid supplies those columns. For example, a 10 × 10 grid gives every cloud exactly 100 numbers. Feature 0 always refers to the same birth–persistence region, feature 1 to the next region, and so on. The grid size is illustrative; the notebook prints the dimensions it actually uses.

```text
one point cloud
    ↓ Ripser
one H1 diagram, with however many intervals were detected
    ↓ PersistenceImager, using a shared grid
one numerical image
    ↓ flatten pixels in a consistent order
one row of features
    ↓ trained classifier
prediction: noise or noise mixed with circles
```

Across many labeled clouds, the model can learn whether particular combinations of pixel values help distinguish the classes. Logistic regression assigns a learned coefficient to each scaled pixel feature. It does not inspect the displayed colors: it receives the underlying numerical array. Changing the plot's color palette does not change the model's input.

In this example, **one whole cloud is one training example**. Twenty-four clouds yield 24 feature rows and 24 labels; the individual points within a cloud are not separately labeled training examples.

### Are images required?

Persistence images are one option. You could instead use summaries such as the longest finite H1 lifetime, sampled persistence landscapes, or methods designed to compare diagrams directly. Images provide a convenient representation for conventional models, but compress information and introduce choices about resolution, smoothing, and weighting. Their usefulness should be checked against simpler features.

The tutorial fits the image grid using only training clouds, then transforms training and test diagrams with that same grid. Its scaler also learns from training data only. This keeps the held-out examples from determining the learned preprocessing. Topological features can help when shape carries information about the label; they do not guarantee better predictions for every problem.

## How to read the tutorial

1. **Before the code** introduces the objects passed between packages.
2. **Persistence API** shows how data and parameter choices affect the diagrams.
3. **Images and landscapes** explain why you might summarize a diagram numerically.
4. **Diagram analysis and classification** connects those summaries to comparison and prediction.
5. **Graphs** shows why different definitions of distance give different answers.

The graph is generated practice data because the guide's chemistry CSV files were not included. Its edge weights have no chemical interpretation. The classifier also uses a small synthetic dataset: its held-out accuracy is a learning exercise.

## Moving to your own data

First decide what one example is. For a table, rows might be points in one cloud. For classification, you generally need many independently labeled examples—such as one cloud per subject or one graph per experiment. The tutorial has one label per entire cloud.

Then choose what “close” means. Units and feature scaling affect distances, and therefore affect persistence. A graph strength or similarity score should not automatically be treated as a distance: decide whether a stronger edge should enter earlier and justify the conversion.

Begin with a small sample and H0/H1. Inspect the original data alongside the diagram, vary a few reasonable parameters, and check whether the interpretation survives. For prediction, learn preprocessing from the training set, keep the test set separate, and compare TDA features with a simple baseline. Larger samples and higher homology dimensions can make Rips computations expensive.
