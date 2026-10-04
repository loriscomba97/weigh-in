#!/usr/bin/env python3
"""Summarize a repository's history: commits, authors, cadence, fixes, releases, hotspots and
signs of AI-assisted development.

Usage:
  python3 git_stats.py <repo> [--since 2026-01-01] [--until 2026-10-01] [--top 10]
                              [--fix-regex REGEX] [--rev HEAD]

Reads history with git log; never writes to the repository. Prints JSON with:
  - commits, merges and non-merge commits, first and last dates;
  - authors by email, with shares of non-merge commits, the top-1 and top-5 shares and a
    "bus factor": the fewest authors who wrote half of the non-merge commits; the same figures with
    likely duplicate identities merged; bots and assistants that author commits, kept out of the
    email domains;
  - commits per ISO week;
  - the share of non-merge commits whose subject reads as a fix;
  - version tags with dates and the gaps between releases;
  - the files touched by the most non-merge commits;
  - AI-assisted development: co-author trailers by assistant, bot authors, merges of
    assistant branches and agent instruction files at HEAD (patterns in ai_signals.json).
Trailers are optional, so AI counts are a lower bound. Author emails are summarized by
domain only; names are kept because they are public in the history.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from common import git, is_git_repo, now_utc, parse_iso, print_json

RECORD = "\x1e"
FIELD = "\x1f"
DEFAULT_FIX = r"^(?:\w+\()?(?:fix|fixes|fixed|bugfix|hotfix)\b|^\w+(?:\([^)]*\))?!?:\s*fix\b|\bfix(?:es|ed)?\b|\bbug\b"
VERSION_TAG = re.compile(r"^(?:[A-Za-z][\w.-]*[-_/])?v?\d+(?:\.\d+)+(?:[-+.][0-9A-Za-z.-]+)?$")
NOREPLY = re.compile(r"^(?:\d+\+)?([^@]+)@users\.noreply\.github\.com$", re.I)


def load_signals() -> dict:
    with open(Path(__file__).with_name("ai_signals.json"), encoding="utf-8") as handle:
        return json.load(handle)


def author_key(name: str, email: str) -> str:
    email = email.strip().lower()
    match = NOREPLY.match(email)
    if match:
        return f"github:{match.group(1)}"
    return email or name.strip().lower()


def read_log(repo: Path, rev: str, since: str, until: str) -> list:
    fmt = "%x1f".join(["%H", "%an", "%ae", "%aI", "%P", "%s", "%b"]) + "%x1e"
    args = ["log", rev, f"--format={fmt}"]
    if since:
        args.append(f"--since={since}")
    if until:
        args.append(f"--until={until}")
    commits = []
    for record in git(repo, *args).split(RECORD):
        record = record.strip("\n")
        if not record:
            continue
        parts = record.split(FIELD)
        if len(parts) < 7:
            continue
        sha, name, email, date, parents, subject, body = parts[:7]
        commits.append({
            "sha": sha, "name": name, "email": email, "date": date,
            "merge": len(parents.split()) > 1, "subject": subject, "body": body,
        })
    return commits


def bus_factor(counts: list, total: int) -> int:
    """The fewest authors whose commits add up to half of all commits."""
    running, bus = 0, 0
    for n in sorted(counts, reverse=True):
        running += n
        bus += 1
        if total and running * 2 >= total:
            break
    return bus


def authors_summary(commits: list, top: int, bots: list) -> dict:
    counts = Counter()
    names = defaultdict(Counter)
    domains = Counter()
    automated = Counter()
    for c in commits:
        if c["merge"]:
            continue
        key = author_key(c["name"], c["email"])
        counts[key] += 1
        names[key][c["name"]] += 1
        if any(b.search(c["name"]) for b in bots):
            # Bots and assistants that author commits under their own name are not people: their
            # email domain says who makes the tool, not who works on the project.
            automated[c["name"]] += 1
            continue
        domain = c["email"].split("@")[-1].lower() if "@" in c["email"] else "(none)"
        domains["users.noreply.github.com" if domain.endswith("users.noreply.github.com") else domain] += 1
    total = sum(counts.values())
    ranked = counts.most_common()
    bus = bus_factor([n for _, n in ranked], total)
    share = lambda n: round(100 * n / total, 1) if total else 0.0
    # The same person often commits under two identities (a work email and a GitHub noreply one).
    # Flag keys whose names fold to the same letters; the analyst decides whether to merge them.
    fold = lambda s: re.sub(r"[\W_]", "", s.casefold())
    groups = defaultdict(set)
    for key, counter in names.items():
        handles = [key.split(":", 1)[1]] if key.startswith("github:") else []
        for value in handles + list(counter):
            folded = fold(value)
            if len(folded) >= 4:
                groups[folded].add(key)
    duplicates, merged_groups = [], []
    for keys in groups.values():
        if len(keys) > 1:
            entry = {"names": sorted({n for k in keys for n in names[k]}), "identities": len(keys),
                     "commits": sum(counts[k] for k in keys)}
            if entry not in duplicates:
                duplicates.append(entry)
                merged_groups.append(set(keys))
    duplicates.sort(key=lambda e: -e["commits"])
    # The same numbers with those identities merged, so shares and the bus factor count people.
    owner = {}
    for index, keys in enumerate(merged_groups):
        for key in keys:
            owner.setdefault(key, f"group:{index}")
    merged, merged_names = Counter(), defaultdict(Counter)
    for key, n in counts.items():
        merged[owner.get(key, key)] += n
        merged_names[owner.get(key, key)].update(names[key])
    merged_ranked = merged.most_common()
    return {
        "distinct_authors": len(counts),
        "authors_with_10_plus": sum(1 for n in counts.values() if n >= 10),
        "authors_with_one": sum(1 for n in counts.values() if n == 1),
        "top": [{"author": names[k].most_common(1)[0][0], "commits": n, "share_pct": share(n)} for k, n in ranked[:top]],
        "top1_share_pct": share(ranked[0][1]) if ranked else 0.0,
        "top5_share_pct": share(sum(n for _, n in ranked[:5])),
        "bus_factor_50": bus,
        "possible_same_person": duplicates,
        "with_identities_merged": {
            "top": [{"author": merged_names[k].most_common(1)[0][0], "commits": n, "share_pct": share(n)} for k, n in merged_ranked[:5]],
            "top1_share_pct": share(merged_ranked[0][1]) if merged_ranked else 0.0,
            "bus_factor_50": bus_factor([n for _, n in merged_ranked], total),
        },
        "automated_authors": dict(automated.most_common(10)),
        "email_domains": dict(domains.most_common(10)),
        "note": ("Authors are keyed by email. with_identities_merged groups the identities in possible_same_person: "
                 "check those groups, then quote the merged figures. Bots and assistants that author commits are "
                 "counted in the totals but left out of email_domains."),
    }


def weekly(commits: list) -> list:
    weeks = defaultdict(lambda: {"commits": 0, "non_merge": 0})
    for c in commits:
        year, week, _ = parse_iso(c["date"]).isocalendar()
        key = f"{year}-W{week:02d}"
        weeks[key]["commits"] += 1
        if not c["merge"]:
            weeks[key]["non_merge"] += 1
    return [{"week": k, **v} for k, v in sorted(weeks.items())]


def releases(repo: Path) -> dict:
    out = git(repo, "for-each-ref", "--sort=creatordate", "--format=%(refname:short)%1f%(creatordate:iso-strict)", "refs/tags")
    tags = []
    for line in out.splitlines():
        if FIELD not in line:
            continue
        name, date = line.split(FIELD, 1)
        if VERSION_TAG.match(name) and date:
            tags.append((name, parse_iso(date)))
    gaps = [(b[1] - a[1]).total_seconds() / 3600 for a, b in zip(tags, tags[1:])]
    return {
        "version_tags": len(tags),
        "first": {"tag": tags[0][0], "date": tags[0][1].isoformat()} if tags else None,
        "last": {"tag": tags[-1][0], "date": tags[-1][1].isoformat()} if tags else None,
        "mean_gap_hours": round(statistics.mean(gaps), 1) if gaps else None,
        "median_gap_hours": round(statistics.median(gaps), 1) if gaps else None,
        "gaps_under_24h": sum(1 for g in gaps if g < 24),
        "recent": [{"tag": t, "date": d.isoformat()} for t, d in tags[-10:]],
        "note": "Tag dates are when the tag object or its commit was created; check the forge's release pages for publish dates.",
    }


def hotspots(repo: Path, rev: str, since: str, until: str, top: int) -> list:
    args = ["log", rev, "--no-merges", "--name-only", "--format=%x1e"]
    if since:
        args.append(f"--since={since}")
    if until:
        args.append(f"--until={until}")
    counts = Counter()
    for record in git(repo, *args).split(RECORD):
        for path in set(filter(None, (line.strip() for line in record.splitlines()))):
            counts[path] += 1
    return [{"path": p, "commits": n} for p, n in counts.most_common(top)]


def ai_signals(repo: Path, rev: str, commits: list, signals: dict) -> dict:
    trailer = re.compile(r"^\s*(?:" + "|".join(re.escape(k) for k in signals["trailer_keys"]) + r")\s*:\s*(.+)$", re.I | re.M)
    assistants = [(a["label"], [re.compile(p, re.I) for p in a["patterns"]]) for a in signals["assistants"]]
    bots = [re.compile(p, re.I) for p in signals["bot_author_patterns"]]
    by_assistant = Counter()
    with_trailer = 0
    non_merge = [c for c in commits if not c["merge"]]
    for c in non_merge:
        labels = set()
        for value in trailer.findall(c["body"]):
            for label, patterns in assistants:
                if any(p.search(value) for p in patterns):
                    labels.add(label)
        if labels:
            with_trailer += 1
            by_assistant.update(labels)
    bot_commits = Counter(c["name"] for c in non_merge if any(b.search(c["name"]) for b in bots))
    prefixes = signals["branch_prefixes"]
    branch_merges = Counter()
    for c in commits:
        if c["merge"]:
            for prefix in prefixes:
                if prefix in c["subject"]:
                    branch_merges[prefix] += 1
    tree = set(git(repo, "ls-tree", "-r", "--name-only", rev).splitlines())
    instruction = []
    for item in signals["instruction_files"]:
        if item.endswith("/"):
            if any(path.startswith(item) or f"/{item}" in path for path in tree):
                instruction.append(item)
        elif item in tree or any(path.endswith("/" + item) for path in tree):
            instruction.append(item)
    total = len(non_merge)
    return {
        "non_merge_commits_with_assistant_trailer": with_trailer,
        "share_pct": round(100 * with_trailer / total, 1) if total else 0.0,
        "by_assistant": dict(by_assistant.most_common()),
        "bot_authored_commits": dict(bot_commits.most_common(10)),
        "merges_of_assistant_branches": dict(branch_merges.most_common()),
        "agent_instruction_files_at_head": instruction,
        "note": "A lower bound: trailers are optional and some tools add none. Read a sample of the commits before you quote a share.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo")
    parser.add_argument("--rev", default="HEAD", help="revision whose history to read (default HEAD)")
    parser.add_argument("--since", default="", help="only commits after this date, e.g. 2026-01-01")
    parser.add_argument("--until", default="", help="only commits before this date")
    parser.add_argument("--top", type=int, default=10, help="rows in the author and hotspot lists")
    parser.add_argument("--fix-regex", default=DEFAULT_FIX, help="regex that marks a commit subject as a fix")
    args = parser.parse_args()

    repo = Path(args.repo)
    if not is_git_repo(repo):
        parser.error(f"{repo} is not a git working tree")
    commits = read_log(repo, args.rev, args.since, args.until)
    signals = load_signals()
    bot_patterns = [re.compile(b, re.I) for b in signals["bot_author_patterns"]]
    non_merge = [c for c in commits if not c["merge"]]
    fix = re.compile(args.fix_regex, re.I)
    fixes = sum(1 for c in non_merge if fix.search(c["subject"]))
    # Sort by the instant, not the text: offsets differ between authors, so string order is wrong.
    ordered = sorted(commits, key=lambda c: parse_iso(c["date"]))
    print_json({
        "repo": str(repo.resolve()),
        "rev": args.rev,
        "head": git(repo, "rev-parse", args.rev).strip(),
        "window": {"since": args.since or None, "until": args.until or None},
        "taken_at": now_utc(),
        "commits": {"all": len(commits), "merges": len(commits) - len(non_merge), "non_merge": len(non_merge),
                    "first": ordered[0]["date"] if ordered else None, "last": ordered[-1]["date"] if ordered else None},
        "authors": authors_summary(commits, args.top, bot_patterns),
        "weekly": weekly(commits),
        "fixes": {"non_merge_fix_commits": fixes,
                  "share_pct": round(100 * fixes / len(non_merge), 1) if non_merge else 0.0,
                  "regex": args.fix_regex},
        "releases": releases(repo),
        "hotspots": hotspots(repo, args.rev, args.since, args.until, args.top),
        "ai_assisted": ai_signals(repo, args.rev, commits, signals),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
