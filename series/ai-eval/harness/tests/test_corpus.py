"""Checks on the committed corpus (manifest.yaml + sections.jsonl) and on BM25 search."""

from collections import Counter

import pytest

from harness.corpus import BM25, load_corpus, load_manifest, load_sections, snippet, tokenize
from harness.models import complete
from harness.sectioning import MAX_SECTION_WORDS
from harness.tools import ErrorCode, execute_tool, tool_specs


@pytest.fixture(scope="module")
def manifest():
    return load_manifest()


@pytest.fixture(scope="module")
def sections():
    return load_sections()


def test_manifest_is_complete(manifest):
    ids = [d.doc_id for d in manifest.documents]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 35
    for doc in manifest.documents:
        assert doc.source_url.scheme == "https"
        assert len(doc.sha256) == 64, f"{doc.doc_id} has no SHA-256; run --write-hashes"
        assert "17 U.S.C. 105" in doc.license_note


def test_sections_match_manifest(manifest, sections):
    assert {s.doc_id for s in sections} == {d.doc_id for d in manifest.documents}
    keys = Counter((s.doc_id, s.section_id) for s in sections)
    assert [k for k, n in keys.items() if n > 1] == []
    per_doc = Counter(s.doc_id for s in sections)
    assert min(per_doc.values()) >= 3


def test_sections_are_clean(sections):
    for s in sections:
        assert s.text.strip() and s.heading.strip()
        # one sentence can push a part past the cap; anything far over means splitting failed
        assert len(s.text.split()) <= MAX_SECTION_WORDS * 1.2, (s.doc_id, s.section_id)


def test_known_anchor_sections(sections):
    by_key = {(s.doc_id, s.section_id): s for s in sections}
    rmf_core = by_key[("nist-ai-100-1", "5")]
    for function in ["GOVERN", "MAP", "MEASURE", "MANAGE"]:
        assert function in rmf_core.text
    assert ("eo-14110", "sec-1") in by_key
    assert ("nist-ai-100-2e2025", "4.2.6") in by_key


def test_bm25_ranks_by_term_overlap():
    index = BM25([["red", "team"], ["data", "poisoning", "attack"], ["poisoning", "poisoning"]])
    assert index.score(["unrelated"], 0) == 0.0
    ranked = index.top_k(["poisoning", "attack"], k=3)
    assert ranked[0][0] == 1
    assert {i for i, _ in ranked} == {1, 2}


def test_tokenize_keeps_hyphenated_terms_and_drops_stopwords():
    assert tokenize("What is red-teaming in the AI RMF?") == ["red-teaming", "ai", "rmf"]


def test_snippet_centers_on_match():
    text = "filler " * 100 + "watermarking is robust"
    assert "watermarking" in snippet(text, ["watermarking"], width=80)


def test_search_over_real_corpus():
    hits = load_corpus().search("four core functions of the AI RMF", 3)
    assert (hits[0].doc_id, hits[0].section_id) == ("nist-ai-100-1", "5")


def test_tools_over_real_corpus():
    corpus = load_corpus()
    listed = execute_tool(corpus, "list_sections", {"doc_id": "nist-ai-100-1"})
    assert {"section_id": "5", "heading": "5 AI RMF Core"} in listed.output
    missing = execute_tool(corpus, "read_document", {"doc_id": "nist-ai-100-1", "section_id": "9"})
    assert missing.error.code == ErrorCode.UNKNOWN_SECTION_ID


@pytest.mark.parametrize(
    ("scenario", "errors"),
    [("correct", []), ("hallucinated_arg", [ErrorCode.UNKNOWN_DOC_ID])],
)
def test_mock_lookup_001_against_real_corpus(scenario, errors):
    corpus = load_corpus()
    messages = [{"role": "user", "content": "What are the four core functions of the AI RMF?"}]
    seen = []
    for _ in range(12):
        response = complete("mock", messages, tool_specs(), task_id="lookup-001", scenario=scenario)
        messages.append(response.to_message())
        call = response.tool_calls[0]
        result = execute_tool(corpus, call.name, call.args)
        if result.error:
            seen.append(result.error.code)
        messages.append(
            {"role": "tool", "tool_call_id": call.id, "content": result.model_dump_json()}
        )
        if result.ends_run:
            break
    assert seen == errors
