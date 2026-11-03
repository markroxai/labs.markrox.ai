import json
from pathlib import Path

import pytest

from harness.models import (
    Cost,
    MissingKeyError,
    MockFixtureError,
    OllamaUnavailableError,
    UnknownModelError,
    complete,
    estimate_cost,
    load_registry,
)
from harness.tools import ErrorCode, execute_tool, tool_specs

QUESTION = [{"role": "user", "content": "What are the four core functions of the NIST AI RMF?"}]


def run_mock(corpus, scenario: str, max_steps: int = 12):
    """Minimal agent loop for tests: model turn, execute tools, repeat until submit_answer."""
    messages = list(QUESTION)
    results = []
    for _ in range(max_steps):
        response = complete("mock", messages, tool_specs(), task_id="lookup-001", scenario=scenario)
        messages.append(response.to_message())
        for call in response.tool_calls:
            result = execute_tool(corpus, call.name, call.args)
            results.append(result)
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result.model_dump_json()}
            )
            if result.ends_run:
                return results
    raise AssertionError("run did not end")


def test_registry_loads_all_entries():
    registry = load_registry()
    assert {"mock", "local-llama", "claude"} <= set(registry)
    assert registry["claude"].key_env == "LABS_ANTHROPIC_API_KEY"
    assert registry["mock"].provider == "mock"


def test_unknown_model_lists_known_names():
    with pytest.raises(UnknownModelError, match="local-llama"):
        complete("gpt-99", QUESTION)


def test_mock_correct_run(corpus):
    results = run_mock(corpus, "correct")
    assert [r.tool for r in results] == ["search_corpus", "read_document", "submit_answer"]
    assert all(r.error is None for r in results)
    assert results[-1].output["citations"] == [{"doc_id": "nist-ai-100-1", "section_id": "5"}]


def test_mock_wrong_tool_run(corpus):
    results = run_mock(corpus, "wrong_tool")
    assert "read_document" not in [r.tool for r in results]
    assert results[1].tool == "list_sections"


def test_mock_hallucinated_arg_run(corpus):
    results = run_mock(corpus, "hallucinated_arg")
    assert results[1].error.code == ErrorCode.UNKNOWN_DOC_ID
    assert results[1].error.value == "nist-ai-rmf-2.0"


def test_mock_missing_citation_run(corpus):
    results = run_mock(corpus, "missing_citation")
    assert results[-1].ends_run
    assert results[-1].output["citations"] == []


def test_mock_is_deterministic_and_free():
    first = complete("mock", QUESTION, task_id="lookup-001")
    second = complete("mock", QUESTION, task_id="lookup-001")
    assert first.tool_calls == second.tool_calls
    assert (first.tokens_in, first.tokens_out, first.cost_usd) == (0, 0, 0.0)
    assert first.model == "mock" and first.provider == "mock"


def test_to_message_is_openai_format():
    message = complete("mock", QUESTION, task_id="lookup-001").to_message()
    call = message["tool_calls"][0]
    assert message["role"] == "assistant"
    assert call["function"]["name"] == "search_corpus"
    assert json.loads(call["function"]["arguments"])["query"] == "AI RMF core functions"


def test_mock_errors():
    with pytest.raises(MockFixtureError, match="task_id"):
        complete("mock", QUESTION)
    with pytest.raises(MockFixtureError, match="No mock fixture"):
        complete("mock", QUESTION, task_id="lookup-999")
    with pytest.raises(MockFixtureError, match="Known scenarios"):
        complete("mock", QUESTION, task_id="lookup-001", scenario="nope")
    too_far = QUESTION + [{"role": "assistant", "content": None}] * 3
    with pytest.raises(MockFixtureError, match="step 3"):
        complete("mock", too_far, task_id="lookup-001")


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    path = tmp_path / "models.yaml"
    path.write_text(
        "models:\n"
        "  hosted:\n"
        "    provider: anthropic\n"
        "    model: anthropic/test-model\n"
        "    key_env: LABS_ANTHROPIC_API_KEY\n"
        "    cost: {input: 3, output: 15}\n"
        "  placeholder:\n"
        "    provider: openai\n"
        "    model: openai/<model-id>\n"
        "    key_env: OPENAI_API_KEY\n"
    )
    return path


def test_missing_key_names_env_var(registry, monkeypatch):
    monkeypatch.delenv("LABS_ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(MissingKeyError, match="LABS_ANTHROPIC_API_KEY"):
        complete("hosted", QUESTION, registry_path=registry)


def test_key_is_passed_explicitly(registry, monkeypatch):
    """LiteLLM doesn't know LABS_ANTHROPIC_API_KEY, so the client must pass it through."""
    import litellm

    seen = {}

    def fake_completion(**kwargs):
        seen.update(kwargs)
        raise RuntimeError("stop")

    monkeypatch.setenv("LABS_ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(litellm, "completion", fake_completion)
    with pytest.raises(RuntimeError, match="stop"):
        complete("hosted", QUESTION, registry_path=registry)
    assert seen["api_key"] == "sk-test"
    assert seen["model"] == "anthropic/test-model"


def test_placeholder_model_id_is_rejected(registry):
    with pytest.raises(Exception, match="no model ID"):
        complete("placeholder", QUESTION, registry_path=registry)


def test_ollama_down_suggests_pull(monkeypatch):
    import litellm

    def refuse(**kwargs):
        raise litellm.APIConnectionError(
            message="connection refused", llm_provider="ollama", model=kwargs["model"]
        )

    monkeypatch.delenv("OLLAMA_API_BASE", raising=False)
    monkeypatch.setattr(litellm, "completion", refuse)
    with pytest.raises(OllamaUnavailableError, match=r"ollama pull llama3\.1:8b"):
        complete("local-llama", QUESTION)


def test_estimate_cost():
    assert estimate_cost(Cost(input=3, output=15), 1_000_000, 100_000) == pytest.approx(4.5)
    assert estimate_cost(Cost(input=None, output=15), 10, 10) is None


@pytest.mark.live
def test_local_llama_live():
    response = complete("local-llama", QUESTION, tool_specs())
    assert response.provider == "ollama"
    assert response.tokens_in > 0
    assert response.content or response.tool_calls
