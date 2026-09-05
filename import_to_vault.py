#!/usr/bin/env python3
"""Import the daily AI news digests from this repo into ken's Obsidian vault.

The cloud routine pushes one `archive/YYYY-MM-DD.md` per morning. This script
reads those from origin/main and writes any not-yet-imported day into a per-day
note inside the project folder, rebuilds that month's index, and commits.

Layout (one note per day since 2026-09-05; it used to be one note per month):

    log/
    ├── 2026-09/
    │   ├── 2026-09-01.md   ## Claude配信 / ## ChatGPT/Codex配信 の2節
    │   └── ...
    └── 2026-09.md          その月の目次。各日へのリンクと要点1行だけ

Codex writes the ChatGPT/Codex delivery into the same day note as a second
section, so every section is labelled with the side it came from. Splitting by
day is what keeps the two sides off each other's file.

Idempotent: a day whose section is already there is skipped, so running it
twice — or after the Mac was off for a week — does the right thing. The index is
rebuilt from whatever day notes exist, so it repairs itself too.

Usage:
    python3 import_to_vault.py [--dry-run]
    python3 import_to_vault.py --reindex [YYYY-MM ...]
"""

import argparse
import datetime
import glob
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
# archive entries are read from origin/main, not from the working tree
VAULT = "/Users/ken/Documents/Obsidian Vault"
LOG_DIR = os.path.join(VAULT, "20_Projects", "AIニュース毎朝配信", "log")
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]

# heading and nickname per delivery side. the heading strings are the agreed
# convention (2026-09-02) — both sides' entries sit in one file, so an unlabelled
# section would be unattributable.
SIDES = {
    "claude": ("Claude配信", "クロ"),
    "codex": ("ChatGPT/Codex配信", "コデ"),
}
MARKER_SUFFIX = {"claude": "-claude", "codex": "-chatgpt-codex"}


