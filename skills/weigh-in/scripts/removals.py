#!/usr/bin/env python3
"""List what a competitor removed between two points in time: folders, files and documentation
headings gone between two commits, and lines gone between two captures of the same page.

Usage:
  python3 removals.py commits <repo> <old-rev> [<new-rev>] [--top 50] [--max-docs 500]
  python3 removals.py pages <old-capture> <new-capture> [--min-chars 8] [--similarity 0.75] [--top 50]

Additions announce themselves: a launch post, a new folder, a new row on the pricing page.
Removals are quiet, so an update looks for them on purpose. Read only: `commits` reads the two
trees with git and never checks anything out; `pages` reads two text or HTML files, such as two
captures from capture_page.py, or a Wayback snapshot (wayback.py fetch --text) and today's capture.

`commits` prints JSON with:
  - removed_dirs: folders that existed at <old-rev> and are gone at <new-rev>, the outermost ones
    only, with their file count and kind (source and other, docs, tests, dependencies or build);
  - moved_dirs: folders that are gone because their files were renamed into another folder;
  - deleted_files: counts by kind and by top-level folder, and the deleted docs and source paths
    (renames are not deletions);
  - removed_headings: Markdown headings that disappeared from README, docs and changelog files that
    still exist, renamed ones included, README and docs checked first; headings inside fenced code
    and section numbers (a renumbered "10." that is now "11.") are ignored;
  - warnings, such as a partial clone that fetches file contents on demand.
`pages` prints JSON with:
  - removed: lines of the older capture that are gone from the newer one, in their order;
  - reworded: removed lines with a close match among the new lines (a changed price, a renamed
    plan), shown before and after;
  - counts of the lines kept and added. Whitespace and case are ignored; lines shorter than
    --min-chars (menus, buttons) are skipped.

A removal is a signal, not a finding: a folder can move to another package, a heading can be
reworded, a feature can live on behind a flag. Confirm each one in the code, the docs or the
changelog before it becomes a "What changed" row.
"""
from __future__ import annotations

import argparse
import difflib
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from common import SKIP_DIRS, TEST_DIRS, git, html_to_text, is_git_repo, is_test_path, now_utc, print_json, read_text

DOC_DIRS = {"docs", "doc", "documentation"}
DOC_EXT = {".md", ".mdx", ".markdown", ".rst", ".adoc"}
MARKDOWN_EXT = {".md", ".mdx", ".markdown"}
# A closing run of "#" counts only after a space, so "## C#" keeps its name.
HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
FENCE = re.compile(r"^ {0,3}(```|~~~)")


def kind_of(path: str, is_dir: bool = False) -> str:
    """What a removed path is: tests, dependencies or build output, docs, or source and other files."""
    folders = path.split("/") if is_dir else path.split("/")[:-1]
    if set(folders) & SKIP_DIRS:
        return "dependencies_or_build"
    if TEST_DIRS.search(path) or (not is_dir and is_test_path(path)):
        return "tests"
    if set(folders) & DOC_DIRS or (not is_dir and os.path.splitext(path)[1].lower() in DOC_EXT):
        return "docs"
    return "source_and_other"


def resolve(repo: Path, rev: str) -> dict:
    commit = git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}", check=False).strip()
    if not commit:
        raise SystemExit(f"removals: {rev} is not a commit in {repo}")
    return {"rev": rev, "commit": commit, "date": git(repo, "show", "-s", "--format=%cI", commit).strip()}


def tree_files(repo: Path, commit: str) -> list:
    return [p for p in git(repo, "ls-tree", "-r", "-z", "--name-only", commit).split("\0") if p]


def changes(repo: Path, old: str, new: str) -> tuple:
    """Deleted paths, renames as (old path, new path), modified paths, and whether git skipped
    part of its rename detection because too many files changed."""
    result = subprocess.run(["git", "-C", str(repo), "diff", "--name-status", "-z", "-M", old, new],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"removals: git diff failed: {result.stderr.strip()}")
    tokens = result.stdout.split("\0")
    deleted, renamed, modified = [], [], []
    i = 0
    while i < len(tokens) and tokens[i]:
        status = tokens[i]
        if status[0] in "RC":
            if status[0] == "R":
                renamed.append((tokens[i + 1], tokens[i + 2]))
            i += 3
            continue
        if status[0] == "D":
            deleted.append(tokens[i + 1])
        elif status[0] == "M":
            modified.append(tokens[i + 1])
        i += 2
    skipped = "rename detection" in result.stderr and "skipped" in result.stderr
    return deleted, renamed, modified, skipped


