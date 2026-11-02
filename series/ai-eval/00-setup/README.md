# Lab 00: Setup and Reference Agent

**Series:** AI Eval Labs · **Phase:** Setup · **Depends on:** None · **Status:** In progress

## Goal

Build the system under test for the whole series: a small research assistant agent that searches a public-domain corpus, reads specific sections, and answers with citations. Every action is recorded as a trace that later labs grade, replay, and compare.

Lab 00 builds the subject, not the evaluation. Keep it simple, deterministic where possible, and easy to break on purpose later.

## Core scope

- [x] Repo, issues, labs.markrox.ai, and #dsi-ai-labs
- [ ] Model registry with `mock`, local, and hosted entries behind one client
- [ ] Corpus of ~40 public-domain documents, chunked by section and indexed
- [ ] Research assistant agent with 4 tools
- [ ] Task suite of ~30 tasks with expected tool DAG, answer, and citations
- [ ] Trace recorder (JSONL) and `harness run` CLI
- [ ] `pytest` passes offline with the `mock` backend

## Stretch

- [ ] Embedding retrieval alongside BM25
- [ ] Run a second model end to end for a first comparison

## Components

All code lives in `series/ai-eval/harness/` as an installable package (`harness`).

### 1. Model registry (`models.yaml`, `harness/models.py`)

- One function, `complete(model_name, messages, tools) -> Response`, backed by LiteLLM.
- `mock` backend: replays recorded fixtures keyed by task ID and step; it never touches the network. It must be able to produce both correct runs and specific failure runs (wrong tool, hallucinated argument, missing citation), so later labs have known-bad traces to grade.
- Missing key: raise an error naming the env var. Missing Ollama: an error suggesting `ollama pull <model>`.

**Done when:** `complete("mock", ...)` works offline, and `complete("local-llama", ...)` works with Ollama running.

### 2. Corpus (`corpus/`)

- About 40 US federal AI publications, generally public domain. Start with NIST: AI RMF 1.0 (NIST AI 100-1), the Generative AI Profile (NIST AI 600-1), and the adversarial ML taxonomy (NIST AI 100-2), then add related NIST and other agency publications.
- `corpus/manifest.yaml` records, for every document: `doc_id`, title, publisher, year, source URL, license note, and SHA-256 of the raw file. Exclude any document whose reuse terms are unclear.
- `scripts/build_corpus.py` downloads the raw files (kept out of git), extracts text, splits by heading into sections (`section_id`, heading, text), and writes `corpus/sections.jsonl`, which *is* committed so tests run offline.
- BM25 index built at load time (e.g. `rank-bm25`), so there's no index file to manage.

**Done when:** `sections.jsonl` has ~40 docs with clean section headings, and every doc has a manifest entry.

### 3. Tools (`harness/tools.py`)

Strict pydantic schemas. Unknown IDs return a structured error rather than raising; that error is what Lab 01 detects as a hallucinated parameter.

| Tool | Args | Returns |
|---|---|---|
| `search_corpus` | `query: str`, `k: int = 5` (1-10) | `[{doc_id, title, section_id, snippet, score}]` |
| `list_sections` | `doc_id: str` | `[{section_id, heading}]` |
| `read_document` | `doc_id: str`, `section_id: str` | `{doc_id, section_id, heading, text}` |
| `submit_answer` | `answer: str`, `citations: [{doc_id, section_id}]`, `abstain: bool = False` | ends the run |

The agent loop stops at `submit_answer`, or after `max_steps` (default 12), which is recorded as a failure.

### 4. Task suite (`tasks/*.yaml`)

About 30 tasks across four types:

| Type | Count | Example |
|---|---|---|
| `lookup` | 10 | What are the four core functions in the AI RMF? |
| `multi_hop` | 8 | Which risk category in the GenAI Profile maps to the RMF function that covers ongoing monitoring? |
| `compare` | 6 | How do two documents define "red-teaming" differently? |
| `unanswerable` | 6 | A question the corpus can't answer; the correct behavior is to abstain |

Task schema:

```yaml
id: lookup-001
type: lookup
question: What are the four core functions of the NIST AI RMF?
expected:
  answer_contains: [Govern, Map, Measure, Manage]
  abstain: false
  citations:                  # at least one must be cited
    - {doc_id: nist-ai-100-1, section_id: "5"}
  required_steps:             # partial order; Lab 01 grades against this
    - {tool: search_corpus}
    - {tool: read_document, args: {doc_id: nist-ai-100-1}}
    - {tool: submit_answer}
tags: [smoke]
```

Tag 5 tasks `smoke` for quick runs.

**Done when:** all tasks validate against the schema, and every cited `doc_id`/`section_id` exists in `sections.jsonl`.

### 5. Traces (`harness/trace.py`)

One JSONL file per run in `traces/<run_id>.jsonl`, one line per step:

```json
{"schema_version": 1, "run_id": "2026-11-03T14-02-11_mock", "task_id": "lookup-001",
 "step": 2, "type": "tool_call", "model": "mock", "tool": "read_document",
 "args": {"doc_id": "nist-ai-100-1", "section_id": "5"}, "output": {"heading": "..."},
 "error": null, "latency_ms": 3, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
 "ts": "2026-11-03T14:02:11.204Z"}
```

`type` is one of `llm_call`, `tool_call`, `final`. Add a run summary line (`type: run_summary`) with total steps, tokens, cost, latency, and outcome. Commit a few small `mock` traces as fixtures; keep real-model traces out of git, or under `demo/` when they're used in a write-up.

### 6. CLI

```bash
uv run harness run --model mock --tasks smoke
uv run harness run --model local-llama --tasks all --out traces/
uv run harness show traces/<run_id>.jsonl      # pretty-print one run
uv run harness check                           # validate tasks + corpus references
```

## Tests (offline)

- Tool schemas reject bad args, and unknown IDs return structured errors
- The `mock` model produces a correct run and each scripted failure run for a smoke task
- Every task validates, and all referenced citations exist
- Trace files round-trip through the pydantic model

## Out of scope for Lab 00

Scoring, graders, judges, and statistics. Those are Labs 01-03. Lab 00 only needs to produce clean traces.

## Demo

A 60-second terminal recording: `harness run --model local-llama --tasks smoke`, then `harness show` on one trace.

## Deliverables

- [ ] Code + tests in `series/ai-eval/harness/`
- [ ] Demo in `demo/`
- [ ] Write-up: "Building the subject: a research agent worth evaluating"
- [ ] Update posted in #dsi-ai-labs
