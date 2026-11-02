# labs.markrox.ai

Hands-on builds in AI, organized as **Series > Lab**. Each lab ships three things:

1. **Code**: in `series/<series>/<NN-slug>/`, with tests
2. **Demo**: a short recording or hosted link in the lab's `demo/` folder
3. **Write-up**: on [markrox.ai](https://markrox.ai)

Live site: **[labs.markrox.ai](https://labs.markrox.ai)** (built from this repo)

> All data is synthetic or public. No client or production data.
>
> Personal project by Mark Roxberry. Not affiliated with or endorsed by DSI.

Code is MIT licensed. Written content in `docs/` and lab write-ups is CC BY 4.0.

## Series

| Series | Status | Plan |
|---|---|---|
| AI Eval Labs | Active | [series/ai-eval/plan.md](series/ai-eval/plan.md) |

## Layout

```
site.yaml                    # global settings (blog, site, repo, Slack channel)
plan.md                      # generated: all series at a glance
series/
  ai-eval/
    series.yaml              # source of truth: phases, labs, core + stretch scope
    plan.md                  # generated weekly plan for this series
    harness/                 # shared system under test for this series
    00-setup/ … 15-…/        # one folder per lab: code, tests, README, demo/
docs/                        # generated site pages for labs.markrox.ai
comms/                       # Slack + write-up templates
scripts/bootstrap.py         # generates folders, plans, site pages, issues
```

## Getting started

```bash
pip install pyyaml mkdocs-material
python scripts/bootstrap.py                                   # regenerate everything
python scripts/bootstrap.py --new-series ai-security "AI Security Labs"
python scripts/bootstrap.py --issues --series ai-eval         # one-time per series (needs gh)
mkdocs serve                                                  # preview locally
```

## Weekly rhythm

| Day | Step |
|---|---|
| Mon | Scope the lab; confirm core vs. stretch |
| Tue-Thu | Build against the core scope |
| Fri | Record demo, draft write-up |
| Next Mon | Publish write-up, update site, post in #dsi-ai-labs |

## Try a lab

Every lab has a core scope you can finish in a day. Fork the repo, pick a lab, and share what you find in #dsi-ai-labs.