def folders_of(files: list) -> set:
    found = set()
    for path in files:
        parts = path.split("/")[:-1]
        for depth in range(1, len(parts) + 1):
            found.add("/".join(parts[:depth]))
    return found


def destination(folder: str, moves: list) -> str:
    """Where most files of a vanished folder went, when they kept their path below it."""
    targets = Counter()
    for old_path, new_path in moves:
        rest = old_path[len(folder) + 1:]
        targets[new_path[: -len(rest) - 1] if new_path.endswith("/" + rest) else os.path.dirname(new_path)] += 1
    return targets.most_common(1)[0][0] if targets else ""


def headings(text: str) -> list:
    """ATX headings outside fenced code, as (level, text, normalized key)."""
    found, fenced = [], False
    for line in text.split("\n"):
        if FENCE.match(line):
            fenced = not fenced
            continue
        match = None if fenced else HEADING.match(line)
        if match:
            title = match.group(2).strip()
            plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", title)
            key = re.sub(r"\s+", " ", re.sub(r"[*_`]", "", plain)).strip().casefold()
            key = re.sub(r"^(?:§\s*)?\d+(?:\.\d+)*\.?\s+", "", key)  # renumbered sections are not removals
            if key:
                found.append((len(match.group(1)), title, key))
    return found


def doc_priority(path: str) -> tuple:
    """README and changelog files first, then documentation folders, then other Markdown."""
    name = path.rsplit("/", 1)[-1].upper()
    if name.startswith(("README", "CHANGELOG", "CHANGES", "HISTORY", "RELEASES")):
        return (0, path)
    return (1, path) if set(path.split("/")[:-1]) & DOC_DIRS else (2, path)


def partial_clone(repo: Path) -> bool:
    return any(git(repo, "config", "--get", key, check=False).strip()
               for key in ("remote.origin.partialclonefilter", "extensions.partialclone"))