def run(cmd, cwd=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(f"ERROR: {' '.join(cmd)}\n{r.stdout}{r.stderr}", file=sys.stderr)
        sys.exit(1)
    return r.stdout.strip()


def strip_frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def demote_headings(body):
    """The day note uses ## for the delivery side, so push the body's own down."""
    return re.sub(r"^(#{2,4}) ", lambda m: "#" + m.group(1) + " ", body, flags=re.M)


def day_path(day):
    return os.path.join(LOG_DIR, day[:7], f"{day}.md")


def index_path(month):
    return os.path.join(LOG_DIR, f"{month}.md")


def markers(day, side):
    """Markers that mean "this side's entry for this day is already here"."""
    found = [f"<!-- imported: {day}{MARKER_SUFFIX[side]} -->"]
    if side == "claude":
        # entries written before the log was shared with Codex carried no suffix
        found.append(f"<!-- imported: {day} -->")
    return found


def day_header(day):
    d = datetime.date.fromisoformat(day)
    return (
        "---\n"
        "type: log\n"
        "project: AIニュース毎朝配信\n"
        f"date: {day}\n"
        "---\n\n"
        f"# AIニュース配信ログ {day}（{WEEKDAYS[d.weekday()]}）\n\n"
        "> 自動生成なので直接編集しない。Claude側（7:00配信）の原本は GitHub の "
        "ai-news-assets/archive にある。\n"
        f"> その月の一覧は [[{day[:7]}]]。\n"
    )


def write_day_section(day, side, body, dry_run=False):
    """Append one side's entry to the day note. Returns the path if it wrote."""
    path = day_path(day)
    existing = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            existing = f.read()
        if any(m in existing for m in markers(day, side)):
            return None
    else:
        existing = day_header(day)

    heading = SIDES[side][0]
    marker = f"<!-- imported: {day}{MARKER_SUFFIX[side]} -->"
    block = f"\n---\n\n## {heading}\n{marker}\n\n{body.strip()}\n"

    if dry_run:
        print(f"[dry-run] would write {heading} into {path}")
        return None

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(existing.rstrip("\n") + "\n" + block)
    return path


def first_bullet(text, limit=68):
    """The day's opening bullet, for the index row. Falsy if the note has none."""
    lines = text.splitlines()
    start = 0
    for i, line in enumerate(lines):
        if re.match(r"^#{3,4} .*(要点|サマリ)", line):
            start = i + 1
            break
    for line in lines[start:]:
        if line.startswith("- "):
            s = line[2:].strip().replace("|", "\\|")
            return s if len(s) <= limit else s[:limit] + "…"
    return ""


def rebuild_index(month, dry_run=False):
    """Regenerate a month's index from the day notes actually on disk.

    Derived from the directory, never appended to, so both sides can trigger it
    and the result is the same — and a hand-broken index heals on the next run.
    """
    days = sorted(
        os.path.basename(p)[:-3]
        for p in glob.glob(os.path.join(LOG_DIR, month, f"{month}-*.md"))
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", os.path.basename(p))
    )
    if not days:
        return None

    rows = []
    for day in days:
        with open(day_path(day), encoding="utf-8") as f:
            text = f.read()
        sides = [
            nick for key, (heading, nick) in SIDES.items()
            if re.search(rf"^## {re.escape(heading)}$", text, flags=re.M)
        ]
        d = datetime.date.fromisoformat(day)
        rows.append(
            f"| [[{day}]]（{WEEKDAYS[d.weekday()]}） | {'・'.join(sides) or '—'} "
            f"| {first_bullet(text)} |"
        )

    content = (
        "---\n"
        "type: log-index\n"
        "project: AIニュース毎朝配信\n"
        f"month: {month}\n"
        "---\n\n"
        f"# AIニュース配信ログ {month}\n\n"
        f"> その月の目次。本文は日ごとに `{month}/` の中にある。クロ（Claude、7:00配信）と"
        "コデ（ChatGPT/Codex、8:00配信）が同じ日のノートにそれぞれ追記する。\n"
        "> この目次は日ごとのノートから毎回作り直すので、直接編集しても次回上書きされる。\n\n"
        "| 日付 | 記録 | 冒頭の要点 |\n"
        "| --- | --- | --- |\n"
        + "\n".join(rows) + "\n"
    )

    path = index_path(month)
    old = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = f.read()
    if old == content:
        return None
    if dry_run:
        print(f"[dry-run] would rebuild {path}（{len(rows)}日分）")
        return None
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def commit(paths, message):
    # commit only the files this script wrote, so a concurrent edit elsewhere
    # in the vault is never swept into our commit
    for path in sorted(set(paths)):
        run(["git", "add", path], cwd=VAULT)
    if run(["git", "diff", "--cached", "--name-only"], cwd=VAULT):
        run(["git", "-c", "user.email=bknb.yone.ken@gmail.com", "-c", "user.name=ken",
             "commit", "-q", "-m", message], cwd=VAULT)
        print("committed to the vault")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reindex", nargs="*", metavar="YYYY-MM",
                    help="rebuild month indexes only (no month = every month)")
    args = ap.parse_args()

    if args.reindex is not None:
        months = args.reindex or sorted({
            os.path.basename(p) for p in glob.glob(os.path.join(LOG_DIR, "*"))
            if re.fullmatch(r"\d{4}-\d{2}", os.path.basename(p)) and os.path.isdir(p)
        })
        touched = [p for p in (rebuild_index(m, args.dry_run) for m in months) if p]
        print(f"reindexed: {', '.join(months) or '(none)'}")
        if touched and not args.dry_run:
            commit(touched, "AIニュース配信ログの月次目次を再生成")
        return

    # Read the archive straight out of origin/main rather than the working tree:
    # a half-finished local edit must never stop the morning import.
    run(["git", "fetch", "--quiet", "origin", "main"], cwd=REPO)
    listing = run(["git", "ls-tree", "--name-only", "origin/main", "archive/"],
                  cwd=REPO, check=False)

    days = sorted(
        os.path.basename(line)[:-3] for line in listing.splitlines()
        if re.fullmatch(r"archive/\d{4}-\d{2}-\d{2}\.md", line.strip())
    )
    if not days:
        print("no archive entries — nothing to import")
        return

    os.makedirs(LOG_DIR, exist_ok=True)
    touched, imported = [], []

    for day in days:
        path = day_path(day)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                if any(m in f.read() for m in markers(day, "claude")):
                    continue

        raw = run(["git", "show", f"origin/main:archive/{day}.md"], cwd=REPO)
        body = demote_headings(strip_frontmatter(raw))
        written = write_day_section(day, "claude", body, args.dry_run)
        if written:
            touched.append(written)
        imported.append(day)

    if not imported:
        print("already up to date — nothing new to import")
    else:
        print(f"imported: {', '.join(imported)}")

    # always rebuild: Codex may have added its own sections since the last run
    for month in sorted({d[:7] for d in days}):
        rebuilt = rebuild_index(month, args.dry_run)
        if rebuilt:
            touched.append(rebuilt)

    if args.dry_run or not touched:
        return
    label = f"（{imported[0]}〜{imported[-1]}）" if imported else "（目次のみ）"
    commit(touched, f"AIニュース配信ログを追記{label}")


if __name__ == "__main__":
    main()
