# Onboarding — CV-CellDetection

A quick orientation for anyone joining the electrocyte-detection work: **what this repo is, what's been done so far, and the key results.** For setup and command usage, see [README.md](README.md); this doc is the *state of the project*.

---

## 1. What this repo is

We reuse **CaImAn's CNMF** — an algorithm built to find **neurons** in two-photon calcium-imaging movies — to instead find **electrocytes** in our microscopy recordings. The goal is accurate per-cell detection (each cell found once, cleanly separated from its neighbours).

The repo has three parts:
- **`cnmf_toolkit/`** — a fork of CaImAn's CNMF **instrumented with debug hooks**, so every stage of the algorithm (init → spatial → temporal → merge → …) is saved to disk and can be inspected. It ships:
  - a **runner** (`cnmf_runner.py`) and named configs (`cnmf_manager.py`),
  - a **napari viewer** (`cnmf_viewer.py`) to step through the stages,
  - a **ground-truth scorer** (`ground_truth_scorer.py`) to score a run against manual tags.
- **`notebooks/`** — the lab's actual electrocyte-detection analysis notebooks.
- **`data/`** — inputs (`RawData/` movies, `TaggedData/` manual annotations) and outputs (`results/`). Content is gitignored; the folder structure ships pre-built.

**Environment:** conda env `cv-celldetection` (Python 3.12). One-command setup: `conda env create -f environment.yml`.

---

## 2. What's been done so far

The main effort was the **merge-tuning mission**: CNMF kept detecting two neighbouring electrocytes as **one** cell (a "merge"), and the task was to fix that and prove it against the manual tags.

- **Built the measurement first:** an evaluation tool that overlays CNMF's detections on the manual tags and counts *correct / merge / split / junk / covered / missed* per run (the local `merge_eval.py`, now shipped as the official **`ground_truth_scorer.py`**).
- **Ran two full test plans (12 runs + several analyses), all logged**, trying: component evaluation, the merge threshold, `max_merge_area`, patch/`K`/`gSig` tuning, a different init method (**corr_pnr**), motion correction, and three ways of splitting merged cells apart (by shape, by activity over time, and by image brightness).
- **Currently drafting a third plan** (test plan 3): replace CNMF's weak seeding with a **deep-learning segmenter (CellPose / StarDist)** — the one promising untried idea, endorsed by the team lead.

Detailed, per-experiment records live locally under `docs/superpowers/` (gitignored): the specs, plans, the living test log, and the findings write-ups. The **team-facing summary** is `docs/superpowers/research/2026-06-25-merge-tuning-full-findings.md`.

---

## 3. The most important results

**The merge problem is not a settings problem — and we proved *why*, three independent ways:**

1. **The "merges" are genuinely inseparable.** For each merged pair, the two cells' activity over time is **~88% identical** (they're adjacent *and* fire together — likely coupled/co-stimulated). With no difference in space *or* time, no algorithm can tell "one cell" from "two co-firing cells." It's a **resolution/biology limit**, not a tunable parameter.
2. **Most of the "junk" is real cells we never tagged.** ~103 of ~123 "junk" detections survive a strict quality filter — they look like genuine cells to CNMF. Our annotation is an incomplete binary mask, so real-but-untagged cells get scored as errors. This is a **measurement limit**.
3. **The best configuration is the standard "greedy" one** we started with — the fancier alternatives all did worse. Baseline: **158/200 cells covered, 42 missed, 25 merges, 123 junk.**

**What unblocks further progress (not more tuning):**
- A **per-cell labelled annotation** (each cell its own label, ideally complete) — to measure accurately and confirm how much "junk" is real cells.
- **Deep-learning seeding (CellPose)** — the active next experiment: it may separate touching cells where CNMF's blur-based seeding can't.
- Possibly **higher-resolution imaging** for the truly-touching co-firing pairs.

---

## 4. Where things are

| You want to… | Go to |
|---|---|
| Set up + run the tools | [README.md](README.md), [cnmf_toolkit/USAGE.md](cnmf_toolkit/USAGE.md) |
| Score a run vs manual tags | `cnmf_toolkit/ground_truth_scorer.py` (README "Step 3") |
| Read the full merge-tuning findings | `docs/superpowers/research/2026-06-25-merge-tuning-full-findings.md` *(local)* |
| See per-experiment detail | `docs/superpowers/research/2026-06-17-merge-tuning-testlog.md` *(local)* |
| See the next plan (CellPose) | `docs/superpowers/plans/2026-07-06-dl-seeding-plan.md` *(local)* |
| Understand the architecture | [CLAUDE.md](CLAUDE.md), [.claude/docs/architectural_patterns.md](.claude/docs/architectural_patterns.md) |
| See per-PR history | [CHANGELOG.md](CHANGELOG.md) |

*(Docs marked “local” live under `docs/`, which is gitignored — ask a teammate for a copy, or read the summary above.)*

---

## 5. Get started in 3 commands

```bash
conda env create -f environment.yml      # one-time
conda activate cv-celldetection
cd cnmf_toolkit && python cnmf_runner.py "../data/RawData/your_movie.tif"
```
Then optionally score it: `python ground_truth_scorer.py --annotation ../data/TaggedData/your_tags.tif`.
