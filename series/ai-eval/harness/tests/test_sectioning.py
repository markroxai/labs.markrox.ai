from harness.sectioning import (
    Heading,
    OutlineEntry,
    clean_pages,
    headings_from_outline,
    headings_from_text,
    join_pages,
    normalize,
    section_id_for,
    sections_from_headings,
    split_document,
    split_long,
    strip_line_numbers,
    unwrap,
)
from harness.tools import Section


def test_normalize_fixes_ligatures_and_spacing():
    assert normalize("Artiﬁcial   Intelligence\n\n\n\nRisk") == "Artificial Intelligence\n\nRisk"


def test_strip_line_numbers_leading_trailing_and_alone():
    text = "12 Risks are scoped\nto public safety 13\n14\nnext line"
    assert strip_line_numbers(text) == "Risks are scoped\nto public safety\nnext line"


def test_unwrap_rejoins_hyphenation_and_wrapped_lines():
    assert unwrap("AML at-\ntacks on\nmodels.\nNext para") == "AML attacks on models.\nNext para"
    assert unwrap("risk-\nBased") == "risk- Based"  # only lowercase continuations are joined


def test_clean_pages_drops_repeated_headers():
    bodies = ["Govern", "Map", "Measure", "Manage", "Profiles"]
    pages = [f"NIST AI 100-1 page {i}\nThis publication is free\n{b}" for i, b in enumerate(bodies)]
    assert clean_pages(pages) == bodies


def test_section_ids():
    assert section_id_for("5. AI RMF Core") == "5"
    assert section_id_for("3.1.2 Metadata Recording") == "3.1.2"
    assert section_id_for("Sec. 4. Ensuring Safety") == "sec-4"
    assert section_id_for("Appendix B: How AI Risks Differ") == "appendix-b"
    assert section_id_for("A.1.6 Information Integrity") == "A.1.6"
    assert section_id_for("Executive Summary") == "executive-summary"


def test_text_headings_follow_numbering_sequence():
    text = "\n".join(
        [
            "1 Summary .......... 3",  # ToC line
            "1. Overview",
            "Body text.",
            "1. Review planned acquisitions",  # list item restarts at 1
            "50 U.S.C. 4501 et seq.",  # footnote
            "2. Scope",
            "2.1 Covered Agencies",
            "3. Requirements. Agencies must do things.",  # inline heading
        ]
    )
    titles = [h.title for h in headings_from_text(text)]
    assert titles == ["1 Overview", "2 Scope", "2.1 Covered Agencies", "3 Requirements"]


def test_executive_order_section_headings():
    text = "Section 1 . Purpose. AI promises growth.\nSec. 2. Policy and Principles. It is policy."
    assert [h.title for h in headings_from_text(text)] == [
        "Sec. 1. Purpose",
        "Sec. 2. Policy and Principles",
    ]


def test_outline_headings_prefer_numbered_occurrence():
    pages = ["GOVERN\nFigure label text\n5.1 Govern\nGovern body text here."]
    text, starts = join_pages(pages)
    [heading] = headings_from_outline([OutlineEntry(title="Govern", page=0)], text, starts)
    assert heading.title == "5.1 Govern"
    assert text[heading.offset :].startswith("5.1 Govern")


def test_sections_from_headings_strips_heading_and_dedupes_ids():
    text = "Cover page words here and more\n1 Intro\none two three four five\n1 Intro\na b c d e f"
    first = text.index("1 Intro")
    headings = [
        Heading(title="1 Intro", offset=first),
        Heading(title="1 Intro", offset=text.index("1 Intro", first + 1)),
    ]
    sections = sections_from_headings("doc", text, headings)
    assert [s.section_id for s in sections] == ["front", "1", "1-2"]
    assert sections[1].text == "one two three four five"


def test_split_long_keeps_first_id():
    section = Section(doc_id="d", section_id="4.7", heading="4.7 Refs", text="One two. " * 30)
    parts = split_long(section, max_words=20)
    assert [p.section_id for p in parts] == ["4.7", "4.7-p2", "4.7-p3"]
    assert parts[1].heading == "4.7 Refs (part 2)"
    assert all(len(p.text.split()) <= 20 for p in parts)


def test_split_document_falls_back_to_pages():
    pages = ["Plain prose without any numbered headings at all.", "More plain prose on page two."]
    sections, method = split_document("doc", pages, outline=[])
    assert method == "page"
    assert [s.section_id for s in sections] == ["p1", "p2"]
    assert sections[0].heading.startswith("Page 1: Plain prose")
