"""Model registry and the single model client.

Every model call in the series goes through `complete(model_name, messages, tools)`.
Models are chosen by name from `models.yaml`:

- `mock`: replays recorded fixtures from `fixtures/mock/<task_id>.yaml`; never touches the network
- `local-*`: Ollama via LiteLLM, no key needed
- hosted: LiteLLM, with the key read from the env var named by `key_env`
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

HARNESS_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = HARNESS_ROOT / "models.yaml"
DEFAULT_FIXTURES = HARNESS_ROOT / "fixtures" / "mock"
DEFAULT_OLLAMA_BASE = "http://localhost:11434"

Message = dict[str, Any]


class ModelError(RuntimeError):
    """Base class for registry and backend errors."""


class UnknownModelError(ModelError):
    pass


class MissingKeyError(ModelError):
    pass


class OllamaUnavailableError(ModelError):
    pass


class MockFixtureError(ModelError):
    pass


# --- Registry -----------------------------------------------------------------


class Cost(BaseModel):
    """USD per 1M tokens. None means unknown; cost is then reported as None."""

    input: float | None = None
    output: float | None = None


class ModelEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    provider: str
    model: str | None = None
    key_env: str | None = None
    api_base_env: str | None = None
    api_version_env: str | None = None
    cost: Cost = Field(default_factory=Cost)
    notes: str | None = None


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, ModelEntry]:
    raw = yaml.safe_load(path.read_text())
    return {name: ModelEntry(name=name, **fields) for name, fields in raw["models"].items()}


def get_model(model_name: str, registry_path: Path = DEFAULT_REGISTRY) -> ModelEntry:
    registry = load_registry(registry_path)
    if model_name not in registry:
        known = ", ".join(sorted(registry))
        raise UnknownModelError(f"Unknown model '{model_name}'. Known models: {known}")
    return registry[model_name]


# --- Response -----------------------------------------------------------------


class ToolCall(BaseModel):
    id: str
    name: str
    args: dict[str, Any]


class Response(BaseModel):
    """One model turn, plus the bookkeeping every trace records."""

    model: str
    provider: str
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    cost_usd: float | None = None

    def to_message(self) -> Message:
        """The assistant message to append to the conversation (OpenAI format)."""
        message: Message = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": json.dumps(call.args)},
                }
                for call in self.tool_calls
            ]
        return message


def estimate_cost(cost: Cost, tokens_in: int, tokens_out: int) -> float | None:
    """Estimated USD for one call from per-1M-token prices; None if either price is unknown."""
    if cost.input is None or cost.output is None:
        return None
    return (tokens_in * cost.input + tokens_out * cost.output) / 1_000_000


# --- Mock backend ---------------------------------------------------------------


class MockTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class MockFixture(BaseModel):
    """Scripted runs for one task. Each scenario is a list of turns, one per model step."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    scenarios: dict[str, list[MockTurn]]


def load_fixture(task_id: str, fixtures_dir: Path = DEFAULT_FIXTURES) -> MockFixture:
    path = fixtures_dir / f"{task_id}.yaml"
    if not path.exists():
        raise MockFixtureError(f"No mock fixture for task '{task_id}' (expected {path})")
    return MockFixture.model_validate(yaml.safe_load(path.read_text()))


def mock_step(messages: list[Message]) -> int:
    """The step to replay: the number of assistant turns already in the conversation."""
    return sum(1 for m in messages if m.get("role") == "assistant")


def _complete_mock(
    entry: ModelEntry,
    messages: list[Message],
    task_id: str | None,
    scenario: str,
    fixtures_dir: Path,
) -> Response:
    if task_id is None:
        raise MockFixtureError("The mock model needs a task_id to choose a fixture")
    fixture = load_fixture(task_id, fixtures_dir)
    if scenario not in fixture.scenarios:
        known = ", ".join(sorted(fixture.scenarios))
        raise MockFixtureError(
            f"Task '{task_id}' has no mock scenario '{scenario}'. Known scenarios: {known}"
        )
    turns = fixture.scenarios[scenario]
    step = mock_step(messages)
    if step >= len(turns):
        raise MockFixtureError(
            f"Mock scenario '{task_id}/{scenario}' has {len(turns)} turns; step {step} requested"
        )
    turn = turns[step]
    calls = [
        ToolCall(id=f"mock-{step}-{i}", name=c["name"], args=c.get("args", {}))
        for i, c in enumerate(turn.tool_calls)
    ]
    return Response(
        model=entry.name,
        provider=entry.provider,
        content=turn.content,
        tool_calls=calls,
        cost_usd=0.0,
    )


