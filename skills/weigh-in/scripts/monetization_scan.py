#!/usr/bin/env python3
"""Find how a product makes money: where the paid layer sits in its code, and what its pricing
pages offer.

Usage:
  python3 monetization_scan.py code <repo> [--own-domain example.com] [--at REV] [--include-tests] [--include-docs] [--max-hits 12]
  python3 monetization_scan.py page <capture> [<capture> ...] [--top 40]

`code` reads files only, with the signatures in monetization_signatures.json, and prints JSON with:
  - billing: payment and licensing providers the code or its manifests use (Stripe, Paddle,
    Lemon Squeezy, Polar, RevenueCat, StoreKit and others), with files and lines;
  - license_gates: license keys, license checks, entitlement checks and edition switches;
  - plan_gates: comparisons with plan or tier names, and flags such as isPro or quota limits;
  - offers: in-app offers: links to pricing, upgrade or checkout pages, prices written in the
    code, launch prices and upgrade buttons. Pass --own-domain with the product's site, so links
    to other vendors' pricing (model price lists, for example) are left out;
  - lead_capture: analytics calls that tie an identity or an email to the user;
  - hosted_seams: environment variables that point the app at services the vendor runs (names
    with CLOUD, RELAY, BROKER, MANAGED, HOSTED or INCLUDED and a URL, TOKEN or KEY suffix);
  - paid_folders: folders named like a paid layer (enterprise, ee, premium...) and folders with
    a license file of their own, with its first line.
Tests, lockfiles and docs are left out unless asked; test hits are counted apart.

`page` reads captures of pricing, cloud, enterprise or partner pages (text or HTML, such as the
files capture_page.py or wayback.py fetch --text write) and prints, per file, the lines with
prices (amount, currency, unit), free-tier markers, calls to action, limits and allowances,
billing terms (annual, launch price, cancel any time, setup fees), add-ons and "contact us"
tiers, with a price range per currency.

Everything here is a signal, not a finding. Read each gate in the code: does it run in the build
that ships, and what does it unlock? Quote prices with the page, the plan name and the date.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from common import SKIP_DIRS, html_to_text, is_test_path, iter_files, now_utc, print_json, read_text, rel, tree_at

CODE_EXT = {
    ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".mts", ".cts", ".py", ".go", ".rs", ".java", ".kt", ".kts",
    ".swift", ".m", ".mm", ".cs", ".rb", ".php", ".dart", ".vue", ".svelte", ".astro", ".html", ".json", ".yml",
    ".yaml", ".toml", ".plist", ".xml", ".gradle", ".properties", ".sh", ".ps1", ".ex", ".exs", ".env",
}
MANIFESTS = {"go.mod", "Gemfile", "Podfile", "Package.swift", "requirements.txt", "Pipfile", "Dockerfile"}
DOC_EXT = {".md", ".mdx", ".rst", ".txt", ".adoc"}
LOCKFILES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "Cargo.lock", "Gemfile.lock", "poetry.lock",
    "go.sum", "composer.lock", "Podfile.lock", "Package.resolved", "uv.lock", "Pipfile.lock", "flake.lock",
}
SEAM = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*_(?:URL|URI|TOKEN|KEY|ENDPOINT|HOST|BASE_URL)\b")
LICENSE_FILE = re.compile(r"^(?:LICEN[CS]E|COPYING)(?:[-_.][A-Z0-9]+(?:[.-][0-9]+)*)?(?:\.(?:md|txt|rst|markdown))?$", re.I)


def load_signatures() -> dict:
    with open(Path(__file__).with_name("monetization_signatures.json"), encoding="utf-8") as handle:
        return json.load(handle)


def snippet(line: str) -> str:
    text = line.strip()
    return text if len(text) <= 160 else text[:157] + "..."


def wanted(path: Path, relative: str, args) -> str:
    """'scan', 'test' or '' (skip) for a file."""
    name = path.name
    if name in LOCKFILES or name.endswith((".min.js", ".map")):
        return ""
    ext = path.suffix.lower()
    if ext in DOC_EXT:
        if not args.include_docs:
            return ""
    elif ext not in CODE_EXT and name not in MANIFESTS and not name.startswith(".env"):
        return ""
    if is_test_path(relative):
        return "test" if not args.include_tests else "scan"
    return "scan"


def paid_folders(root: Path, names: set) -> list:
    """Folders named like a paid layer, and folders with a license file of their own, three levels deep."""
    found = []
    for current, dirs, files in os.walk(root):
        relative = Path(current).relative_to(root)
        depth = len(relative.parts)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        if depth >= 3:
            dirs[:] = []
        if depth == 0:
            continue
        path = relative.as_posix()
        own = [f for f in files if LICENSE_FILE.match(f) and Path(f).suffix.lower() not in CODE_EXT]
        by_name = relative.name.lower() in names
        if by_name or own:
            entry = {"path": path, "reason": "name" if by_name and not own else ("own license" if not by_name else "name and own license")}
            if own:
                first = next((l.strip() for l in (read_text(Path(current) / own[0], 4000) or "").split("\n") if l.strip()), "")
                entry["license_file"] = f"{path}/{own[0]}"
                entry["license_first_line"] = first[:100]
            found.append(entry)
    return found


def run_code(args) -> int:
    signatures = load_signatures()
    billing = [(item["name"], [re.compile(p, re.M) for p in item["patterns"]]) for item in signatures["billing"]]
    groups = {key: [(re.compile(entry["pattern"]), entry["strength"]) for entry in signatures[key]]
              for key in ("license_gates", "plan_gates", "offers", "lead_capture")}
    # One combined pattern per group first: most lines match nothing, and this keeps large repositories fast.
    billing_any = re.compile("|".join(f"(?:{p})" for item in signatures["billing"] for p in item["patterns"]), re.M)
    group_any = {key: re.compile("|".join(f"(?:{entry['pattern']})" for entry in signatures[key])) for key in groups}
    seam_words = tuple(signatures["hosted_seam_words"])
    own_domains = [d.lower().lstrip(".") for d in args.own_domain]
    repo = Path(args.repo)
    if not repo.is_dir():
        raise SystemExit(f"monetization_scan: {repo} is not a folder")
    with tree_at(repo, args.at) as root:
        billing_hits = defaultdict(list)
        hits = {key: [] for key in groups}
        seams = {}
        test_hits = Counter()
        scanned = 0
        for path in iter_files(root):
            relative = rel(path, root)
            mode = wanted(path, relative, args)
            if not mode:
                continue
            try:
                if path.stat().st_size > args.max_file_bytes:
                    continue
            except OSError:
                continue
            text = read_text(path)
            if text is None:
                continue
            scanned += 1
            for number, line in enumerate(text.split("\n"), 1):
                if len(line) > 2000:
                    continue
                for name, patterns in (billing if billing_any.search(line) else ()):
                    if any(p.search(line) for p in patterns):
                        if mode == "test":
                            test_hits["billing"] += 1
                        else:
                            billing_hits[name].append({"file": relative, "line": number, "text": snippet(line)})
                for key, patterns in groups.items():
                    if not group_any[key].search(line):
                        continue
                    for pattern, strength in patterns:
                        match = pattern.search(line)
                        if match and key == "offers" and own_domains and match.group(0).startswith("http"):
                            host = re.sub(r"^https?://", "", match.group(0)).split("/")[0].split(":")[0].lower()
                            if not any(host == d or host.endswith("." + d) for d in own_domains):
                                continue  # a link to another vendor's pricing, such as a model price list
                        if match:
                            if mode == "test":
                                test_hits[key] += 1
                            else:
                                hits[key].append({"file": relative, "line": number, "match": match.group(0)[:80],
                                                  "strength": strength, "text": snippet(line)})
                            break
                for seam in SEAM.findall(line):
                    # Whole name parts only: CLOUDFLARE_API_TOKEN is not a CLOUD seam.
                    if mode != "test" and any(f"_{word}_" in f"_{seam}_" for word in seam_words):
                        entry = seams.setdefault(seam, {"name": seam, "files": set(), "first": {"file": relative, "line": number}})
                        entry["files"].add(relative)
        folders = paid_folders(root, {n.lower() for n in signatures["paid_folder_names"]})

    def ranked(items: list) -> list:
        # Strong signals in the product code first; CI and deployment files after them; weak signals last.
        def key(item: dict) -> tuple:
            ci = item["file"].startswith((".github/", ".gitlab", ".circleci/")) or item["file"].endswith((".yml", ".yaml", ".sh"))
            return (item["strength"] != "strong", ci)
        ordered = sorted(items, key=key)
        return ordered[: args.max_hits] if args.max_hits > 0 else ordered

    billing_out = [{"name": name, "hits": len(found), "files": sorted({f["file"] for f in found}),
                    "examples": found[: args.max_hits if args.max_hits > 0 else None]}
                   for name, found in sorted(billing_hits.items(), key=lambda kv: -len(kv[1]))]
    seam_out = sorted(({"name": s["name"], "files": len(s["files"]), "first": s["first"]} for s in seams.values()),
                      key=lambda s: (-s["files"], s["name"]))
    print_json({
        "repo": str(repo.resolve()),
        "at": args.at or None,
        "taken_at": now_utc(),
        "files_scanned": scanned,
        "summary": {"billing": len(billing_out), **{key: len(value) for key, value in hits.items()},
                    "hosted_seams": len(seam_out), "paid_folders": len(folders)},
        "billing": billing_out,
        **{key: ranked(value) for key, value in hits.items()},
        "strong_counts": {key: sum(1 for i in value if i["strength"] == "strong") for key, value in hits.items()},
        "hosted_seams": seam_out[: args.max_hits * 4 if args.max_hits > 0 else None],
        "paid_folders": folders,
        "hits_in_tests": dict(test_hits),
        "note": "Signals, not findings. Read each gate: does it run in the shipped build, and what does it unlock? "
                "Compare the offers in the code with the pricing page of the same day.",
    })
    return 0


CURRENCY = {"$": "USD", "US$": "USD", "USD": "USD", "€": "EUR", "EUR": "EUR", "£": "GBP", "GBP": "GBP"}
NUMBER = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
PRICE = re.compile(rf"(?P<pre>US\$|\$|€|£|\b(?:USD|EUR|GBP)\s?)(?P<a>{NUMBER})|(?P<b>{NUMBER})\s?(?P<post>€|£|\b(?:USD|EUR|GBP)\b)")
UNIT = re.compile(r"(?i)(?:/\s?|\bper\s|\ba\s|\beach\s)(month|mo|year|yr|annum|seat|user|person|member|workspace|hour|minute|GB|TB|request|credit|agent|bot|computer|machine|day)s?\b")
PAGE_RULES = {
    "free": re.compile(r"(?i)\bfree\b|(?:\$|€|£)\s?0(?![\d.,])|\bforever\b|open[- ]source"),
    "ctas": re.compile(r"(?i)^(get|start|try|buy|subscribe|upgrade|download|book a (call|demo)|talk to (us|sales)|contact (us|sales)|join|sign up|choose)\b"),
    "limits": re.compile(r"(?i)\bup to \d|\bunlimited\b|\bfair[- ]use\b|\ballowances?\b|\b\d[\d,.]*\s?(?:hours?|minutes?|GB|TB|seats?|users?|people|persons?|workspaces?|computers?|agents?|bots?|projects?|credits?|requests?|vCPU|messages?)\b"),
    "terms": re.compile(r"(?i)billed (?:yearly|annually|monthly)|\bannual(?:ly)?\b|\bmonths? free\b|launch price|\bfirst \d+\b|\bdiscount\b|% off|cancel any ?time|set-?up (?:fee|of)|one-time|\bminimum\b|\bcontract\b|\bagreement\b|plus (?:applicable )?tax|tax may be added"),
    "add_ons": re.compile(r"(?i)\+\s?(?:\$|€|£)\s?\d|\beach extra\b|\bper extra\b|\bextra [a-z-]+(?: [a-z-]+)? (?:are|is|cost)\b|\badd-?ons?\b"),
    "contact": re.compile(r"(?i)\bcustom\b|contact (?:us|sales)|talk to us|priced on a call|let's talk|book a call|starts with a call|on a call"),
}


def to_number(text: str) -> float:
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", text):
        return float(re.sub(r"[.,]", "", text))
    match = re.fullmatch(r"(\d{1,3}(?:[.,]\d{3})*|\d+)[.,](\d{1,2})", text)
    if match:
        return float(re.sub(r"[.,]", "", match.group(1)) + "." + match.group(2))
    return float(re.sub(r"[.,]", "", text))


def page_report(path: Path, top: int) -> dict:
    raw = read_text(path)
    if raw is None:
        raise SystemExit(f"monetization_scan: cannot read {path} as text")
    if path.suffix.lower() in (".html", ".htm") or raw.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        raw = html_to_text(raw)
    lines = [line.strip() for line in raw.split("\n")]
    prices, groups = [], {key: [] for key in PAGE_RULES}
    ranges = defaultdict(list)
    for number, line in enumerate(lines, 1):
        if not line:
            continue
        amounts = []
        for match in PRICE.finditer(line):
            symbol = (match.group("pre") or match.group("post") or "").strip()
            value = to_number(match.group("a") or match.group("b"))
            currency = CURRENCY.get(symbol, symbol)
            amounts.append({"currency": currency, "amount": value})
            ranges[currency].append(value)
        if amounts:
            prices.append({"line": number, "text": snippet(line), "amounts": amounts,
                           "units": sorted({u.lower() for u in UNIT.findall(line)})})
        for key, rule in PAGE_RULES.items():
            if key == "ctas" and len(line) > 60:
                continue
            if rule.search(line):
                groups[key].append({"line": number, "text": snippet(line)})
    cap = (lambda items: items[:top]) if top > 0 else (lambda items: items)
    return {
        "file": str(path),
        "lines": sum(1 for line in lines if line),
        "price_lines": len(prices),
        "price_range": {c: {"min": min(v), "max": max(v), "count": len(v)} for c, v in sorted(ranges.items())},
        "prices": cap(prices),
        **{key: cap(value) for key, value in groups.items()},
        "counts": {key: len(value) for key, value in groups.items()},
    }


def run_page(args) -> int:
    print_json({
        "taken_at": now_utc(),
        "pages": [page_report(path, args.top) for path in args.captures],
        "note": "Quote each price with its plan name, the page and the capture time (capture_page.py writes it in its "
                ".json file). A line can belong to several groups; read the page around it before you quote.",
    })
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    code = sub.add_parser("code", help="where the paid layer sits in a codebase")
    code.add_argument("repo")
    code.add_argument("--at", default="", help="scan this revision's tree without a checkout")
    code.add_argument("--include-tests", action="store_true")
    code.add_argument("--include-docs", action="store_true")
    code.add_argument("--max-hits", type=int, default=12, help="rows per list; 0 for all")
    code.add_argument("--max-file-bytes", type=int, default=1_000_000)
    code.add_argument("--own-domain", action="append", default=[],
                      help="the product's own site domain, repeatable: links to pricing pages on other domains are left out")
    page = sub.add_parser("page", help="what a pricing, cloud, enterprise or partner page offers")
    page.add_argument("captures", nargs="+", type=Path)
    page.add_argument("--top", type=int, default=40, help="rows per list; 0 for all")
    args = parser.parse_args()
    return run_code(args) if args.command == "code" else run_page(args)


if __name__ == "__main__":
    sys.exit(main())
