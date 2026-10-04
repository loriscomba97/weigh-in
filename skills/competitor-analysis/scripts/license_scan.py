#!/usr/bin/env python3
"""Map the licenses of a codebase, so you know what you may reuse and on which terms.

Usage:
  python3 license_scan.py <repo> [--include-vendored]

Reads files and, when the folder is a git clone, the history of its license files. Prints JSON:
  - license_files: every LICENSE, COPYING, NOTICE, LICENSING and PATENTS file, with the license
    family recognized from its text and its first copyright line;
  - spdx_headers: SPDX-License-Identifier lines, counted by identifier and by top-level folder;
  - manifests: the license each package manifest declares (package.json, Cargo.toml,
    pyproject.toml, setup.cfg, composer.json, *.gemspec, *.podspec);
  - lockfiles: how many dependencies each lockfile pins (their licenses need a scanner);
  - history: the commits that changed each top-level license file (relicensing shows here);
  - contribution_terms: CLA, DCO and trademark files, and CONTRIBUTING lines that mention them;
  - flags: copyleft, source-available or non-standard terms, more than one license family
    (often open core), and a missing root license.
Recognition is by key phrases, not a legal reading. Confirm every license by reading its text,
and take any reuse decision to counsel.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from common import SKIP_DIRS, git, is_git_repo, iter_files, print_json, read_text, rel

LICENSE_NAME = re.compile(r"^(licen[cs]e|copying|notice|licensing|patents|unlicense)([._-].*)?$", re.I)
CODE_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".go", ".rs", ".json", ".yml", ".yaml", ".toml", ".sh",
                 ".rb", ".java", ".kt", ".swift", ".c", ".h", ".cpp", ".cs", ".php", ".lock", ".xml", ".plist", ".svg",
                 ".png", ".jpg", ".css", ".scss", ".vue", ".svelte"}
CONTRIB_NAME = re.compile(r"^(cla|dco|trademarks?|contributing|contributor[-_]license[-_]agreement)([._-].*)?$", re.I)

# (family, kind, phrases that must all appear). Order matters: the first match wins.
LICENSES = [
    ("AGPL-3.0", "strong copyleft (network)", ["gnu affero general public license"]),
    ("LGPL", "weak copyleft", ["gnu lesser general public license"]),
    ("GPL", "strong copyleft", ["gnu general public license"]),
    ("SSPL-1.0", "source-available", ["server side public license"]),
    ("BUSL-1.1", "source-available", ["business source license"]),
    ("FSL", "source-available (converts to open source later)", ["functional source license"]),
    ("Elastic-2.0", "source-available", ["elastic license"]),
    ("Commons Clause", "source-available restriction", ["commons clause"]),
    ("PolyForm", "source-available", ["polyform"]),
    ("Fair Source", "source-available", ["fair source"]),
    ("MPL-2.0", "weak copyleft (file level)", ["mozilla public license"]),
    ("EPL", "weak copyleft", ["eclipse public license"]),
    ("CDDL", "weak copyleft", ["common development and distribution license"]),
    ("Apache-2.0", "permissive with patent grant", ["apache license", "version 2.0"]),
    ("MIT", "permissive", ["permission is hereby granted, free of charge"]),
    ("BSD-3-Clause", "permissive", ["redistribution and use in source and binary forms", "neither the name"]),
    ("BSD-2-Clause", "permissive", ["redistribution and use in source and binary forms"]),
    ("ISC", "permissive", ["permission to use, copy, modify, and/or distribute this software for any purpose"]),
    ("Zlib", "permissive", ["this software is provided 'as-is'", "altered source versions must be plainly marked"]),
    ("Unlicense", "public domain dedication", ["this is free and unencumbered software released into the public domain"]),
    ("CC0-1.0", "public domain dedication", ["cc0 1.0 universal"]),
    ("CC-BY", "content license", ["creative commons attribution"]),
    ("Proprietary or custom", "custom terms, read in full", ["all rights reserved"]),
]
COPYLEFT = {"AGPL-3.0", "LGPL", "GPL", "MPL-2.0", "EPL", "CDDL"}
SOURCE_AVAILABLE = {"SSPL-1.0", "BUSL-1.1", "FSL", "Elastic-2.0", "Commons Clause", "PolyForm", "Fair Source", "Proprietary or custom"}
SPDX = re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9.+\-() ]+?)\s*(?:\*/|-->|#|$)", re.M)
LOCKFILES = {
    "package-lock.json": "npm", "npm-shrinkwrap.json": "npm", "pnpm-lock.yaml": "pnpm", "yarn.lock": "yarn",
    "bun.lockb": "bun", "Cargo.lock": "cargo", "poetry.lock": "poetry", "uv.lock": "uv", "Pipfile.lock": "pipenv",
    "Package.resolved": "swiftpm", "Podfile.lock": "cocoapods", "go.sum": "go", "Gemfile.lock": "bundler",
    "composer.lock": "composer", "gradle.lockfile": "gradle", "pubspec.lock": "pub", "mix.lock": "mix",
}


def recognize(text: str) -> dict:
    lower = re.sub(r"\s+", " ", text.lower())
    for family, kind, phrases in LICENSES:
        if all(p in lower for p in phrases):
            result = {"family": family, "kind": kind}
            if family == "GPL":
                result["version"] = "3" if "version 3" in lower else ("2" if "version 2" in lower else None)
            if "source code" in lower and "license key" in lower:
                result["note"] = "mentions a license key: likely source-available terms"
            return result
    if "source-available" in lower or "source available" in lower or "license key" in lower:
        return {"family": "Proprietary or custom", "kind": "custom terms, read in full"}
    return {"family": "Unrecognized", "kind": "read in full"}


def copyright_line(text: str):
    for line in text.splitlines()[:60]:
        if re.search(r"copyright\s*(\(c\)|©|\d{4})", line, re.I):
            return re.sub(r"<[^>]*@[^>]*>", "<email>", line.strip())[:160]
    return None


def manifest_license(path: Path, text: str):
    name = path.name
    try:
        if name in ("package.json", "composer.json"):
            data = json.loads(text)
            value = data.get("license") or data.get("licenses")
            return value if isinstance(value, str) else json.dumps(value) if value else None
    except ValueError:
        return None
    patterns = {
        "Cargo.toml": r'^\s*license\s*=\s*"([^"]+)"',
        "pyproject.toml": r'^\s*license\s*=\s*(?:\{\s*text\s*=\s*)?"([^"]+)"',
        "setup.cfg": r"^\s*license\s*=\s*(.+)$",
    }
    if name in patterns:
        match = re.search(patterns[name], text, re.M)
        return match.group(1).strip() if match else None
    if name.endswith((".gemspec", ".podspec")):
        match = re.search(r"\.licen[cs]es?\s*=\s*(?:\{\s*:type\s*=>\s*)?['\"]([^'\"]+)['\"]", text)
        return match.group(1) if match else None
    return None


def lockfile_entries(name: str, text: str) -> int:
    if name in ("package-lock.json", "npm-shrinkwrap.json"):
        try:
            data = json.loads(text)
        except ValueError:
            return 0
        packages = data.get("packages") or data.get("dependencies") or {}
        return len([k for k in packages if k])
    if name == "pnpm-lock.yaml":
        section = text.split("\npackages:", 1)[-1].split("\nsnapshots:", 1)[0]
        return len(re.findall(r"^  '?/?(@?[^\s:'@][^\s:']*)@[^:]+:", section, re.M))
    if name == "yarn.lock":
        return len(re.findall(r'^"?(@?[^\s",@][^\s",]*)@', text, re.M))
    if name in ("Cargo.lock", "poetry.lock", "uv.lock"):
        return text.count("[[package]]")
    if name == "Package.resolved":
        return text.count('"identity"') or text.count('"package"')
    if name == "Podfile.lock":
        block = text.split("PODS:", 1)[-1].split("\n\n", 1)[0]
        return len(re.findall(r"^  - ", block, re.M))
    if name == "go.sum":
        return len({line.split()[0] for line in text.splitlines() if line.strip()})
    if name in ("Gemfile.lock", "composer.lock", "Pipfile.lock", "pubspec.lock", "mix.lock", "gradle.lockfile"):
        return len(re.findall(r'^\s{4}[\w.-]+ \(|"name":\s*"', text, re.M)) or len(text.splitlines())
    return 0


def scan(root: Path, include_vendored: bool) -> dict:
    skip = set() if include_vendored else SKIP_DIRS
    license_files, contrib = [], []
    spdx_by_id, spdx_by_area = Counter(), defaultdict(Counter)
    manifests, lockfiles = [], []
    walker = iter_files(root, skip_dirs=skip | {".git"})
    for path in walker:
        relative = rel(path, root)
        name = path.name
        if LICENSE_NAME.match(name) and path.suffix.lower() not in CODE_SUFFIXES:
            text = read_text(path) or ""
            license_files.append({"path": relative, **recognize(text), "copyright": copyright_line(text)})
            continue
        if CONTRIB_NAME.match(name):
            text = read_text(path) or ""
            mentions = [line.strip()[:160] for line in text.splitlines()
                        if re.search(r"contributor license agreement|\bcla\b|developer certificate of origin|signed-off-by|\bdco\b|trademark", line, re.I)]
            contrib.append({"path": relative, "mentions": mentions[:6]})
        if name in LOCKFILES:
            text = read_text(path) or ""
            lockfiles.append({"path": relative, "ecosystem": LOCKFILES[name], "entries": lockfile_entries(name, text)})
            continue
        if name in ("package.json", "Cargo.toml", "pyproject.toml", "setup.cfg", "composer.json") or name.endswith((".gemspec", ".podspec")):
            text = read_text(path) or ""
            declared = manifest_license(path, text)
            if declared:
                manifests.append({"path": relative, "license": declared})
        if path.suffix.lower() in (".md", ".txt", ".json", ".lock", ".svg", ".png", ".jpg"):
            continue
        text = read_text(path, limit=4000)
        if text and "SPDX-License-Identifier" in text:
            match = SPDX.search(text)
            if match:
                spdx_by_id[match.group(1).strip()] += 1
                spdx_by_area[relative.split("/")[0] if "/" in relative else "(root)"][match.group(1).strip()] += 1

    history = {}
    if is_git_repo(root):
        for item in license_files:
            if "/" not in item["path"]:
                log = git(root, "log", "--follow", "--format=%h%x1f%aI%x1f%s", "--", item["path"], check=False)
                history[item["path"]] = [dict(zip(("commit", "date", "subject"), line.split("\x1f"))) for line in log.splitlines() if line]

    families = {f["family"] for f in license_files if f["family"] not in ("Unrecognized",)}
    root_license = [f for f in license_files if "/" not in f["path"] and f["path"].lower().startswith(("licen", "copying"))]
    return {
        "license_files": license_files,
        "spdx_headers": {"by_identifier": dict(spdx_by_id.most_common()), "by_area": {a: dict(c) for a, c in spdx_by_area.items()}},
        "manifests": manifests,
        "lockfiles": lockfiles,
        "history": history,
        "contribution_terms": contrib,
        "flags": {
            "copyleft": sorted(families & COPYLEFT),
            "source_available_or_custom": sorted(families & SOURCE_AVAILABLE),
            "more_than_one_family": len(families) > 1,
            "missing_root_license": not root_license,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo")
    parser.add_argument("--include-vendored", action="store_true", help="also read vendored and dependency folders")
    args = parser.parse_args()
    root = Path(args.repo)
    print_json({
        "repo": str(root.resolve()),
        **scan(root, args.include_vendored),
        "next_steps": [
            "Read every license and NOTICE in full; key phrases only point at the family.",
            "For the dependency licenses, run a scanner for the ecosystem (for example license-checker, cargo-deny, pip-licenses or ScanCode).",
            "Note what ships in the binaries: notices bundled or missing, pinned versions, SBOMs.",
            "Take every reuse decision to counsel. This output is not legal advice.",
        ],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