def show(repo: Path, commit: str, path: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{path}"], capture_output=True)
    return result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else ""


def capped(items: list, top: int) -> list:
    return items[:top] if top > 0 else items


def run_commits(args) -> int:
    repo = Path(args.repo)
    if not is_git_repo(repo):
        raise SystemExit(f"removals: {repo} is not a git working tree")
    old, new = resolve(repo, args.old), resolve(repo, args.new)
    old_files, new_files = tree_files(repo, old["commit"]), tree_files(repo, new["commit"])
    deleted, renamed, modified, skipped = changes(repo, old["commit"], new["commit"])

    gone = folders_of(old_files) - folders_of(new_files)
    outermost = sorted(d for d in gone if "/".join(d.split("/")[:-1]) not in gone)
    removed_dirs, moved_dirs = [], []
    for folder in outermost:
        inside = [f for f in old_files if f.startswith(folder + "/")]
        moves = [(o, n) for o, n in renamed if o.startswith(folder + "/")]
        if inside and len(moves) * 2 >= len(inside):
            moved_dirs.append({"from": folder, "to": destination(folder, moves), "files": len(inside), "renamed": len(moves)})
        else:
            removed_dirs.append({"path": folder, "files": len(inside), "kind": kind_of(folder, is_dir=True)})

    by_kind = Counter(kind_of(p) for p in deleted)
    by_top = Counter(p.split("/")[0] if "/" in p else "(root)" for p in deleted)

    checked, removed_headings = 0, []
    pairs = [(p, p) for p in modified] + [(o, n) for o, n in renamed]
    pairs = [(o, n) for o, n in pairs
             if os.path.splitext(n)[1].lower() in MARKDOWN_EXT and kind_of(n) not in ("tests", "dependencies_or_build")]
    for old_path, new_path in sorted(pairs, key=lambda pair: doc_priority(pair[1]))[: args.max_docs]:
        checked += 1
        kept = {key for _, _, key in headings(show(repo, new["commit"], new_path))}
        seen = set()
        for level, title, key in headings(show(repo, old["commit"], old_path)):
            if key not in kept and key not in seen:
                seen.add(key)
                removed_headings.append({"file": new_path, "heading": title if len(title) <= 160 else title[:157] + "...", "level": level,
                                         **({"was": old_path} if old_path != new_path else {})})

    deleted_docs = sorted(p for p in deleted if kind_of(p) == "docs")
    deleted_source = sorted(p for p in deleted if kind_of(p) == "source_and_other")
    print_json({
        "repo": str(repo.resolve()),
        "old": old,
        "new": new,
        "taken_at": now_utc(),
        "files": {"at_old": len(old_files), "at_new": len(new_files), "deleted": len(deleted),
                  "renamed": len(renamed), "added": len(set(new_files) - set(old_files) - {n for _, n in renamed})},
        "removed_dirs": capped(removed_dirs, args.top),
        "removed_dirs_total": len(removed_dirs),
        "moved_dirs": capped(moved_dirs, args.top),
        "deleted_files": {
            "by_kind": dict(by_kind.most_common()),
            "by_top_level": dict(by_top.most_common(args.top if args.top > 0 else None)),
            "docs": capped(deleted_docs, args.top),
            "docs_total": len(deleted_docs),
            "source_and_other": capped(deleted_source, args.top),
            "source_and_other_total": len(deleted_source),
        },
        "removed_headings": capped(removed_headings, args.top),
        "removed_headings_total": len(removed_headings),
        "markdown_files_checked": checked,
        "markdown_files_not_checked": max(0, len(pairs) - checked),
        "rename_detection": "partial: git skipped part of it because many files changed; raise diff.renameLimit and run again"
                            if skipped else "complete",
        "warnings": ["A partial clone: git fetches file contents from the remote as the comparison needs them, which is "
                     "slower and needs the network. Clone fully for an update."] if partial_clone(repo) else [],
        "note": "Signals, not findings. A folder can move to another package, a heading can be reworded, a feature can "
                "live on behind a flag. Confirm each removal in the code, the docs or the changelog before it becomes a "
                "\"What changed\" row.",
    })
    return 0


def page_lines(path: Path) -> list:
    """The page as readable lines; HTML files are converted to text first."""
    raw = read_text(path)
    if raw is None:
        raise SystemExit(f"removals: cannot read {path} as text")
    if path.suffix.lower() in (".html", ".htm") or raw.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        raw = html_to_text(raw)
    return [line.strip() for line in raw.split("\n")]


def normalize(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip().casefold()


def run_pages(args) -> int:
    old_lines, new_lines = page_lines(args.old), page_lines(args.new)
    old_keys = {normalize(line) for line in old_lines if line}
    new_keys = {normalize(line) for line in new_lines if line}
    added = [key for key in dict.fromkeys(normalize(line) for line in new_lines if line)
             if key not in old_keys and len(key) >= args.min_chars]
    removed, reworded, seen, taken = [], [], set(), set()
    originals = {normalize(line): line for line in new_lines if line}
    for number, line in enumerate(old_lines, 1):
        key = normalize(line)
        if not key or key in new_keys or key in seen or len(key) < args.min_chars:
            continue
        seen.add(key)
        match = difflib.get_close_matches(key, [a for a in added if a not in taken], n=1, cutoff=args.similarity)
        if match:
            taken.add(match[0])
            reworded.append({"line": number, "before": line, "after": originals[match[0]],
                             "similarity": round(difflib.SequenceMatcher(None, key, match[0]).ratio(), 2)})
        else:
            removed.append({"line": number, "text": line})
    print_json({
        "old": {"file": str(args.old), "lines": sum(1 for line in old_lines if line)},
        "new": {"file": str(args.new), "lines": sum(1 for line in new_lines if line)},
        "taken_at": now_utc(),
        "removed": capped(removed, args.top),
        "removed_total": len(removed),
        "reworded": capped(reworded, args.top),
        "reworded_total": len(reworded),
        "added_total": len(added) - len(taken),
        "kept_total": sum(1 for key in old_keys & new_keys if len(key) >= args.min_chars),
        "min_chars": args.min_chars,
        "note": "Line numbers refer to the older capture as text. Date both captures (capture_page.py writes the time "
                "in its .json file; a Wayback snapshot carries it in its id) and confirm each removal on the live page.",
    })
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    commits = sub.add_parser("commits", help="what disappeared between two commits")
    commits.add_argument("repo")
    commits.add_argument("old", help="the baseline: the commit pinned by the earlier analysis")
    commits.add_argument("new", nargs="?", default="HEAD", help="the new snapshot (default HEAD)")
    commits.add_argument("--top", type=int, default=50, help="rows per list; 0 for all")
    commits.add_argument("--max-docs", type=int, default=500, help="Markdown files to compare at most")
    pages = sub.add_parser("pages", help="what disappeared between two captures of a page")
    pages.add_argument("old", type=Path)
    pages.add_argument("new", type=Path)
    pages.add_argument("--min-chars", type=int, default=8, help="skip shorter lines, such as menu items")
    pages.add_argument("--similarity", type=float, default=0.75, help="how close a new line must be to count as a rewording")
    pages.add_argument("--top", type=int, default=50, help="rows per list; 0 for all")
    args = parser.parse_args()
    return run_commits(args) if args.command == "commits" else run_pages(args)


if __name__ == "__main__":
    sys.exit(main())
