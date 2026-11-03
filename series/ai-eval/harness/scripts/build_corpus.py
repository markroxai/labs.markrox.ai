"""Build corpus/sections.jsonl from the documents in corpus/manifest.yaml.

    uv run --group corpus python scripts/build_corpus.py                 # download, verify, build
    uv run --group corpus python scripts/build_corpus.py --write-hashes  # record new SHA-256s

Raw PDFs go to corpus/raw/ (gitignored). sections.jsonl is committed so tests run offline.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import urllib.request
from pathlib import Path

import yaml
from pypdf import PdfReader

from harness.corpus import DEFAULT_CORPUS_DIR, Manifest
from harness.sectioning import OutlineEntry, split_document

USER_AGENT = "Mozilla/5.0 (labs.markrox.ai corpus builder)"


def download(url: str, dest: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    if not data.startswith(b"%PDF"):
        raise RuntimeError(f"{url} did not return a PDF")
    dest.write_bytes(data)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_outline(reader: PdfReader) -> list[OutlineEntry]:
    entries: list[OutlineEntry] = []

    def walk(items: list, depth: int) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item, depth + 1)
                continue
            try:
                page = reader.get_destination_page_number(item)
            except Exception:
                continue
            if page is not None and page >= 0:
                entries.append(OutlineEntry(title=item.title, page=page, depth=depth))

    try:
        walk(reader.outline, 0)
    except Exception:
        return []
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--write-hashes", action="store_true", help="record SHA-256 in manifest")
    parser.add_argument("--only", help="process one doc_id (sections.jsonl is not written)")
    args = parser.parse_args()
    logging.getLogger("pypdf").setLevel(logging.ERROR)

    manifest_path = args.corpus_dir / "manifest.yaml"
    manifest = Manifest.model_validate(yaml.safe_load(manifest_path.read_text()))
    raw_dir = args.corpus_dir / "raw"
    raw_dir.mkdir(exist_ok=True)

    lines: list[str] = []
    failed = False
    for doc in manifest.documents:
        if args.only and doc.doc_id != args.only:
            continue
        pdf = raw_dir / f"{doc.doc_id}.pdf"
        if not pdf.exists():
            print(f"download  {doc.doc_id}")
            try:
                download(str(doc.source_url), pdf)
            except Exception as exc:
                print(f"DOWNLOAD FAILED {doc.doc_id}: {exc}")
                failed = True
                continue
        digest = sha256(pdf)
        if not doc.sha256 or args.write_hashes:
            doc.sha256 = digest
        elif doc.sha256 != digest:
            print(f"HASH MISMATCH {doc.doc_id}: source changed; rerun with --write-hashes")
            failed = True
            continue

        reader = PdfReader(pdf)
        pages = [page.extract_text() or "" for page in reader.pages]
        sections, method = split_document(
            doc.doc_id, pages, read_outline(reader), line_numbers=doc.line_numbers
        )
        words = sum(len(s.text.split()) for s in sections)
        print(f"{doc.doc_id:30} {method:8} {len(sections):4} sections {words:7} words")
        lines += [s.model_dump_json() for s in sections]

    if args.write_hashes:
        header = "# Corpus manifest. Source of truth for which documents are in the corpus.\n"
        body = yaml.safe_dump(
            manifest.model_dump(mode="json", exclude_defaults=True),
            sort_keys=False,
            width=100,
            allow_unicode=True,
        )
        manifest_path.write_text(header + body)
    if failed:
        return 1
    if not args.only:
        (args.corpus_dir / "sections.jsonl").write_text("\n".join(lines) + "\n")
        print(f"wrote {len(lines)} sections")
    return 0


if __name__ == "__main__":
    sys.exit(main())
