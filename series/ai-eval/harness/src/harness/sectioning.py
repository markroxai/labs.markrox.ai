"""Split extracted PDF text into sections. Pure functions; PDF I/O lives in the build script.

Headings come from the PDF outline (bookmarks) when it has enough entries. Otherwise they
come from numbered heading lines in the text ("Sec. 4.", "2.1 Scope", "III. Guidance").
If neither finds enough headings, the document is split by page.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from pydantic import BaseModel

from harness.tools import Section

MIN_HEADINGS = 3
MIN_SECTION_WORDS = 5
MAX_SECTION_WORDS = 2500
SKIP_HEADINGS = re.compile(
    r"^(table of )?contents$|^list of (figures|tables)$|^figures$|^tables$", re.IGNORECASE
)


class OutlineEntry(BaseModel):
    title: str
    page: int  # 0-based
    depth: int = 0


class Heading(BaseModel):
    title: str
    offset: int  # character offset into the joined document text


# --- Text cleanup -------------------------------------------------------------------


def normalize(text: str) -> str:
    """NFKC (fixes ligatures like "ﬁ"), unify whitespace within lines, drop blank runs."""
    text = unicodedata.normalize("NFKC", text).replace(" ", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def strip_line_numbers(text: str) -> str:
    """Remove draft-style line numbers: a number alone on a line, or separated by a space at
    the start or end of a line. Only for documents flagged `line_numbers` in the manifest."""
    text = re.sub(r"(?m)^\d{1,4}$\n?", "", text)
    text = re.sub(r"(?m) \d{1,4}$", "", text)
    return re.sub(r"(?m)^\d{1,4} (?=\S)", "", text)


def unwrap(text: str) -> str:
    """Undo PDF line wrapping: rejoin words hyphenated across lines ("at-\ntacks"), then
    join wrapped lines. A line break survives only after sentence-ending punctuation."""
    text = re.sub(r"(?<=[a-z])-\n(?=[a-z])", "", text)
    text = re.sub(r"(?<![.:;!?])\n(?!\n)", " ", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def boilerplate_lines(pages: list[str], min_share: float = 0.3) -> set[str]:
    """Lines (ignoring digits) that repeat on at least `min_share` of pages: running headers,
    footers, and "available free of charge" notices."""
    if len(pages) < 4:
        return set()
    counts: Counter[str] = Counter()
    for page in pages:
        counts.update({_line_key(line) for line in page.splitlines() if line.strip()})
    return {key for key, n in counts.items() if key and n >= min_share * len(pages)}


def _line_key(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())


def clean_pages(pages: list[str], line_numbers: bool = False) -> list[str]:
    pages = [normalize(p) for p in pages]
    if line_numbers:
        pages = [strip_line_numbers(p) for p in pages]
    noise = boilerplate_lines(pages)
    cleaned = []
    for page in pages:
        kept = [line for line in page.splitlines() if _line_key(line) not in noise]
        cleaned.append("\n".join(kept).strip())
    return cleaned


def join_pages(pages: list[str]) -> tuple[str, list[int]]:
    """Join pages into one text; return it with each page's starting offset."""
    starts, parts, pos = [], [], 0
    for page in pages:
        starts.append(pos)
        parts.append(page)
        pos += len(page) + 2
    return "\n\n".join(parts), starts


# --- Heading detection ----------------------------------------------------------------


NUMBER_PREFIX = re.compile(r"^(\d+(?:\.\d+)*)\.?\s")


def _title_pattern(title: str) -> re.Pattern[str]:
    """Match a title at the start of a line, tolerating whitespace differences and an
    optional section number printed before it ("5. AI RMF Core")."""
    words = [re.escape(w) for w in title.split()]
    number = r"(?P<num>\d+(?:\.\d+)*)\.?\s+"
    return re.compile(rf"(?m)^(?:{number})?" + r"\s*".join(words), re.IGNORECASE)


