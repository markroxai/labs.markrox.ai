"""The corpus: manifest, sections, and BM25 search.

`corpus/manifest.yaml` lists every document and where it came from. `corpus/sections.jsonl`
holds the extracted sections (built by `scripts/build_corpus.py`, committed so tests run
offline). The BM25 index is built in memory at load time, so there is no index file.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from harness.tools import SearchHit, Section

HARNESS_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS_DIR = HARNESS_ROOT / "corpus"

# --- Manifest -------------------------------------------------------------------------


class DocMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]*$")
    title: str
    publisher: str
    year: int = Field(ge=1990, le=2100)
    source_url: HttpUrl
    license_note: str = Field(min_length=10)
    sha256: str = Field(default="", pattern=r"^([0-9a-f]{64})?$")
    line_numbers: bool = False  # the PDF prints draft line numbers that extraction must strip


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: list[DocMeta]


def load_manifest(corpus_dir: Path = DEFAULT_CORPUS_DIR) -> Manifest:
    return Manifest.model_validate(yaml.safe_load((corpus_dir / "manifest.yaml").read_text()))


def load_sections(corpus_dir: Path = DEFAULT_CORPUS_DIR) -> list[Section]:
    with (corpus_dir / "sections.jsonl").open() as f:
        return [Section.model_validate(json.loads(line)) for line in f if line.strip()]


# --- BM25 -------------------------------------------------------------------------------

STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the this to was "
    "were which with what how do does which who whom".split()
)


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens (hyphenated terms kept whole), minus stopwords."""
    return [t for t in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower()) if t not in STOPWORDS]


class BM25:
    """Okapi BM25 over pre-tokenized documents.

    `score(query, i)` is the sum over query terms t of
    idf(t) * f(t,i) * (k1 + 1) / (f(t,i) + k1 * (1 - b + b * len_i / avg_len)),
    with idf(t) = ln(1 + (N - n_t + 0.5) / (n_t + 0.5)). Range: [0, inf); 0 means no term
    overlap. Scores are comparable only within one corpus.
    """

    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.term_freqs = [Counter(doc) for doc in docs]
        self.lengths = [len(doc) for doc in docs]
        self.avg_len = sum(self.lengths) / len(docs) if docs else 0.0
        doc_freq: Counter[str] = Counter()
        for tf in self.term_freqs:
            doc_freq.update(tf.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in doc_freq.items()}

    def score(self, query: list[str], i: int) -> float:
        tf, norm = self.term_freqs[i], 1 - self.b + self.b * self.lengths[i] / self.avg_len
        total = 0.0
        for term in query:
            if f := tf.get(term):
                total += self.idf[term] * f * (self.k1 + 1) / (f + self.k1 * norm)
        return total

    def top_k(self, query: list[str], k: int) -> list[tuple[int, float]]:
        scored = [(i, self.score(query, i)) for i in range(len(self.term_freqs))]
        scored = [pair for pair in scored if pair[1] > 0]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))  # ties broken by corpus order
        return scored[:k]


def snippet(text: str, query: list[str], width: int = 240) -> str:
    """About `width` characters of text around the first query-term match."""
    lowered = text.lower()
    hits = [m.start() for t in query if (m := re.search(rf"\b{re.escape(t)}\b", lowered))]
    start = max(0, min(hits) - width // 4) if hits else 0
    clip = " ".join(text[start : start + width].split())
    return ("..." if start else "") + clip + ("..." if start + width < len(text) else "")


# --- Corpus -------------------------------------------------------------------------------


class LocalCorpus:
    """Implements `tools.Corpus` over sections.jsonl."""

    def __init__(self, sections: list[Section], titles: dict[str, str]) -> None:
        self._sections = sections
        self._titles = titles
        self._by_doc: dict[str, list[Section]] = {}
        for section in sections:
            self._by_doc.setdefault(section.doc_id, []).append(section)
        self._index = BM25([tokenize(f"{s.heading} {s.text}") for s in sections])

    @property
    def doc_ids(self) -> list[str]:
        return list(self._by_doc)

    def search(self, query: str, k: int) -> list[SearchHit]:
        terms = tokenize(query)
        return [
            SearchHit(
                doc_id=(s := self._sections[i]).doc_id,
                title=self._titles.get(s.doc_id, s.doc_id),
                section_id=s.section_id,
                snippet=snippet(s.text, terms),
                score=round(score, 4),
            )
            for i, score in self._index.top_k(terms, k)
        ]

    def sections(self, doc_id: str) -> list[Section] | None:
        return self._by_doc.get(doc_id)


@cache
def load_corpus(corpus_dir: Path = DEFAULT_CORPUS_DIR) -> LocalCorpus:
    """Load sections and build the index. Cached: one build per process."""
    titles = {d.doc_id: d.title for d in load_manifest(corpus_dir).documents}
    return LocalCorpus(load_sections(corpus_dir), titles)
