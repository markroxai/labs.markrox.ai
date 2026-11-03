# AI Eval harness: the system under test

A research assistant agent over a public-domain corpus. Every lab in the AI Eval series evaluates this agent, so no lab starts from scratch. Full spec: [Lab 00](../00-setup/README.md).

## Layout

```
models.yaml        model registry (mock, local, hosted); chosen with --model
corpus/            manifest.yaml + sections.jsonl (public-domain US federal AI publications)
scripts/           build_corpus.py
tasks/             ~30 tasks: lookup, multi_hop, compare, unanswerable
fixtures/mock/     scripted mock runs, one YAML per task
src/harness/       models.py, tools.py, agent.py, trace.py, cli.py
traces/            run output (JSONL); only small mock fixtures are committed
tests/             offline tests using the mock backend
```

## Corpus

41 U.S. federal AI publications (NIST, OMB, executive orders, FDA, DHS, NTIA, Treasury, Copyright Office, USPTO, NASA, OSTP/NSTC), split into 1,172 sections. `corpus/manifest.yaml` records each document's source URL, publisher, year, license note, and SHA-256. `corpus/sections.jsonl` is committed so tests run offline; raw PDFs in `corpus/raw/` are not.

```bash
uv run --group corpus python scripts/build_corpus.py                 # download missing PDFs, verify hashes, rebuild
uv run --group corpus python scripts/build_corpus.py --write-hashes  # after adding a document
```

Sections come from the PDF outline when it has one, otherwise from numbered headings in the text (accepted only if they continue a valid 1, 1.1, 2 ... sequence), otherwise one section per page. Sections over 2,500 words are split into parts (`4.7`, `4.7-p2`, ...). Search is BM25 (`harness.corpus.BM25`), built in memory at load (about 0.2 s).

**Licensing.** Every document is a U.S. Government work (17 U.S.C. 105). Five NIST publications list non-federal co-authors (NIST AI 100-2 e2023 and e2025, SP 1270, SP 800-226, IR 8596); their license notes say so.

**Excluded:** GAO, DoD, HHS, Education, Senate, and CFPB sources block scripted downloads, so they can't be rebuilt reliably. Withdrawn NIST drafts, the superseded first draft of NIST AI 800-1, the FRVT face-recognition reports (mostly figures), and the House AI Task Force report (published PDF still has template placeholders) were also left out.

**Known limitations:** the AI Bill of Rights blueprint and the NASA framework have unnumbered headings and are split by page (`p1`, `p2`, ...). A few documents split on numbered headings have coarse sections (USPTO 2020 report: 5 sections).

## Mock backend

`complete("mock", messages, tools, task_id=..., scenario=...)` replays `fixtures/mock/<task_id>.yaml`, one turn per step (step = assistant turns so far). It never touches the network. Each fixture has a `correct` scenario plus known-bad ones for later labs to catch: `wrong_tool`, `hallucinated_arg`, `missing_citation`.

## Tools

`search_corpus`, `list_sections`, `read_document`, `submit_answer`. Unknown IDs return structured errors, which Lab 01 uses to detect hallucinated parameters.

## Trace schema

Schema version **1**, defined in `src/harness/trace.py`. Labs 01, 09, 10, 11, and 12 depend on it. Any change bumps the version and gets a changelog entry here.

## Changelog

- v1: initial schema