def _find_title(title: str, text: str, start: int, end: int) -> re.Match[str] | None:
    """Prefer a numbered occurrence ("5.1 Govern") over a bare one (a figure label)."""
    matches = list(_title_pattern(title).finditer(text, start, max(end, start)))
    numbered = [m for m in matches if m.group("num")]
    return (numbered or matches or [None])[0]


def headings_from_outline(
    outline: list[OutlineEntry], text: str, page_starts: list[int]
) -> list[Heading]:
    """Place each outline entry where its title starts a line on its page (else the page
    start). If the page prints a section number before the title, keep it in the title."""
    headings: list[Heading] = []
    floor = 0
    for entry in outline:
        title = normalize(entry.title)
        if not title or entry.page >= len(page_starts):
            continue
        start = max(page_starts[entry.page], floor)
        end = page_starts[entry.page + 1] if entry.page + 1 < len(page_starts) else len(text)
        offset = start
        match = _find_title(title, text, start, end)
        if match:
            offset = match.start()
            if match.group("num") and not NUMBER_PREFIX.match(title):
                title = f"{match.group('num')} {title}"
        headings.append(Heading(title=title, offset=offset))
        floor = offset
    return headings


TEXT_HEADING = re.compile(
    r"(?m)^(?:Sec(?:tion)?\.?\s*(?P<sec>\d+)\s*\.|(?P<num>\d+(?:\.\d+)*)\.?)"
    r"\s+(?P<title>[A-Z][^\n]{1,250})$"
)
# URLs and legal citations mark footnotes; dot leaders or a trailing page number mark ToC lines
NOT_A_HEADING = re.compile(
    r"https?://|U\.S\.C\.|et seq|^(See|Id|Ibid)\b|(\.\s*){3,}\d*$|\s\d{1,3}$"
)


def _follows(prev: tuple[int, ...], num: tuple[int, ...]) -> bool:
    """True if `num` can come right after `prev` in a numbered outline: the first child
    (4.1 -> 4.1.1) or the next sibling at any level (4.1 -> 4.2, 4.1 -> 5)."""
    if num == (*prev, 1):
        return True
    return any(num == (*prev[:level], prev[level] + 1) for level in range(len(prev)))


def headings_from_text(text: str) -> list[Heading]:
    """Numbered heading lines ("Sec. 4.", "2.1 Scope") that continue a valid numbering
    sequence starting at 1. The sequence check drops footnotes, page numbers, and list
    items, which jump around or restart. Inline headings keep only their first sentence."""
    headings: list[Heading] = []
    prev: tuple[int, ...] = ()
    for match in TEXT_HEADING.finditer(text):
        number = match.group("sec") or match.group("num")
        num = tuple(int(part) for part in number.split("."))
        rest = match.group("title").strip()
        if NOT_A_HEADING.search(rest) or not _follows(prev, num):
            continue
        first_sentence = re.split(r"(?<=[a-z)])\.\s|\.\s+(?=\()", rest, maxsplit=1)[0].rstrip(".")
        if len(first_sentence.split()) > 14:
            continue
        prefix = f"Sec. {number}." if match.group("sec") else number
        headings.append(Heading(title=f"{prefix} {first_sentence}", offset=match.start()))
        prev = num
    return headings


# --- Section ids and assembly -----------------------------------------------------------


def section_id_for(title: str) -> str:
    """ "5. AI RMF Core" -> "5"; "Sec. 4. Ensuring Safety" -> "sec-4"; "Appendix B: ..." ->
    "appendix-b"; otherwise a slug of the first few words."""
    title = normalize(title)
    if m := re.match(r"^Sec\.\s*(\d+)", title):
        return f"sec-{m.group(1)}"
    if m := re.match(r"^(\d+(?:\.\d+)*)\.?(?:\s|$)", title):
        return m.group(1)
    if m := re.match(r"^([A-H](?:\.\d+)+)\.?(?:\s|$)", title):
        return m.group(1)
    if m := re.match(r"^(appendix|annex)\s+([A-Z0-9]+)\b", title, re.IGNORECASE):
        return f"{m.group(1).lower()}-{m.group(2).lower()}"
    if m := re.match(r"^([IVX]{1,5})\.\s", title):
        return m.group(1).lower()
    words = re.findall(r"[a-z0-9]+", title.lower())[:6]
    return "-".join(words) or "section"