# --- LiteLLM backends ---------------------------------------------------------------


def _litellm_kwargs(entry: ModelEntry) -> dict[str, Any]:
    """Resolve key, base URL, and API version from env vars named in the registry."""
    if entry.model is None or "<" in entry.model:
        raise ModelError(
            f"Model '{entry.name}' has no model ID set in models.yaml (got '{entry.model}')"
        )
    kwargs: dict[str, Any] = {"model": entry.model}
    if entry.key_env:
        key = os.environ.get(entry.key_env)
        if not key:
            raise MissingKeyError(
                f"Model '{entry.name}' needs an API key: set {entry.key_env} in your environment "
                f"or .env"
            )
        kwargs["api_key"] = key
    if entry.api_base_env:
        base = os.environ.get(entry.api_base_env)
        if base:
            kwargs["api_base"] = base
        elif entry.provider == "ollama":
            kwargs["api_base"] = DEFAULT_OLLAMA_BASE
        else:
            raise MissingKeyError(
                f"Model '{entry.name}' needs a base URL: set {entry.api_base_env}"
            )
    if entry.api_version_env:
        version = os.environ.get(entry.api_version_env)
        if not version:
            raise MissingKeyError(
                f"Model '{entry.name}' needs an API version: set {entry.api_version_env}"
            )
        kwargs["api_version"] = version
    return kwargs


def _ollama_hint(entry: ModelEntry, api_base: str, exc: Exception) -> OllamaUnavailableError:
    tag = entry.model.removeprefix("ollama/") if entry.model else "<model>"
    return OllamaUnavailableError(
        f"Could not run '{entry.name}' on Ollama at {api_base}: {exc}\n"
        f"Start Ollama (`ollama serve`) and pull the model: `ollama pull {tag}`"
    )


def _complete_litellm(
    entry: ModelEntry, messages: list[Message], tools: list[dict[str, Any]] | None
) -> Response:
    # Costs come from models.yaml; stop LiteLLM fetching its price map over the network.
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    import litellm  # imported lazily: slow to import, and mock runs never need it

    kwargs = _litellm_kwargs(entry)
    if tools:
        kwargs["tools"] = tools
        # LiteLLM >=1.106 routes any tools= call through its MCP gateway check, which imports
        # the undeclared `mcp` package. We never use MCP tools, so skip that path.
        kwargs["_skip_mcp_handler"] = True
    start = time.perf_counter()
    try:
        result = litellm.completion(messages=messages, **kwargs)
    except (litellm.APIConnectionError, litellm.NotFoundError) as exc:
        if entry.provider == "ollama":
            raise _ollama_hint(entry, kwargs["api_base"], exc) from exc
        raise
    latency_ms = round((time.perf_counter() - start) * 1000)

    message = result.choices[0].message
    calls = [
        ToolCall(
            id=call.id,
            name=call.function.name,
            args=json.loads(call.function.arguments or "{}"),
        )
        for call in (message.tool_calls or [])
    ]
    usage = getattr(result, "usage", None)
    tokens_in = getattr(usage, "prompt_tokens", 0) or 0
    tokens_out = getattr(usage, "completion_tokens", 0) or 0
    return Response(
        model=entry.name,
        provider=entry.provider,
        content=message.content,
        tool_calls=calls,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        cost_usd=estimate_cost(entry.cost, tokens_in, tokens_out),
    )


# --- Public entry point -------------------------------------------------------------


def complete(
    model_name: str,
    messages: list[Message],
    tools: list[dict[str, Any]] | None = None,
    *,
    task_id: str | None = None,
    scenario: str = "correct",
    registry_path: Path = DEFAULT_REGISTRY,
    fixtures_dir: Path = DEFAULT_FIXTURES,
) -> Response:
    """Run one model turn.

    `task_id` and `scenario` are used only by the mock backend, which replays the turn for
    the current step (the number of assistant messages so far) from the task's fixture.
    """
    entry = get_model(model_name, registry_path)
    if entry.provider == "mock":
        start = time.perf_counter()
        response = _complete_mock(entry, messages, task_id, scenario, fixtures_dir)
        response.latency_ms = round((time.perf_counter() - start) * 1000)
        return response
    return _complete_litellm(entry, messages, tools)
