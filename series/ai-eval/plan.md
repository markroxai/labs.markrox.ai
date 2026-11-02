# AI Eval Labs: Plan

Hands-on builds in AI evaluation: grading, statistics, judges, robustness, and production eval pipelines.

Generated from `series.yaml`. Edit that file, then run `python scripts/bootstrap.py`.

Each lab has a **core** scope (~6-8 hours, enough for demo + write-up) and an optional **stretch** scope.

## Phase 0: Setup

### Lab 00: Setup and Reference Agent

_Depends on: None_

**Core**

- [ ] Repo, labels, milestones, and Project board in place
- [ ] Reference agent in harness/ with 3-4 mock tools and a small RAG corpus
- [ ] Synthetic task suite (~30 tasks) with expected outcomes
- [ ] labs.markrox.ai live via GitHub Pages
- [ ] #dsi-ai-labs created and launch post sent

**Stretch**

- [ ] Swappable model backends (frontier + small open model)

## Phase 1: Foundations

### Lab 01: Trajectory Grading Engine

_Depends on: Lab 00 · orig #1_

**Core**

- [ ] Define a deterministic DAG of expected tool calls for the task suite
- [ ] Score each step; fail on hallucinated API params or skipped checks
- [ ] Report the exact step where the run broke

**Stretch**

- [ ] Partial credit for valid alternative orderings

### Lab 02: Statistical Significance Engine

_Depends on: Lab 01 · orig #7_

**Core**

- [ ] Bootstrap utility for model-vs-model deltas
- [ ] Output win margin with confidence interval and p-value
- [ ] Flag deltas that are noise at the current sample size

**Stretch**

- [ ] Power analysis (sample size needed to detect a given delta)

### Lab 03: Calibrated LLM-as-a-Judge

_Depends on: Lab 01, Lab 02 · orig #3_

**Core**

- [ ] Human-labeled anchor set of ~100 items
- [ ] Measure verbosity, position, and self-preference bias
- [ ] Document judge agreement vs. human labels (Cohen's kappa)

**Stretch**

- [ ] Grow anchor set to 500 items

### Lab 04: Dataset Contamination Checker

_Depends on: None · orig #14_

**Core**

- [ ] N-gram overlap scan between eval set and a public training corpus sample
- [ ] Embedding similarity scan for near-duplicates
- [ ] Contamination report with thresholds

**Stretch**

- [ ] MinHash/LSH to scale to large corpora

## Phase 2: Robustness and Security

### Lab 05: RAG Adversarial Harness

_Depends on: Lab 03 · orig #5_

**Core**

- [ ] Inject irrelevant context and contradictory documents
- [ ] Remove citations and test for grounded abstention
- [ ] Score confident-but-ungrounded answers as failures

**Stretch**

- [ ] Per-perturbation degradation curves

### Lab 06: Synthetic Edge-Case Generator

_Depends on: Lab 03 · orig #12_

**Core**

- [ ] Use a frontier model to generate out-of-distribution inputs
- [ ] Cover boundary conditions systematically
- [ ] Review and add accepted cases to the golden dataset

**Stretch**

- [ ] Judge-filtered generation with dedup against existing set

### Lab 07: Agent Red-Team Fuzzer

_Depends on: Lab 01 · orig #8_

**Core**

- [ ] Inject prompt injections into agent inputs and tool outputs
- [ ] Feed malformed tool schemas
- [ ] Trigger infinite-loop conditions; verify guardrails

**Stretch**

- [ ] Mutation-based fuzzing with a coverage score

### Lab 08: Context Window Eviction Tester

_Depends on: Lab 01 · orig #13_

**Core**

- [ ] Fill agent working memory with noise
- [ ] Test compression, eviction, and retrieval of key state
- [ ] Measure task success as context pressure rises

**Stretch**

- [ ] Compare two memory strategies head to head

## Phase 3: Production Pipelines

### Lab 09: CI/CD Regression Gate

_Depends on: Lab 01, Lab 02 · orig #4_

**Core**

- [ ] GitHub Action running parameterized evals on every PR
- [ ] Block merge if task success drops 2% (significance-checked) or latency spikes
- [ ] Publish eval summary as a PR comment

**Stretch**

- [ ] Cached baselines and per-tag gating

### Lab 10: Counterfactual Replay Debugger

_Depends on: Lab 01 · orig #11_

**Core**

- [ ] Record every LLM hop and tool output
- [ ] Swap one node and replay the rest of the trajectory
- [ ] Isolate the step that introduced a hallucination

**Stretch**

- [ ] Automated bisection across nodes

### Lab 11: Shadow Routing Comparator

_Depends on: Lab 01, Lab 02 · orig #2_

**Core**

- [ ] Proxy mirroring a sample of simulated traffic to a candidate model
- [ ] Diff trajectories between current and candidate
- [ ] Auto-generate a cost/quality report

**Stretch**

- [ ] Configurable sampling and canary percentage

### Lab 12: Production Drift Monitor

_Depends on: Lab 01, Lab 03 · orig #9_

**Core**

- [ ] Nightly sampling job over simulated live traffic
- [ ] Run offline trajectory evals on samples
- [ ] Alert on quality decay trends

**Stretch**

- [ ] Input-distribution drift (embedding shift) alongside quality drift

### Lab 13: Cost-Quality Pareto Dashboard

_Depends on: Lab 02 · orig #10_

**Core**

- [ ] Collect cost and success rate per routing strategy
- [ ] Plot the Pareto frontier per tenant, with confidence intervals
- [ ] Compare reasoning-heavy vs. fast routing

**Stretch**

- [ ] Interactive dashboard published to labs.markrox.ai

### Lab 14: Automated DPO Flywheel

_Depends on: Lab 03 · orig #6_

**Core**

- [ ] Capture simulated thumbs-down feedback
- [ ] Format feedback into preference pairs
- [ ] LoRA fine-tune a small open model and re-eval

**Stretch**

- [ ] Scheduled end-to-end loop with regression gate

## Phase 4: Publish

### Lab 15: Public Eval Methodology Teardown

_Depends on: Lab 01, Lab 02, Lab 03 · orig #15_

**Core**

- [ ] Deep-dive 1: grading rubrics
- [ ] Deep-dive 2: judge prompts and calibration
- [ ] Deep-dive 3: statistical framework

**Stretch**

- [ ] Series retrospective post