def _unique(section_id: str, seen: Counter[str]) -> str:
    seen[section_id] += 1
    return section_id if seen[section_id] == 1 else f"{section_id}-{seen[section_id]}"


def sections_from_headings(doc_id: str, text: str, headings: list[Heading]) -> list[Section]:
    """Cut text at heading offsets. Text before the first heading becomes "front"."""
    headings = sorted(headings, key=lambda h: h.offset)
    bounds = [Heading(title="Front matter", offset=0), *headings]
    seen: Counter[str] = Counter()
    sections = []
    for i, heading in enumerate(bounds):
        end = bounds[i + 1].offset if i + 1 < len(bounds) else len(text)
        body = text[heading.offset : end].strip()
        if i > 0 and body.lower().startswith(heading.title.lower()):
            body = body[len(heading.title) :].strip()
        if SKIP_HEADINGS.match(heading.title) or len(body.split()) < MIN_SECTION_WORDS:
            continue
        section_id = _unique("front" if i == 0 else section_id_for(heading.title), seen)
        sections += split_long(
            Section(doc_id=doc_id, section_id=section_id, heading=heading.title, text=unwrap(body))
        )
    return sections


def split_long(section: Section, max_words: int = MAX_SECTION_WORDS) -> list[Section]:
    """Split a section longer than `max_words` into parts at sentence boundaries, so one
    read_document call stays a reasonable size. Part 1 keeps the section's id; later parts
    get "-p2", "-p3", ... and "(part N)" in the heading."""
    if len(section.text.split()) <= max_words:
        return [section]
    parts: list[list[str]] = [[]]
    count = 0
    for sentence in re.split(r"(?<=[.!?])\s+", section.text):
        words = len(sentence.split())
        if count and count + words > max_words:
            parts.append([])
            count = 0
        parts[-1].append(sentence)
        count += words
    return [
        section.model_copy(
            update={
                "section_id": section.section_id if n == 1 else f"{section.section_id}-p{n}",
                "heading": section.heading if n == 1 else f"{section.heading} (part {n})",
                "text": " ".join(part),
            }
        )
        for n, part in enumerate(parts, start=1)
    ]


def sections_by_page(doc_id: str, pages: list[str]) -> list[Section]:
    """Fallback: one section per page, headed by the page's first line."""
    return [
        Section(
            doc_id=doc_id,
            section_id=f"p{i + 1}",
            heading=f"Page {i + 1}: {page.splitlines()[0][:70]}",
            text=unwrap(page),
        )
        for i, page in enumerate(pages)
        if len(page.split()) >= MIN_SECTION_WORDS
    ]


def split_document(
    doc_id: str,
    raw_pages: list[str],
    outline: list[OutlineEntry],
    line_numbers: bool = False,
) -> tuple[list[Section], str]:
    """Split one document. Returns the sections and the method used:
    "outline", "text", or "page"."""
    pages = clean_pages(raw_pages, line_numbers)
    text, starts = join_pages(pages)
    if len(outline) >= MIN_HEADINGS:
        headings = headings_from_outline(outline, text, starts)
        sections = sections_from_headings(doc_id, text, headings)
        if len(sections) >= MIN_HEADINGS:
            return sections, "outline"
    headings = headings_from_text(text)
    if len(headings) >= MIN_HEADINGS:
        return sections_from_headings(doc_id, text, headings), "text"
    return sections_by_page(doc_id, pages), "page"
