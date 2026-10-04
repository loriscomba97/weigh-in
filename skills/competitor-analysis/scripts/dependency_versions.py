#!/usr/bin/env python3
"""List the third-party components a codebase depends on, at the versions it pins, and on request
how far each one is behind the latest version published upstream.

Usage:
  python3 dependency_versions.py <repo> [--only NAME ...] [--prod-only] [--check-latest] [--max-lookups 40] [--rows]

Reads manifests and lockfiles only: nothing is installed, built or run.
  - npm: package.json (declared ranges); package-lock.json, pnpm-lock.yaml and yarn.lock (resolved);
  - Python: pyproject.toml and requirements*.txt (declared); poetry.lock and uv.lock (resolved);
  - Rust: Cargo.toml (declared); Cargo.lock (resolved);
  - Go: go.mod (required versions; indirect ones are marked);
  - Swift: Package.resolved; CocoaPods: Podfile.lock (pinned versions).
Prints one entry per component (ecosystem and name) with every declared range and resolved version
found and the number of manifests that use it; --rows adds one row per manifest.
--only keeps the names that match one of the given shell patterns ("electron", "@scope/*").
Development dependencies are kept, marked "dev", because some ship (Electron is one); --prod-only
drops them and indirect Go requirements.

With --check-latest, asks the public registry for each direct dependency's latest version, one GET
at a time (npm, PyPI, crates.io and the Go module proxy; Swift and CocoaPods pins are not looked
up), and says how far the resolved version is behind: major, minor, patch or current.

Why it matters: a competitor's weakness may come from an old component that upstream fixed long
ago, and the reverse: a comparison against the latest upstream release can be wrong for the version
they actually ship. Read the upstream changelog between the two versions before you write either.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Optional

from common import USER_AGENT, iter_files, now_utc, print_json, read_text, rel

MANIFESTS = {"package.json", "pyproject.toml", "Cargo.toml", "go.mod", "Package.resolved", "Podfile.lock"}
LOCKS = {"package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "uv.lock", "Cargo.lock"}
REQUIREMENTS = re.compile(r"^requirements[\w.-]*\.txt$", re.I)
PEP508 = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*(.*)$")


def norm_py(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


# ---------- declared dependencies ----------

def from_package_json(text: str) -> list:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    rows = []
    for key, kind in (("dependencies", "prod"), ("optionalDependencies", "optional"), ("peerDependencies", "peer"), ("devDependencies", "dev")):
        for name, spec in (data.get(key) or {}).items():
            if isinstance(spec, str):
                rows.append({"ecosystem": "npm", "name": name, "declared": spec, "kind": kind})
    return rows


def toml_tables(text: str):
    """(table name, body lines) for each [table] in a TOML file: enough for dependency tables."""
    table, lines = "", []
    for raw in text.splitlines():
        line = raw.split(" #")[0].rstrip() if not raw.lstrip().startswith("#") else ""
        header = re.match(r"^\s*\[\[?([^\]]+)\]\]?\s*$", line)
        if header:
            yield table, lines
            table, lines = header.group(1).strip(), []
        elif line.strip():
            lines.append(line)
    yield table, lines


def toml_strings_in_array(lines: list, key: str) -> list:
    """The strings of `key = [ ... ]`, on one line or across several."""
    body, inside = "", False
    for line in lines:
        if not inside and re.match(rf"^\s*{re.escape(key)}\s*=\s*\[", line):
            inside, line = True, line.split("=", 1)[1]
        if inside:
            body += line + "\n"
            if body.count("[") <= body.count("]"):
                break
    return re.findall(r"\"([^\"]+)\"|'([^']+)'", body)


def from_pyproject(text: str) -> list:
    rows = []

    def add_pep508(spec: str, kind: str) -> None:
        match = PEP508.match(spec)
        if match:
            rows.append({"ecosystem": "pypi", "name": match.group(1), "declared": match.group(3).split(";")[0].strip() or "*", "kind": kind})

    for table, lines in toml_tables(text):
        if table == "project":
            for a, b in toml_strings_in_array(lines, "dependencies"):
                add_pep508(a or b, "prod")
        elif table in ("project.optional-dependencies", "dependency-groups"):
            for line in lines:
                group = re.match(r"^\s*([\w.-]+)\s*=", line)
                if group:
                    kind = "dev" if re.search(r"dev|test|lint|doc", group.group(1), re.I) else "optional"
                    for a, b in toml_strings_in_array(lines[lines.index(line):], group.group(1)):
                        add_pep508(a or b, kind)
        elif re.match(r"^tool\.poetry\.(dependencies|dev-dependencies|group\.[\w-]+\.dependencies)$", table):
            kind = "prod" if table == "tool.poetry.dependencies" else "dev"
            for line in lines:
                match = re.match(r"^\s*([A-Za-z0-9][\w.-]*)\s*=\s*(.+)$", line)
                if not match or match.group(1).lower() == "python":
                    continue
                value = match.group(2).strip()
                version = re.search(r"version\s*=\s*\"([^\"]+)\"", value) if value.startswith("{") else re.match(r"^\"([^\"]+)\"", value)
                rows.append({"ecosystem": "pypi", "name": match.group(1), "declared": version.group(1) if version else value[:60], "kind": kind})
    return rows


def from_requirements(text: str, dev: bool) -> list:
    rows = []
    for raw in text.splitlines():
        line = raw.split("#")[0].strip()
        if not line or line.startswith(("-", "git+", "http:", "https:", "file:", ".")):
            continue
        match = PEP508.match(line)
        if match:
            rows.append({"ecosystem": "pypi", "name": match.group(1), "declared": match.group(3).split(";")[0].strip() or "*", "kind": "dev" if dev else "prod"})
    return rows


def from_cargo_toml(text: str) -> list:
    rows = []
    kinds = {"dependencies": "prod", "dev-dependencies": "dev", "build-dependencies": "build"}
    for table, lines in toml_tables(text):
        single = re.search(r"(^|\.)(dependencies|dev-dependencies|build-dependencies)\.([A-Za-z0-9_-]+)$", table)
        if single:
            body = " ".join(lines)
            version = re.search(r"version\s*=\s*\"([^\"]+)\"", body)
            declared = version.group(1) if version else ("workspace" if "workspace" in body else "path" if "path" in body else "git")
            rows.append({"ecosystem": "crates", "name": single.group(3), "declared": declared, "kind": kinds[single.group(2)]})
            continue
        kind_match = re.search(r"(^|\.)(dependencies|dev-dependencies|build-dependencies)$", table)
        if not kind_match:
            continue
        kind = kinds[kind_match.group(2)]
        for line in lines:
            match = re.match(r"^\s*([A-Za-z0-9_-]+)(\.workspace)?\s*=\s*(.+)$", line)
            if not match:
                continue
            value = match.group(3).strip()
            if match.group(2) or "workspace = true" in value:
                declared = "workspace"
            elif value.startswith("{"):
                version = re.search(r"version\s*=\s*\"([^\"]+)\"", value)
                declared = version.group(1) if version else ("path" if "path" in value else "git" if "git" in value else value[:60])
            else:
                declared = value.strip("\"'")
            rows.append({"ecosystem": "crates", "name": match.group(1), "declared": declared, "kind": kind})
    return rows


def from_go_mod(text: str) -> list:
    rows, block = [], False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("require ("):
            block = True
            continue
        if block and line == ")":
            block = False
            continue
        match = re.match(r"^(?:require\s+)?(\S+)\s+(v\S+)(\s*//\s*indirect)?", line) if (block or line.startswith("require ")) else None
        if match:
            rows.append({"ecosystem": "go", "name": match.group(1), "declared": match.group(2), "resolved": match.group(2),
                         "kind": "indirect" if match.group(3) else "prod"})
    return rows


def from_package_resolved(text: str) -> list:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    pins = data.get("pins") or (data.get("object") or {}).get("pins") or []
    rows = []
    for pin in pins:
        name = pin.get("identity") or pin.get("package") or ""
        state = pin.get("state") or {}
        version = state.get("version") or (state.get("revision") or "")[:12]
        rows.append({"ecosystem": "swift", "name": name, "declared": version, "resolved": version, "kind": "prod",
                     "source": pin.get("location") or pin.get("repositoryURL")})
    return rows


def from_podfile_lock(text: str) -> list:
    rows = []
    for match in re.finditer(r"^  - ([^\s(]+) \(([^)]+)\)", text, re.M):
        rows.append({"ecosystem": "cocoapods", "name": match.group(1), "declared": match.group(2), "resolved": match.group(2), "kind": "prod"})
    return rows


# ---------- resolved versions ----------

def npm_lock_versions(name: str, text: str) -> dict:
    """{package name: resolved version} for the top level of an npm, pnpm or yarn lockfile."""
    versions = {}
    if name in ("package-lock.json", "npm-shrinkwrap.json"):
        try:
            data = json.loads(text)
        except ValueError:
            return {}
        for path, info in (data.get("packages") or {}).items():
            if path.count("node_modules/") == 1 and isinstance(info, dict) and info.get("version"):
                versions.setdefault(path.split("node_modules/", 1)[1], info["version"])
        for pkg, info in (data.get("dependencies") or {}).items():
            if isinstance(info, dict) and info.get("version"):
                versions.setdefault(pkg, info["version"])
    elif name == "pnpm-lock.yaml":
        current, section = None, None
        for line in text.splitlines():
            if re.match(r"^\S", line):
                section = line.rstrip(":")
                continue
            if section == "importers":
                dep = re.match(r"^      ('?[^\s:']+'?):\s*$", line)
                version = re.match(r"^        version:\s*'?([^'\s(]+)", line)
                if dep:
                    current = dep.group(1).strip("'")
                elif version and current:
                    versions.setdefault(current, version.group(1))
            elif section in ("dependencies", "devDependencies", "optionalDependencies"):
                old = re.match(r"^  ('?[^\s:']+'?):\s*'?([^'\s(]+)", line)
                if old:
                    versions.setdefault(old.group(1).strip("'"), old.group(2))
    elif name == "yarn.lock":
        specs = []
        for line in text.splitlines():
            if line and not line.startswith((" ", "#")) and line.rstrip().endswith(":"):
                specs = [s.strip().strip('"') for s in line.rstrip()[:-1].split(",")]
                continue
            version = re.match(r'^\s+version:?\s+"?([^"\s]+)"?', line)
            if version and specs:
                for spec in specs:
                    pkg = spec[: spec.rfind("@")] if spec.rfind("@") > 0 else spec
                    versions.setdefault(pkg, version.group(1))
                specs = []
    return versions


def toml_packages(text: str) -> dict:
    """{name: [versions]} from the [[package]] blocks of Cargo.lock, poetry.lock or uv.lock."""
    found = defaultdict(list)
    for table, lines in toml_tables(text):
        if table != "package":
            continue
        fields = {}
        for line in lines:
            match = re.match(r'^\s*(name|version)\s*=\s*"([^"]+)"', line)
            if match and match.group(1) not in fields:
                fields[match.group(1)] = match.group(2)
        if "name" in fields and "version" in fields:
            found[fields["name"]].append(fields["version"])
    return found


# ---------- upstream lookups ----------

def go_escape(module: str) -> str:
    return re.sub(r"[A-Z]", lambda m: "!" + m.group(0).lower(), module)


def latest_url(ecosystem: str, name: str) -> Optional[str]:
    if ecosystem == "npm":
        return "https://registry.npmjs.org/-/package/" + urllib.parse.quote(name, safe="@") + "/dist-tags"
    if ecosystem == "pypi":
        return f"https://pypi.org/pypi/{urllib.parse.quote(name)}/json"
    if ecosystem == "crates":
        return f"https://crates.io/api/v1/crates/{urllib.parse.quote(name)}"
    if ecosystem == "go":
        return f"https://proxy.golang.org/{go_escape(name)}/@latest"
    return None


def latest_from(ecosystem: str, body: dict) -> Optional[str]:
    if ecosystem == "npm":
        return body.get("latest")
    if ecosystem == "pypi":
        return (body.get("info") or {}).get("version")
    if ecosystem == "crates":
        crate = body.get("crate") or {}
        return crate.get("max_stable_version") or crate.get("newest_version")
    if ecosystem == "go":
        return body.get("Version")
    return None


def version_tuple(value: Optional[str]) -> Optional[tuple]:
    match = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", value or "")
    return tuple(int(g or 0) for g in match.groups()) if match else None


def behind(resolved: Optional[str], latest: Optional[str]) -> str:
    have, want = version_tuple(resolved), version_tuple(latest)
    if not have or not want:
        return "unknown"
    if have > want:
        return "ahead"
    for label, i in (("major", 0), ("minor", 1), ("patch", 2)):
        if have[i] < want[i]:
            return label
    return "current"


def fetch_json(url: str) -> Optional[dict]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError, TimeoutError):
        return None


# ---------- scan ----------

def scan(root: Path) -> list:
    rows, npm_locks, py_locks, cargo_locks = [], {}, {}, {}
    for path in iter_files(root):
        name, folder = path.name, path.parent
        if name not in MANIFESTS and name not in LOCKS and not REQUIREMENTS.match(name):
            continue
        text = read_text(path, limit=20_000_000) or ""
        where = rel(path, root)
        found = []
        if name == "package.json":
            found = from_package_json(text)
        elif name == "pyproject.toml":
            found = from_pyproject(text)
        elif REQUIREMENTS.match(name):
            found = from_requirements(text, dev=bool(re.search(r"dev|test|lint|doc", name, re.I)))
        elif name == "Cargo.toml":
            found = from_cargo_toml(text)
        elif name == "go.mod":
            found = from_go_mod(text)
        elif name == "Package.resolved":
            found = from_package_resolved(text)
        elif name == "Podfile.lock":
            found = from_podfile_lock(text)
        elif name in ("package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock"):
            npm_locks[folder] = (where, npm_lock_versions(name, text))
        elif name in ("poetry.lock", "uv.lock"):
            py_locks[folder] = (where, {norm_py(k): v for k, v in toml_packages(text).items()})
        elif name == "Cargo.lock":
            cargo_locks[folder] = (where, toml_packages(text))
        for row in found:
            row["manifest"] = where
            row["_folder"] = folder
        rows.extend(found)

    def nearest(locks: dict, folder: Path):
        for candidate in [folder, *folder.parents]:
            if candidate in locks:
                return locks[candidate]
            if candidate == root:
                break
        return None

    for row in rows:
        folder = row.pop("_folder")
        if row.get("resolved"):
            continue
        lock = None
        if row["ecosystem"] == "npm":
            lock = nearest(npm_locks, folder)
            version = lock[1].get(row["name"]) if lock else None
        elif row["ecosystem"] == "pypi":
            lock = nearest(py_locks, folder)
            versions = lock[1].get(norm_py(row["name"])) if lock else None
            version = versions[0] if versions else None
        elif row["ecosystem"] == "crates":
            lock = nearest(cargo_locks, folder)
            versions = lock[1].get(row["name"]) if lock else None
            version = ", ".join(sorted(set(versions))) if versions else None
        else:
            version = None
        if version:
            row["resolved"], row["lockfile"] = version, lock[0]
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo", type=Path)
    parser.add_argument("--only", nargs="+", default=[], help="shell patterns of dependency names to keep")
    parser.add_argument("--prod-only", action="store_true", help="drop development dependencies and indirect requirements")
    parser.add_argument("--check-latest", action="store_true", help="look up the latest upstream version (network)")
    parser.add_argument("--max-lookups", type=int, default=40, help="cap on registry requests, one at a time")
    parser.add_argument("--rows", action="store_true", help="also print one row per manifest")
    args = parser.parse_args()
    root = args.repo.resolve()
    if not root.is_dir():
        parser.error(f"{root} is not a folder")

    rows = [r for r in scan(root) if not args.prod_only or r["kind"] not in ("dev", "indirect")]
    if args.only:
        rows = [r for r in rows if any(fnmatch.fnmatch(r["name"], p) for p in args.only)]
    rows.sort(key=lambda r: (r["ecosystem"], r["name"].lower(), r["manifest"]))

    lookups, latest = 0, {}
    if args.check_latest:
        for row in rows:
            key = (row["ecosystem"], row["name"])
            if key in latest or not latest_url(*key):
                continue
            if lookups >= args.max_lookups:
                latest[key] = None
                continue
            if lookups:
                time.sleep(0.3)
            lookups += 1
            body = fetch_json(latest_url(*key))
            latest[key] = latest_from(row["ecosystem"], body) if body else None
        for row in rows:
            key = (row["ecosystem"], row["name"])
            if key in latest:
                row["latest"] = latest[key]
                row["behind"] = behind(row.get("resolved") or row.get("declared"), latest[key]) if latest[key] else "not looked up"

    components = {}
    for row in rows:
        entry = components.setdefault((row["ecosystem"], row["name"]), {
            "ecosystem": row["ecosystem"], "name": row["name"], "kinds": [], "declared": [], "resolved": [],
            "manifests": 0, "example_manifest": row["manifest"]})
        entry["manifests"] += 1
        for field, value in (("kinds", row["kind"]), ("declared", row["declared"]), ("resolved", row.get("resolved"))):
            if value and value not in entry[field]:
                entry[field].append(value)
        if "latest" in row:
            entry["latest"], entry["behind"] = row["latest"], row["behind"]
    by_ecosystem = defaultdict(int)
    for ecosystem, _ in components:
        by_ecosystem[ecosystem] += 1
    print_json({
        "taken_at": now_utc(),
        "root": str(root),
        "components": list(components.values()),
        **({"rows": rows} if args.rows else {}),
        "counts": dict(sorted(by_ecosystem.items())),
        "registry_lookups": lookups,
        "notes": [
            "declared is the range in the manifest; resolved is the version the lockfile pins, which is what ships.",
            "behind compares resolved (or declared, without a lockfile) with the latest upstream release.",
            "Read the upstream changelog between the two versions before you call anything a weakness.",
        ],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
