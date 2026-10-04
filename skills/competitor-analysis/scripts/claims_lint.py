#!/usr/bin/env python3
"""Check draft comparison copy before anyone publishes it.

Usage:
  python3 claims_lint.py drafts/*.md [--forbidden phrases.txt] [--max-words 40]
                                     [--competitor "Acme"] [--superlatives] [--strict]

Reads Markdown or text files and prints JSON findings with file and line:
  - forbidden: phrases from a file, one per line, matched as whole words regardless of case;
    a line starting with "re:" is a regular expression, "#" starts a comment;
  - too_long: blockquote answers (lines starting with ">") longer than --max-words, which is how
    the skill drafts FAQ answers;
  - superlative (with --superlatives): "the first", "the only", best, fastest, #1, guaranteed,
    always, never, 100% and similar, which need proof or a softer claim;
  - comparative: with --competitor, "unlike", "better than", "faster than" and similar next to a
    competitor's name: a comparison that needs its proof and its date;
  - undated_number: with --competitor, a line that names a competitor next to a number or
    percentage and has no date in it. Version numbers, file:line citations, inline code and the
    numbers of headings and list items are not counted.
Fenced code is skipped, and so is anything between <!-- claims-lint: off --> and
<!-- claims-lint: on -->, or on a line that carries <!-- claims-lint: ignore -->: use them for the
phrases a "What not to say" section quotes on purpose.
The exit status is 1 when a forbidden or too_long finding exists; the other rules are warnings,
unless --strict makes every finding fail the run.
These are checks on wording. They do not make a claim true: every claim still needs its evidence.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from common import print_json

SUPERLATIVES = re.compile(
    r"(?<!\w)((?:the|our|its|their) (?:first|only)(?!\w)|first[- ]ever|best|fastest|cheapest|leading|#\s?1|number one|guaranteed?|"
    r"always|never|100\s?%|unbeatable|unmatched|world'?s|most (?:advanced|powerful|secure)|zero (?:risk|bugs))(?!\w)",
    re.I,
)
DATE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2} (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{4}|"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2},? \d{4}|(as of|on) \w+ \d{4}|q[1-4] \d{4})\b",
    re.I,
)
NUMBER = re.compile(r"\b\d[\d,.]*\s?(%|k\b|m\b|x\b|stars|users|downloads|customers)?", re.I)
NOT_A_CLAIM = re.compile(
    r"`[^`]*`|\bv?\d+\.\d+(?:\.\d+)+\b|[\w./-]+\.\w+:\d+(?:-\d+)?|\[[^\]]*\]\([^)]*\)|^\s*(?:#+\s*)?\d+[.)]\s",
)
COMPARATIVE = r"(?:unlike|better than|faster than|cheaper than|safer than|more \w+ than|worse than|slower than|instead of|vs\.?|versus)"
OFF, ON, IGNORE = "<!-- claims-lint: off -->", "<!-- claims-lint: on -->", "<!-- claims-lint: ignore -->"


def load_forbidden(path: Path) -> list:
    rules = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("re:"):
            rules.append((line, re.compile(line[3:], re.I)))
        else:
            rules.append((line, re.compile(r"(?<!\w)" + re.escape(line) + r"(?!\w)", re.I)))
    return rules


def lint(path: Path, forbidden: list, max_words: int, competitors: list, superlatives: bool) -> list:
    findings = []
    in_code, muted = False, False
    comparative = [re.compile(rf"\b{COMPARATIVE}\s+{re.escape(c)}\b", re.I) for c in competitors]
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if OFF in line:
            muted = True
        if ON in line:
            muted = False
            continue
        if in_code or muted or IGNORE in line:
            continue
        for label, rule in forbidden:
            if rule.search(line):
                findings.append({"file": str(path), "line": number, "rule": "forbidden", "detail": label})
        if line.startswith(">"):
            words = len(re.findall(r"\S+", line.lstrip("> ").strip()))
            if words > max_words:
                findings.append({"file": str(path), "line": number, "rule": "too_long", "detail": f"{words} words (limit {max_words})"})
        if superlatives:
            for match in SUPERLATIVES.finditer(line):
                findings.append({"file": str(path), "line": number, "rule": "superlative", "detail": match.group(0)})
        for pattern in comparative:
            match = pattern.search(line)
            if match:
                findings.append({"file": str(path), "line": number, "rule": "comparative", "detail": match.group(0)})
        if competitors and any(c.lower() in line.lower() for c in competitors):
            if NUMBER.search(NOT_A_CLAIM.sub(" ", line)) and not DATE.search(line):
                findings.append({"file": str(path), "line": number, "rule": "undated_number", "detail": line.strip()[:120]})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--forbidden", type=Path, help="file of forbidden phrases, one per line")
    parser.add_argument("--max-words", type=int, default=40)
    parser.add_argument("--competitor", action="append", default=[], help="a competitor's name; repeatable")
    parser.add_argument("--superlatives", action="store_true", help="flag superlatives and absolute claims")
    parser.add_argument("--strict", action="store_true", help="fail the run on any finding, warnings included")
    args = parser.parse_args()
    forbidden = load_forbidden(args.forbidden) if args.forbidden else []
    findings = []
    for path in args.files:
        findings.extend(lint(path, forbidden, args.max_words, args.competitor, args.superlatives))
    failing = [f for f in findings if args.strict or f["rule"] in ("forbidden", "too_long")]
    print_json({"files": [str(p) for p in args.files], "findings": findings, "count": len(findings),
                "failing": len(failing), "warnings": len(findings) - len(failing)})
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
