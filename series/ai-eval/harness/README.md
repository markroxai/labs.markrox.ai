# AI Eval harness: the system under test

A research assistant agent over a public-domain corpus. Every lab in the AI Eval series evaluates this agent, so no lab starts from scratch. Full spec: [Lab 00](../00-setup/README.md).

## Layout

```
models.yaml        model registry (mock, local, hosted); chosen with --model
corpus/            manifest.yaml + sections.jsonl (public-domain US federal AI publications)
tasks/             ~30 tasks: lookup, multi_hop, compare, unanswerable
src/harness/       models.py, tools.py, agent.py, trace.py, cli.py
traces/            run output (JSONL); only small mock fixtures are committed
tests/             offline tests using the mock backend
```

## Tools

`search_corpus`, `list_sections`, `read_document`, `submit_answer`. Unknown IDs return structured errors, which Lab 01 uses to detect hallucinated parameters.

## Trace schema

Schema version **1**, defined in `src/harness/trace.py`. Labs 01, 09, 10, 11, and 12 depend on it. Any change bumps the version and gets a changelog entry here.

## Changelog

- v1: initial schema
