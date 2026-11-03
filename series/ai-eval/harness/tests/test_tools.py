import pytest

from harness.tools import ErrorCode, execute_tool, tool_specs


def test_tool_specs_cover_all_four_tools():
    names = [spec["function"]["name"] for spec in tool_specs()]
    assert names == ["search_corpus", "list_sections", "read_document", "submit_answer"]
    search = tool_specs()[0]["function"]["parameters"]
    assert search["properties"]["k"]["maximum"] == 10
    assert search["additionalProperties"] is False


def test_search_returns_hits(corpus):
    result = execute_tool(corpus, "search_corpus", {"query": "four functions govern", "k": 3})
    assert result.error is None
    assert result.output[0]["doc_id"] == "nist-ai-100-1"
    assert result.output[0]["section_id"] == "5"
    assert set(result.output[0]) == {"doc_id", "title", "section_id", "snippet", "score"}


@pytest.mark.parametrize(
    ("name", "args", "field"),
    [
        ("search_corpus", {"query": "x", "k": 0}, "k"),
        ("search_corpus", {"query": "x", "k": 11}, "k"),
        ("search_corpus", {"query": "x", "k": "5"}, "k"),  # strict: no string coercion
        ("search_corpus", {"query": ""}, "query"),
        ("search_corpus", {"query": "x", "top_k": 3}, "top_k"),  # unknown field
        ("read_document", {"doc_id": "nist-ai-100-1"}, "section_id"),  # missing field
        (
            "submit_answer",
            {"answer": "a", "citations": [{"doc_id": "d"}]},
            "citations.0.section_id",
        ),
    ],
)
def test_bad_args_return_invalid_args(corpus, name, args, field):
    result = execute_tool(corpus, name, args)
    assert result.output is None
    assert result.error.code == ErrorCode.INVALID_ARGS
    assert result.error.field == field
    assert not result.ends_run


def test_unknown_tool(corpus):
    result = execute_tool(corpus, "web_search", {"query": "x"})
    assert result.error.code == ErrorCode.UNKNOWN_TOOL
    assert result.error.value == "web_search"


@pytest.mark.parametrize("tool", ["list_sections", "read_document"])
def test_unknown_doc_id_is_structured_error(corpus, tool):
    args = {"doc_id": "nist-ai-rmf-2.0"}
    if tool == "read_document":
        args["section_id"] = "5"
    result = execute_tool(corpus, tool, args)
    assert result.error.code == ErrorCode.UNKNOWN_DOC_ID
    assert result.error.field == "doc_id"
    assert result.error.value == "nist-ai-rmf-2.0"


def test_unknown_section_id_is_structured_error(corpus):
    result = execute_tool(corpus, "read_document", {"doc_id": "nist-ai-100-1", "section_id": "99"})
    assert result.error.code == ErrorCode.UNKNOWN_SECTION_ID
    assert result.error.value == "99"


def test_list_sections_and_read_document(corpus):
    listed = execute_tool(corpus, "list_sections", {"doc_id": "nist-ai-100-1"})
    assert listed.output == [
        {"section_id": "1", "heading": "Framing risk"},
        {"section_id": "5", "heading": "AI RMF Core"},
    ]
    read = execute_tool(corpus, "read_document", {"doc_id": "nist-ai-100-1", "section_id": "5"})
    assert read.output["heading"] == "AI RMF Core"
    assert "Govern" in read.output["text"]


def test_submit_answer_ends_run(corpus):
    result = execute_tool(
        corpus,
        "submit_answer",
        {
            "answer": "Govern, Map, Measure, Manage",
            "citations": [{"doc_id": "nist-ai-100-1", "section_id": "5"}],
        },
    )
    assert result.ends_run
    assert result.output["abstain"] is False
    assert result.output["citations"] == [{"doc_id": "nist-ai-100-1", "section_id": "5"}]


def test_abstain(corpus):
    result = execute_tool(corpus, "submit_answer", {"answer": "", "abstain": True})
    assert result.ends_run and result.output["abstain"] is True
