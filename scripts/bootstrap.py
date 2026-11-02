#!/usr/bin/env python3
"""Generate series/lab folders, site pages, and plans from series/*/series.yaml.

Hierarchy: Series > Lab
  series/<series>/series.yaml        series definition (labs, phases, scope)
  series/<series>/<NN-slug>/          one lab: code, tests, README, demo/

Usage:
  python scripts/bootstrap.py                         # regenerate everything
  python scripts/bootstrap.py --new-series ai-security "AI Security Labs"
  python scripts/bootstrap.py --issues [--series ai-eval]   # GitHub milestones + issues (needs gh)

Lab READMEs are only created if missing, so your notes are never overwritten.
Site pages and plan.md files are regenerated every run.
"""
import argparse
import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SITE = yaml.safe_load((ROOT / "site.yaml").read_text())
SERIES_DIR = ROOT / "series"
DOCS = ROOT / "docs"


# ---------- loading ----------

def load_series():
    out = []
    for f in sorted(SERIES_DIR.glob("*/series.yaml")):
        s = yaml.safe_load(f.read_text())
        s["slug"] = f.parent.name
        s.setdefault("labs", [])
        s.setdefault("phases", {})
        out.append(s)
    return out


def lab_id(lab):
    return f"{lab['lab']:02d}-{lab['slug']}"


def lab_label(lab):
    return f"Lab {lab['lab']:02d}: {lab['title']}"


def issue_title(series, lab):
    return f"[{series['short']}] {lab_label(lab)}"


def deps(lab):
    return ", ".join(f"Lab {d:02d}" for d in lab.get("depends", [])) or "None"


def checklist(items):
    return "\n".join(f"- [ ] {i}" for i in items or [])


def phase_name(series, lab):
    return series["phases"].get(lab["phase"], f"Phase {lab['phase']}")


# ---------- lab folders ----------

def lab_readme(series, lab):
    return f"""# {lab_label(lab)}

**Series:** {series['title']} · **Phase:** {phase_name(series, lab)} · **Depends on:** {deps(lab)} · **Status:** Not started

## Goal

_One sentence: what this lab proves or measures._

## Core scope (timebox: ~6-8 hours)

{checklist(lab['core'])}

## Stretch

{checklist(lab.get('stretch'))}

## Run it

```bash
# TODO
```

## Findings

_What surprised you? One chart or table that tells the story._

## Deliverables

- [ ] Code + tests in this folder
- [ ] Demo in `demo/` (60-90s recording or hosted link)
- [ ] Write-up on markrox.ai: _link_
- [ ] Update posted in {SITE['slack']}
"""


def write_lab_folders(series):
    base = SERIES_DIR / series["slug"]
    for lab in series["labs"]:
        d = base / lab_id(lab)
        (d / "demo").mkdir(parents=True, exist_ok=True)
        (d / "demo" / ".gitkeep").touch()
        if not (d / "README.md").exists():
            (d / "README.md").write_text(lab_readme(series, lab))


# ---------- plans ----------

def series_plan(series):
    out = [f"# {series['title']}: Plan", "",
           f"{series.get('summary', '')}", "",
           "Generated from `series.yaml`. Edit that file, then run `python scripts/bootstrap.py`.", "",
           "Each lab has a **core** scope (~6-8 hours, enough for demo + write-up) and an optional **stretch** scope.", ""]
    for p, name in series["phases"].items():
        group = [l for l in series["labs"] if l["phase"] == p]
        if not group:
            continue
        out += [f"## Phase {p}: {name}", ""]
        for lab in group:
            orig = f" · orig #{lab['orig']}" if lab.get("orig") else ""
            out += [f"### {lab_label(lab)}", "", f"_Depends on: {deps(lab)}{orig}_", "",
                    "**Core**", "", checklist(lab["core"]), "",
                    "**Stretch**", "", checklist(lab.get("stretch")), ""]
    return "\n".join(out)


def root_plan(all_series):
    rows = "\n".join(
        f"| [{s['title']}](series/{s['slug']}/plan.md) | {s.get('status', 'planned')} | {len(s['labs'])} | {s.get('summary', '').strip()} |"
        for s in all_series)
    return f"""# Labs: Plan

Hierarchy: **Series > Lab**. Each series is a themed run of weekly labs.
Per-series plans live in `series/<series>/plan.md`, generated from `series.yaml`.

| Series | Status | Labs | Summary |
|---|---|---|---|
{rows}

Start a new series: `python scripts/bootstrap.py --new-series <slug> "<Title>"`
"""


# ---------- site ----------

def site_home(all_series):
    cards = "\n\n".join(
        f"### [{s['title']}]({s['slug']}/index.md)\n\n_{s.get('status', 'planned').capitalize()} · {len(s['labs'])} labs_\n\n{s.get('summary', '').strip()}"
        for s in all_series)
    return f"""# {SITE['title']}

{SITE['tagline']} Write-ups live on [markrox.ai]({SITE['blog']}).

All data is synthetic or public. No client or production data.

## Series

{cards}

Want to try a lab yourself? Each one has a core scope you can finish in a day.
"""


