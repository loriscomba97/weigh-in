#!/usr/bin/env python3
"""Find what a codebase may send home: analytics and error-reporting SDKs, the switches that
control them, and every external host the code mentions.

Usage:
  python3 telemetry_scan.py <repo> [--include-tests] [--include-docs] [--max-hits 8]

Reads files only. Signatures live in telemetry_signatures.json. Prints JSON with:
  - sdks: each SDK found, its kind, and the files and lines that mention it. "strength" is
    "usage" when a line imports, initializes or loads it, and "mention only" when the code just
    names the vendor's domain, as an integration catalog or a docs link does;
  - controls: lines that look like consent, opt-out or telemetry switches;
  - hosts: every external host in the code, with how many files mention it and an example,
    known telemetry hosts flagged.
Everything here is a signal, not a finding. Confirm each one by reading the code path: does it
run by default, before any consent, and what does it send, with which identity? Then compare
the answer with the product's privacy policy.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from common import iter_files, print_json, read_text, rel

TEXT_EXT = {
    ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".mts", ".cts", ".py", ".go", ".rs", ".java", ".kt", ".kts",
    ".swift", ".m", ".mm", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".dart", ".vue", ".svelte",
    ".astro", ".html", ".json", ".yml", ".yaml", ".toml", ".plist", ".xml", ".gradle", ".properties", ".env.example",
    ".sh", ".ps1", ".lua", ".ex", ".exs",
}
DOC_EXT = {".md", ".mdx", ".rst", ".txt", ".adoc"}
TEST_PATH = re.compile(r"(^|/)(__tests__|tests?|spec|specs|e2e|fixtures|testdata|mocks?|__mocks__)(/|$)|\.(test|spec)\.[a-z]+$", re.I)
URL = re.compile(r"https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?::\d+)?")


def load_signatures() -> dict:
    with open(Path(__file__).with_name("telemetry_signatures.json"), encoding="utf-8") as handle:
        return json.load(handle)


BARE_DOMAIN = re.compile(r"[a-z0-9-]+(\\\.[a-z0-9-]+)+")


def hit_strength(line: str, matched: list) -> str:
    """"usage" when the line imports, initializes or loads the SDK; "mention" when it only names
    the vendor's domain, as an integration catalog, a docs link or a settings list does."""
    if any(not BARE_DOMAIN.fullmatch(p.pattern) for p in matched):
        return "usage"
    low = line.lower()
    return "usage" if ("://" in line or "<script" in low or "src=" in low) else "mention"


def scan(root: Path, include_tests: bool, include_docs: bool, max_hits: int) -> dict:
    signatures = load_signatures()
    sdks = [(s, [re.compile(p, re.I) for p in s["patterns"]]) for s in signatures["sdks"]]
    controls = [re.compile(p, re.I) for p in signatures["controls"]]
    # Plain substring checks screen each file and line; the regular expressions run only where a
    # keyword appears. This keeps a scan of a large monorepo to seconds.
    sdk_keywords = [(sdk, patterns, [k.lower() for k in sdk.get("keywords", [])]) for sdk, patterns in sdks]
    control_keywords = [k.lower() for k in signatures.get("control_keywords", [])]
    ignore = tuple(signatures["ignore_hosts"])
    telemetry_hosts = {h: s["name"] for s in signatures["sdks"] for h in s.get("hosts", [])}

    sdk_hits = defaultdict(list)
    sdk_files = defaultdict(set)
    sdk_usage = set()
    control_hits = []
    hosts = defaultdict(lambda: {"files": set(), "example": None})
    scanned = 0
    for path in iter_files(root):
        relative = rel(path, root)
        suffix = path.suffix.lower()
        name = path.name.lower()
        is_doc = suffix in DOC_EXT
        if not (suffix in TEXT_EXT or name in ("package.json", "podfile", "gemfile", "cargo.toml", "go.mod") or (include_docs and is_doc)):
            continue
        if not include_tests and TEST_PATH.search(relative):
            continue
        if name.endswith((".min.js", ".map")) or name in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock"):
            continue
        text = read_text(path, limit=2_000_000)
        if text is None:
            continue
        scanned += 1
        lower = text.lower()
        present = [(sdk, patterns, keys) for sdk, patterns, keys in sdk_keywords if any(k in lower for k in keys)]
        want_controls = len(control_hits) < max_hits * 6 and any(k in lower for k in control_keywords)
        if present or want_controls:
            for number, line in enumerate(text.split("\n"), 1):
                if len(line) > 2000:
                    continue
                low = line.lower()
                for sdk, patterns, keys in present:
                    matched = [p for p in patterns if p.search(line)] if any(k in low for k in keys) else []
                    if matched:
                        strength = hit_strength(line, matched)
                        sdk_files[sdk["name"]].add(relative)
                        if strength == "usage":
                            sdk_usage.add(sdk["name"])
                        if len(sdk_hits[sdk["name"]]) < max_hits:
                            sdk_hits[sdk["name"]].append({"file": relative, "line": number, "match": strength, "text": line.strip()[:160]})
                if want_controls and any(k in low for k in control_keywords) and any(p.search(line) for p in controls):
                    control_hits.append({"file": relative, "line": number, "text": line.strip()[:160]})
                    want_controls = len(control_hits) < max_hits * 6
        if "://" in text:
            for match in URL.finditer(text):
                host = match.group(1).lower().rstrip(".")
                if host.endswith(ignore) or host in ignore:
                    continue
                entry = hosts[host]
                entry["files"].add(relative)
                if entry["example"] is None:
                    entry["example"] = f"{relative}:{text.count(chr(10), 0, match.start()) + 1}"

    def telemetry_of(host: str):
        for known, sdk in telemetry_hosts.items():
            if host == known or host.endswith("." + known):
                return sdk
        return None

    return {
        "files_scanned": scanned,
        "sdks": [
            {"name": sdk["name"], "kind": sdk["kind"], "files": len(sdk_files[sdk["name"]]),
             "strength": "usage" if sdk["name"] in sdk_usage else "mention only", "hits": sdk_hits[sdk["name"]]}
            for sdk, _ in sdks if sdk_files[sdk["name"]]
        ],
        "controls": control_hits,
        "hosts": sorted(
            ({"host": h, "files": len(v["files"]), "example": v["example"], "telemetry": telemetry_of(h)} for h, v in hosts.items()),
            key=lambda r: (r["telemetry"] is None, -r["files"], r["host"]),
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo")
    parser.add_argument("--include-tests", action="store_true", help="also scan tests, fixtures and mocks")
    parser.add_argument("--include-docs", action="store_true", help="also scan Markdown and other docs")
    parser.add_argument("--max-hits", type=int, default=8, help="example lines kept per SDK")
    args = parser.parse_args()
    root = Path(args.repo)
    result = scan(root, args.include_tests, args.include_docs, args.max_hits)
    print_json({
        "repo": str(root.resolve()),
        **result,
        "how_to_confirm": [
            "Open the file where each SDK is initialized: does it run by default, and before any consent screen?",
            "Look for an identify call that links events to an email or account.",
            "List what runs at startup with nothing switched on, including update checks and the vendor's own services.",
            "Compare with the privacy policy and the store privacy labels, with their dates.",
        ],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
