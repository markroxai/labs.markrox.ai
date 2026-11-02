# AI Eval harness: the system under test

Every lab in the AI Eval series evaluates this shared reference agent, so no lab starts from scratch.

## Lab 00 builds

- `agent/`: a small tool-using agent with swappable model backends
- `tools/`: 3-4 mock tools (e.g. search, calculator, order lookup, ticket create) with strict schemas
- `corpus/`: a small public-domain document set for RAG
- `tasks/`: ~30 synthetic tasks, each with expected tool-call DAG and expected answer
- `traces/`: recorded runs (JSONL) that later labs grade, replay, and compare

## Trace format (draft)

One JSON object per step:

```json
{"run_id": "...", "step": 3, "type": "tool_call", "tool": "order_lookup",
 "args": {"order_id": "A-1001"}, "output": {...}, "latency_ms": 412, "tokens": {"in": 812, "out": 64}}
```

Keep this format stable: labs 01, 09, 10, 11, and 12 depend on it.