def site_series_index(series):
    rows = "\n".join(
        f"| {lab['lab']:02d} | [{lab['title']}]({lab_id(lab)}.md) | {phase_name(series, lab)} | {lab.get('status', 'Not started')} |"
        for lab in series["labs"])
    return f"""# {series['title']}

{series.get('summary', '').strip()}

| Lab | Title | Phase | Status |
|---|---|---|---|
{rows}
"""


def site_lab_page(series, lab):
    path = f"series/{series['slug']}/{lab_id(lab)}"
    return f"""# {lab_label(lab)}

**Series:** [{series['title']}](index.md) · **Phase:** {phase_name(series, lab)} · **Depends on:** {deps(lab)}

## Core scope

{checklist(lab['core'])}

## Stretch

{checklist(lab.get('stretch'))}

## Links

- Code: [`{path}`]({SITE['repo']}/tree/main/{path})
- Demo: {lab.get('demo') or '_coming soon_'}
- Write-up: {lab.get('post') or f'_coming soon on [markrox.ai]({SITE["blog"]})_'}
"""


def write_site(all_series):
    # clear generated series pages (keep CNAME and any hand-written files at docs root)
    for s in all_series:
        d = DOCS / s["slug"]
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.md"):
            old.unlink()
        (d / "index.md").write_text(site_series_index(s))
        for lab in s["labs"]:
            (d / f"{lab_id(lab)}.md").write_text(site_lab_page(s, lab))
    (DOCS / "index.md").write_text(site_home(all_series))


# ---------- new series ----------

NEW_SERIES = """# Series definition: {title}
title: {title}
short: {short}
status: planned         # planned | active | complete
summary: >-
  One or two sentences on what this series covers.

phases:
  0: Setup
  1: Foundations

labs:
  - lab: 0
    slug: setup
    title: Setup
    phase: 0
    depends: []
    core:
      - Define the system under test for this series
    stretch: []
"""


def new_series(slug, title):
    d = SERIES_DIR / slug
    if d.exists():
        raise SystemExit(f"series/{slug} already exists")
    d.mkdir(parents=True)
    short = title.replace(" Labs", "").strip()
    (d / "series.yaml").write_text(NEW_SERIES.format(title=title, short=short))
    print(f"Created series/{slug}/series.yaml. Edit it, then run bootstrap.py")


# ---------- GitHub ----------

def gh(*args):
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def create_issues(all_series, only=None):
    existing_ms = {m["title"] for m in json.loads(gh("api", "repos/{owner}/{repo}/milestones?state=all"))}
    existing_issues = {i["title"] for i in json.loads(
        gh("issue", "list", "--state", "all", "--limit", "500", "--json", "title"))}
    for name, color in [("lab", "1f6feb"), ("stretch", "8b949e"), ("write-up", "d29922"), ("demo", "3fb950")]:
        subprocess.run(["gh", "label", "create", name, "--color", color, "--force"], capture_output=True)
    for s in all_series:
        if only and s["slug"] != only:
            continue
        series_label = f"series:{s['slug']}"
        subprocess.run(["gh", "label", "create", series_label, "--color", "6e40c9", "--force"], capture_output=True)
        for p, name in s["phases"].items():
            ms = f"{s['short']} · Phase {p}: {name}"
            if ms not in existing_ms:
                gh("api", "repos/{owner}/{repo}/milestones", "-f", f"title={ms}")
        for lab in s["labs"]:
            title = issue_title(s, lab)
            if title in existing_issues:
                continue
            path = f"series/{s['slug']}/{lab_id(lab)}"
            body = (f"**Series:** {s['title']} · **Phase:** {phase_name(s, lab)} · **Depends on:** {deps(lab)}\n\n"
                    f"### Core\n{checklist(lab['core'])}\n\n### Stretch\n{checklist(lab.get('stretch'))}\n\n"
                    f"### Definition of done\n- [ ] Core scope complete, tests passing\n- [ ] Demo in `{path}/demo/`\n"
                    f"- [ ] Write-up published on markrox.ai and linked from labs.markrox.ai\n"
                    f"- [ ] Update posted in {SITE['slack']}")
            gh("issue", "create", "--title", title, "--body", body, "--label", f"lab,{series_label}",
               "--milestone", f"{s['short']} · Phase {lab['phase']}: {phase_name(s, lab)}")
            print(f"Created issue: {title}")


# ---------- main ----------

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--new-series", nargs=2, metavar=("SLUG", "TITLE"))
    ap.add_argument("--issues", action="store_true", help="create GitHub milestones and issues via gh")
    ap.add_argument("--series", help="limit --issues to one series slug")
    args = ap.parse_args()

    if args.new_series:
        new_series(*args.new_series)

    all_series = load_series()
    for s in all_series:
        write_lab_folders(s)
        (SERIES_DIR / s["slug"] / "plan.md").write_text(series_plan(s))
    (ROOT / "plan.md").write_text(root_plan(all_series))
    write_site(all_series)
    print(f"Generated {len(all_series)} series, {sum(len(s['labs']) for s in all_series)} labs")

    if args.issues:
        create_issues(all_series, args.series)
