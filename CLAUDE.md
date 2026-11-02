# CLAUDE.md

Guidance for Claude Code working in this repo.

## What this repo is

labs.markrox.ai: hands-on AI builds organized as **Series > Lab**. Each lab ships code + tests, a short demo, and a write-up (on markrox.ai). Personal project by Mark Roxberry; not a DSI deliverable.

Active series: **AI Eval Labs** (`series/ai-eval/`). The system under test is a research assistant agent over a public-domain corpus, in `series/ai-eval/harness/`.

## Hard rules

- **Synthetic or public data only.** Never add client, employer, or production data. Corpus documents must be public domain or openly licensed, with the source recorded.
- **Never commit secrets.** Keys live in `.env` (gitignored). Add new variables to `.env.example` with an empty value.
- **Tests run offline.** `pytest` must pass with no network and no API keys, using the `mock` model backend. Mark tests that call real models with `@pytest.mark.live`; they are skipped by default.
- **Don't edit generated files by hand:** `plan.md`, `series/*/plan.md`, and everything under `docs/`. Edit `site.yaml` or `series/*/series.yaml`, then run `python scripts/bootstrap.py`.
- **The trace schema is a contract.** `series/ai-eval/harness/src/harness/trace.py` is used by labs 01, 09, 10, 11, and 12. Changing it needs a schema version bump and a note in the harness README.

## Layout

```
site.yaml                         global settings
series/<series>/series.yaml       source of truth for labs (scope, deps)
series/<series>/harness/          shared system under test for that series
series/<series>/NN-slug/          one lab: src/, tests/, README.md, demo/
scripts/bootstrap.py              regenerates plans, site pages, lab folders, issues
```

A lab imports the harness; it never copies it. If a lab needs a harness change, make it in the harness with tests, then use it from the lab.

## Stack

- Python 3.12+, `uv` for environments and dependencies, one `pyproject.toml` per package (harness and each lab)
- `pydantic` v2 for schemas, `pytest` for tests, `ruff` for lint and format
- `litellm` as the single model client; models are chosen by name from `series/ai-eval/harness/models.yaml`
- CLIs with `typer`; output tables with `rich`
- Keep dependencies minimal. Prefer the standard library plus the above. Ask before adding a heavy dependency.

## Models

Every model call goes through `harness.models.complete(model_name, ...)`. Never call a provider SDK directly.

- `mock`: deterministic, replays fixtures; used by all default tests and CI
- `local-*`: Ollama, no key needed
- hosted entries read keys from env vars named in `models.yaml`; missing key means a clear error naming the variable

Each run records model name, provider, token counts, latency, and estimated cost in the trace.

## Commands

```bash
cd series/ai-eval/harness
uv sync
uv run pytest                        # offline, mock backend
uv run pytest -m live                # real models (needs keys or Ollama)
uv run ruff check . && uv run ruff format .
uv run harness run --model mock --tasks all
uv run harness run --model local-llama --tasks smoke
```

## How to work on a lab

1. Read the lab's `README.md` and its entry in `series.yaml`. Build to the **core** scope first; stretch only when core is done and tested.
2. Small commits, with messages prefixed by lab: `ai-eval/01: score tool-call DAG steps`.
3. Keep the lab `README.md` current: goal, how to run, findings. Findings should include at least one concrete number.
4. Put demo assets (recordings, screenshots, small output files) in the lab's `demo/`.
5. When a session ends, write a short progress note (what changed, what's next, any surprise) suitable for posting to #dsi-ai-labs.

## Style

- Type hints everywhere; pydantic models at boundaries
- Pure functions for scoring and statistics; side effects (model calls, file I/O) at the edges
- Every metric gets a docstring that says exactly what it measures and its range
- Prefer clear output over clever code: these labs are read by others
