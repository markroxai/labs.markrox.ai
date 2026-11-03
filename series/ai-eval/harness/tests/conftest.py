"""Shared test fixtures. The corpus here is synthetic; the real one is built in component 2."""

import pytest

from harness.tools import SearchHit, Section

FAKE_SECTIONS = [
    Section(
        doc_id="nist-ai-100-1",
        section_id="1",
        heading="Framing risk",
        text="Synthetic text about framing AI risk and trustworthiness.",
    ),
    Section(
        doc_id="nist-ai-100-1",
        section_id="5",
        heading="AI RMF Core",
        text="Synthetic text: the core is organized into four functions, "
        "Govern, Map, Measure, and Manage.",
    ),
    Section(
        doc_id="nist-ai-600-1",
        section_id="2",
        heading="Overview of risks",
        text="Synthetic text listing generative AI risks such as confabulation.",
    ),
]
TITLES = {"nist-ai-100-1": "AI RMF 1.0", "nist-ai-600-1": "Generative AI Profile"}


class FakeCorpus:
    """Implements the tools.Corpus protocol with naive term-overlap scoring."""

    def search(self, query: str, k: int) -> list[SearchHit]:
        terms = set(query.lower().split())
        scored = [
            (len(terms & set(s.text.lower().replace(",", " ").split())), s) for s in FAKE_SECTIONS
        ]
        scored = [(score, s) for score, s in scored if score > 0]
        scored.sort(key=lambda pair: -pair[0])
        return [
            SearchHit(
                doc_id=s.doc_id,
                title=TITLES[s.doc_id],
                section_id=s.section_id,
                snippet=s.text[:80],
                score=float(score),
            )
            for score, s in scored[:k]
        ]

    def sections(self, doc_id: str) -> list[Section] | None:
        found = [s for s in FAKE_SECTIONS if s.doc_id == doc_id]
        return found or None


@pytest.fixture
def corpus() -> FakeCorpus:
    return FakeCorpus()
