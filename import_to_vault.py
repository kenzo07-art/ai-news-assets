#!/usr/bin/env python3
"""Import the daily AI news digests from this repo into ken's Obsidian vault.

The cloud routine pushes one `archive/YYYY-MM-DD.md` per morning. This script
reads those from origin/main and appends any not-yet-imported day into a monthly
log inside the project folder, then commits the vault.

Codex writes the ChatGPT/Codex delivery into the same monthly log, so every
entry is labelled with the side it came from.

Idempotent: a day already present in the monthly file is skipped, so running it
twice — or after the Mac was off for a week — does the right thing.

Usage:
    python3 import_to_vault.py [--dry-run]
"""

import argparse
import datetime
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
# archive entries are read from origin/main, not from the working tree
VAULT = "/Users/ken/Documents/Obsidian Vault"
LOG_DIR = os.path.join(VAULT, "20_Projects", "AIニュース毎朝配信", "log")
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]


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
    """The monthly log uses ## for the day, so push the day's own headings down."""
    return re.sub(r"^(#{2,4}) ", lambda m: "#" + m.group(1) + " ", body, flags=re.M)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

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
        month = day[:7]
        target = os.path.join(LOG_DIR, f"{month}.md")
        marker = f"<!-- imported: {day}-claude -->"
        # entries written before the log was shared with Codex carried no side suffix
        legacy_marker = f"<!-- imported: {day} -->"

        existing = ""
        if os.path.exists(target):
            with open(target, encoding="utf-8") as f:
                existing = f.read()
            if marker in existing or legacy_marker in existing:
                continue
        else:
            existing = (
                "---\n"
                f"type: log\n"
                f"project: AIニュース毎朝配信\n"
                f"month: {month}\n"
                "---\n\n"
                f"# AIニュース配信ログ {month}\n\n"
                "> 毎朝配信したダイジェストの記録。Claude側（7:00）とChatGPT/Codex側（8:00）の"
                "両方が追記するので、見出しに配信元を書く。自動生成なので直接編集しない"
                "（Claude側の原本は GitHub の ai-news-assets/archive にある）。\n\n"
                "---\n"
            )

        raw = run(["git", "show", f"origin/main:archive/{day}.md"], cwd=REPO)
        body = demote_headings(strip_frontmatter(raw)).strip()

        # the log is shared with Codex, which records the ChatGPT/Codex delivery in
        # the same file — always say which side an entry came from
        d = datetime.date.fromisoformat(day)
        block = f"\n## {day}（{WEEKDAYS[d.weekday()]}）Claude配信\n{marker}\n\n{body}\n\n---\n"

        if args.dry_run:
            print(f"[dry-run] would append {day} to {target}")
        else:
            with open(target, "w", encoding="utf-8") as f:
                f.write(existing.rstrip("\n") + "\n" + block)
            touched.append(target)
        imported.append(day)

    if not imported:
        print("already up to date — nothing new to import")
        return

    print(f"imported: {', '.join(imported)}")

    if args.dry_run or not touched:
        return

    # commit only the files this script wrote, so a concurrent edit elsewhere
    # in the vault is never swept into our commit
    for path in sorted(set(touched)):
        run(["git", "add", path], cwd=VAULT)
    staged = run(["git", "diff", "--cached", "--name-only"], cwd=VAULT)
    if staged:
        run(["git", "-c", "user.email=bknb.yone.ken@gmail.com", "-c", "user.name=ken",
             "commit", "-q", "-m",
             f"AIニュース配信ログを追記（{imported[0]}〜{imported[-1]}）"], cwd=VAULT)
        print("committed to the vault")


if __name__ == "__main__":
    main()
