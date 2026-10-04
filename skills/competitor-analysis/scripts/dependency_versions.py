#!/usr/bin/env python3
"""List the third-party components a codebase depends on, at the versions it pins, and on request
how far each one is behind the latest version published upstream, and since when.

Usage:
  python3 dependency_versions.py <repo> [--at REV] [--only NAME ...] [--prod-only] [--check-latest] [--dates]
                                        [--max-lookups 40] [--rows]

Reads manifests and lockfiles only: nothing is installed, built or run.
  - npm: package.json (declared ranges); package-lock.json, pnpm-lock.yaml and yarn.lock (resolved,
    per workspace package when the lockfile records it);
  - Python: pyproject.toml and requirements*.txt (declared); poetry.lock and uv.lock (resolved);
  - Rust: Cargo.toml (declared); Cargo.lock (resolved);
  - Go: go.mod (required versions; indirect ones are marked);
  - Java and Kotlin, Android included: build.gradle and build.gradle.kts, with version catalogs
    (gradle/*.versions.toml);
  - Swift: Package.swift, Xcode projects and XcodeGen project.yml (declared requirements);
    Package.resolved (pinned);
  - CocoaPods: Podfile.lock (pinned);
  - components copied into vendored folders (third_party/, vendor/) that ship a CycloneDX or SPDX
    SBOM: the component the SBOM describes, marked "vendored".
Prints one entry per component (ecosystem and name) with every declared range and resolved version
found and the number of manifests that use it; --rows adds one row per manifest.
--only keeps the names that match one of the given shell patterns ("electron", "@scope/*").
Development dependencies are kept, marked "dev", because some ship (Electron is one); --prod-only
drops them and indirect Go requirements.

With --check-latest, asks the public registry for each component's latest version, one GET at a time
(npm, PyPI, crates.io, the Go module proxy, Maven Central or Google's Maven repository, and GitHub
releases for Swift packages hosted there), and says how far the resolved version is behind: major,
minor, patch or current. --dates adds when the resolved and the latest versions were published, and
the days between them: a gap of two weeks and a gap of two years are different stories.
--max-lookups caps how many components are looked up. An optional GITHUB_TOKEN in the environment is
sent to api.github.com only and never printed.

Why it matters: a competitor's weakness may come from an old component that upstream fixed long
ago, and the reverse: a comparison against the latest upstream release can be wrong for the version
they actually ship. Read the upstream changelog between the two versions before you write either.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from common import USER_AGENT, iter_files, iter_vendored, now_utc, parse_iso, print_json, read_text, rel, tree_at

MANIFESTS = {"package.json", "pyproject.toml", "Cargo.toml", "go.mod", "Package.resolved", "Podfile.lock",
             "Package.swift", "build.gradle", "build.gradle.kts", "project.pbxproj", "project.yml", "project.yaml"}
LOCKS = {"package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "uv.lock", "Cargo.lock"}
REQUIREMENTS = re.compile(r"^requirements[\w.-]*\.txt$", re.I)
CATALOG = re.compile(r"\.versions\.toml$")
PEP508 = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*(.*)$")
GOOGLE_MAVEN = ("androidx.", "com.google.android", "com.android.", "com.google.firebase", "com.google.gms")


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
        name = (pin.get("identity") or pin.get("package") or "").lower()
        state = pin.get("state") or {}
        version = state.get("version") or (state.get("revision") or "")[:12]
        rows.append({"ecosystem": "swift", "name": name, "declared": "pinned", "resolved": version, "kind": "prod",
                     "source": pin.get("location") or pin.get("repositoryURL")})
    return rows


def swift_identity(url: str) -> str:
    return re.sub(r"\.git$", "", url.rstrip("/").rsplit("/", 1)[-1]).lower()


def balanced_calls(text: str, opener: str) -> list:
    """The argument text of every call that starts with `opener(` (nested parentheses included)."""
    found, start = [], 0
    while True:
        index = text.find(opener + "(", start)
        if index < 0:
            return found
        depth, i = 0, index + len(opener)
        for i in range(index + len(opener), len(text)):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    break
        found.append(text[index + len(opener) + 1:i])
        start = i + 1


def swift_requirement(args: str) -> str:
    for pattern, label in ((r"exact:\s*\"([^\"]+)\"", "exact {}"), (r"\.upToNextMinor\(\s*from:\s*\"([^\"]+)\"", "upToNextMinor {}"),
                           (r"(?:from:|\.upToNextMajor\(\s*from:)\s*\"([^\"]+)\"", "from {}"), (r"branch:\s*\"([^\"]+)\"", "branch {}"),
                           (r"revision:\s*\"([^\"]+)\"", "revision {}")):
        match = re.search(pattern, args)
        if match:
            return label.format(match.group(1)[:40])
    span = re.search(r"\"([^\"]+)\"\s*(\.\.<|\.\.\.)\s*\"([^\"]+)\"", args)
    return f"{span.group(1)}{span.group(2)}{span.group(3)}" if span else "unknown"


def from_package_swift(text: str) -> list:
    rows = []
    for args in balanced_calls(text, ".package"):
        url = re.search(r"url:\s*\"([^\"]+)\"", args)
        if not url:
            continue
        rows.append({"ecosystem": "swift", "name": swift_identity(url.group(1)), "declared": swift_requirement(args),
                     "kind": "prod", "source": url.group(1)})
    return rows


def from_pbxproj(text: str) -> list:
    rows = []
    for match in re.finditer(r"repositoryURL\s*=\s*\"([^\"]+)\";\s*requirement\s*=\s*\{([^}]*)\}", text, re.S):
        fields = dict(re.findall(r"(\w+)\s*=\s*\"?([^\";]+)\"?;", match.group(2)))
        kind = fields.get("kind", "")
        if fields.get("version"):
            declared = f"exact {fields['version']}"
        elif fields.get("minimumVersion"):
            declared = ("upToNextMinor " if "Minor" in kind else "from ") + fields["minimumVersion"]
        elif fields.get("branch"):
            declared = f"branch {fields['branch']}"
        elif fields.get("revision"):
            declared = f"revision {fields['revision'][:12]}"
        else:
            declared = kind or "unknown"
        rows.append({"ecosystem": "swift", "name": swift_identity(match.group(1)), "declared": declared, "kind": "prod",
                     "source": match.group(1)})
    return rows


def from_xcodegen(text: str) -> list:
    """Remote Swift packages from the `packages:` block of an XcodeGen project.yml."""
    rows, inside, name, fields = [], False, None, {}

    def flush() -> None:
        if name and fields.get("url"):
            if fields.get("exactVersion") or fields.get("version"):
                declared = f"exact {fields.get('exactVersion') or fields.get('version')}"
            elif fields.get("from") or fields.get("majorVersion"):
                declared = f"from {fields.get('from') or fields.get('majorVersion')}"
            elif fields.get("minorVersion"):
                declared = f"upToNextMinor {fields['minorVersion']}"
            elif fields.get("minVersion"):
                declared = f"{fields['minVersion']}..<{fields.get('maxVersion', '')}"
            elif fields.get("branch") or fields.get("revision"):
                declared = f"branch {fields['branch']}" if fields.get("branch") else f"revision {fields['revision'][:12]}"
            else:
                declared = "unknown"
            rows.append({"ecosystem": "swift", "name": swift_identity(fields["url"]), "declared": declared,
                         "kind": "prod", "source": fields["url"]})

    for line in text.splitlines():
        if re.match(r"^\S", line):
            if inside:
                flush()
            inside, name, fields = line.startswith("packages:"), None, {}
            continue
        if not inside or not line.strip() or line.lstrip().startswith("#"):
            continue
        entry = re.match(r"^  ([\w.-]+):\s*$", line)
        field = re.match(r"^    (\w+):\s*['\"]?([^'\"#]+?)['\"]?\s*(#.*)?$", line)
        if entry:
            flush()
            name, fields = entry.group(1), {}
        elif field and name:
            fields[field.group(1)] = field.group(2).strip()
    if inside:
        flush()
    return rows


PURL_ECOSYSTEM = {"npm": "npm", "pypi": "pypi", "cargo": "crates", "golang": "go", "maven": "maven", "swift": "swift",
                  "cocoapods": "cocoapods", "github": "github", "generic": "vendored"}


def from_sbom(text: str) -> list:
    """The component a CycloneDX or SPDX JSON SBOM describes: what a vendored folder pins."""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    described = []
    if data.get("bomFormat") == "CycloneDX":
        component = (data.get("metadata") or {}).get("component") or {}
        if component.get("name"):
            ref = component.get("bom-ref") or ""
            described.append((component["name"], component.get("version"), component.get("purl") or (ref if ref.startswith("pkg:") else None)))
    elif data.get("spdxVersion"):
        targets = set(data.get("documentDescribes") or [])
        for package in data.get("packages") or []:
            if package.get("SPDXID") in targets and package.get("name"):
                purl = next((r.get("referenceLocator") for r in package.get("externalRefs") or [] if r.get("referenceType") == "purl"), None)
                described.append((package["name"], package.get("versionInfo"), purl))
    rows = []
    for name, version, purl in described:
        kind = re.match(r"^pkg:([\w.-]+)/", purl or "")
        rows.append({"ecosystem": PURL_ECOSYSTEM.get(kind.group(1), "vendored") if kind else "vendored", "name": name,
                     "declared": version or "unknown", "resolved": version, "kind": "vendored"})
    return rows


def from_podfile_lock(text: str) -> list:
    rows = []
    for match in re.finditer(r"^  - ([^\s(]+) \(([^)]+)\)", text, re.M):
        rows.append({"ecosystem": "cocoapods", "name": match.group(1), "declared": match.group(2), "resolved": match.group(2), "kind": "prod"})
    return rows


def gradle_kind(configuration: str) -> str:
    lower = configuration.lower()
    if "test" in lower:
        return "dev"
    if lower.startswith(("kapt", "ksp", "annotationprocessor", "lintchecks", "detektplugins", "classpath")):
        return "build"
    return "prod"


def is_exact(version: str) -> bool:
    return bool(re.fullmatch(r"[\w.\-]+", version)) and not version.endswith("+") and "latest" not in version.lower()


def gradle_catalog(text: str) -> dict:
    """{accessor: (group:artifact, version)} from a Gradle version catalog."""
    versions, libraries = {}, {}
    for table, lines in toml_tables(text):
        for line in lines:
            entry = re.match(r"^\s*([\w.\-]+)\s*=\s*(.+)$", line)
            if not entry:
                continue
            key, value = entry.group(1), entry.group(2).strip()
            if table == "versions":
                plain = re.match(r"^\"([^\"]+)\"", value) or re.search(r"(?:strictly|require|prefer)\s*=\s*\"([^\"]+)\"", value)
                if plain:
                    versions[key] = plain.group(1)
            elif table == "libraries":
                accessor = re.sub(r"[-_]", ".", key)
                if value.startswith("\""):
                    parts = value.strip("\"").split(":")
                    if len(parts) >= 2:
                        libraries[accessor] = (f"{parts[0]}:{parts[1]}", parts[2] if len(parts) > 2 else None)
                    continue
                module = re.search(r"module\s*=\s*\"([^\"]+)\"", value)
                group = re.search(r"group\s*=\s*\"([^\"]+)\"", value)
                name = re.search(r"\bname\s*=\s*\"([^\"]+)\"", value)
                coordinate = module.group(1) if module else (f"{group.group(1)}:{name.group(1)}" if group and name else None)
                ref = re.search(r"version\.ref\s*=\s*\"([^\"]+)\"", value)
                literal = re.search(r"\bversion\s*=\s*\"([^\"]+)\"", value)
                if coordinate:
                    libraries[accessor] = (coordinate, versions.get(ref.group(1)) if ref else (literal.group(1) if literal else None))
    return libraries


def from_gradle(text: str, catalog: dict) -> list:
    rows = []
    direct = re.compile(r"""^\s*([A-Za-z]+)\s*\(?\s*(?:(?:platform|enforcedPlatform)\s*\(\s*)?["']([\w.\-]+):([\w.\-]+):([^"'@:\s]+)(?::[\w\-]+)?["']""")
    alias = re.compile(r"""^\s*([A-Za-z]+)\s*\(?\s*(?:(?:platform|enforcedPlatform)\s*\(\s*)?libs\.([\w.]+?)(?:\.get\(\))?\s*\)""")
    for line in text.splitlines():
        match = direct.match(line)
        if match and match.group(1) not in ("id", "version", "group"):
            rows.append({"ecosystem": "maven", "name": f"{match.group(2)}:{match.group(3)}", "declared": match.group(4),
                         "kind": gradle_kind(match.group(1))})
            continue
        match = alias.match(line)
        if match and match.group(2) in catalog:
            coordinate, version = catalog[match.group(2)]
            rows.append({"ecosystem": "maven", "name": coordinate, "declared": version or "managed (BOM or platform)",
                         "kind": gradle_kind(match.group(1)), "catalog_alias": match.group(2)})
    for row in rows:
        if is_exact(row["declared"]):
            row["resolved"] = row["declared"]
    return rows


# ---------- resolved versions ----------

class NpmLock:
    """Resolved versions from an npm, pnpm or yarn lockfile, per workspace package when the lockfile records it."""

    def __init__(self, name: str, text: str):
        self.importers = defaultdict(dict)  # workspace path relative to the lockfile ("" for the root) -> {package: version}
        self.specs = {}                      # (package, range) -> version, from yarn.lock
        if name in ("package-lock.json", "npm-shrinkwrap.json"):
            self._package_lock(text)
        elif name == "pnpm-lock.yaml":
            self._pnpm(text)
        elif name == "yarn.lock":
            self._yarn(text)

    def _package_lock(self, text: str) -> None:
        try:
            data = json.loads(text)
        except ValueError:
            return
        for path, info in (data.get("packages") or {}).items():
            if not isinstance(info, dict) or not info.get("version") or "node_modules/" not in path:
                continue
            prefix, _, package = path.rpartition("node_modules/")
            prefix = prefix.rstrip("/")
            if "node_modules" not in prefix:  # nested copies belong to other packages, not to a workspace
                self.importers[prefix].setdefault(package, info["version"])
        for package, info in (data.get("dependencies") or {}).items():
            if isinstance(info, dict) and info.get("version"):
                self.importers[""].setdefault(package, info["version"])

    def _pnpm(self, text: str) -> None:
        section, importer, package = None, "", None
        for line in text.splitlines():
            if re.match(r"^\S", line):
                section, importer, package = line.rstrip(":").strip(), "", None
                continue
            if section == "importers":
                head = re.match(r"^  (\S.*?):\s*$", line)
                if head:
                    importer = head.group(1).strip("'\"")
                    importer = "" if importer == "." else importer
                    continue
                inline = re.match(r"^      ('?[^\s:']+'?|\"[^\"]+\"):\s*'?([^'\s(]+)", line)
                name_only = re.match(r"^      ('?[^\s:']+'?|\"[^\"]+\"):\s*$", line)
                version = re.match(r"^        version:\s*'?([^'\s(]+)", line)
                if name_only:
                    package = name_only.group(1).strip("'\"")
                elif version and package:
                    self._add(importer, package, version.group(1))
                elif inline:
                    self._add(importer, inline.group(1).strip("'\""), inline.group(2))
            elif section in ("dependencies", "devDependencies", "optionalDependencies"):
                old = re.match(r"^  ('?[^\s:']+'?):\s*'?([^'\s(]+)", line)
                if old:
                    self._add("", old.group(1).strip("'"), old.group(2))

    def _add(self, importer: str, package: str, version: str) -> None:
        if not version.startswith(("link:", "file:", "workspace:")):
            self.importers[importer].setdefault(package, version)

    def _yarn(self, text: str) -> None:
        specs = []
        for line in text.splitlines():
            if line and not line.startswith((" ", "#")) and line.rstrip().endswith(":"):
                specs = [s.strip().strip('"') for s in line.rstrip()[:-1].split(",")]
                continue
            version = re.match(r'^\s+version:?\s+"?([^"\s]+)"?', line)
            if version and specs:
                for spec in specs:
                    at = spec.rfind("@")
                    if at > 0:
                        package, wanted = spec[:at], spec[at + 1:]
                        self.specs[(package, re.sub(r"^npm:", "", wanted))] = version.group(1)
                specs = []

    def resolve(self, package: str, declared: str, importer: str) -> Optional[str]:
        found = self.importers.get(importer, {}).get(package) or self.specs.get((package, declared)) or self.importers.get("", {}).get(package)
        if found:
            return found
        versions = {v for (p, _), v in self.specs.items() if p == package}
        return versions.pop() if len(versions) == 1 else None


def npm_lock_versions(name: str, text: str) -> dict:
    """{package: version} for the root of an npm, pnpm or yarn lockfile (kept for callers that need one map)."""
    lock = NpmLock(name, text)
    merged = dict(lock.importers.get("", {}))
    for (package, _), version in lock.specs.items():
        merged.setdefault(package, version)
    return merged


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


def github_repo(url: Optional[str]) -> Optional[str]:
    match = re.match(r"^(?:https?://|git@)github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", url or "")
    return f"{match.group(1)}/{match.group(2)}" if match else None


def latest_url(ecosystem: str, name: str, source: Optional[str] = None) -> Optional[str]:
    if ecosystem == "npm":
        return "https://registry.npmjs.org/-/package/" + urllib.parse.quote(name, safe="@") + "/dist-tags"
    if ecosystem == "pypi":
        return f"https://pypi.org/pypi/{urllib.parse.quote(name)}/json"
    if ecosystem == "crates":
        return f"https://crates.io/api/v1/crates/{urllib.parse.quote(name)}"
    if ecosystem == "go":
        return f"https://proxy.golang.org/{go_escape(name)}/@latest"
    if ecosystem == "maven" and ":" in name:
        group, artifact = name.split(":", 1)
        query = urllib.parse.quote(f'g:"{group}" AND a:"{artifact}"')
        return f"https://search.maven.org/solrsearch/select?q={query}&rows=1&wt=json"
    if ecosystem == "swift" and github_repo(source):
        return f"https://api.github.com/repos/{github_repo(source)}/releases/latest"
    return None


def latest_from(ecosystem: str, body: dict) -> Optional[str]:
    if ecosystem == "npm":
        return body.get("latest") or (body.get("dist-tags") or {}).get("latest")
    if ecosystem == "pypi":
        return (body.get("info") or {}).get("version")
    if ecosystem == "crates":
        crate = body.get("crate") or {}
        return crate.get("max_stable_version") or crate.get("newest_version")
    if ecosystem == "go":
        return body.get("Version")
    if ecosystem == "maven":
        docs = (body.get("response") or {}).get("docs") or []
        return docs[0].get("latestVersion") if docs else None
    if ecosystem == "swift":
        return (body.get("tag_name") or "").lstrip("v") or None
    return None


def publish_dates(ecosystem: str, body: dict) -> dict:
    """{version: ISO date} that a registry response already holds, where it holds any."""
    if ecosystem == "npm":
        return {k: v for k, v in (body.get("time") or {}).items() if k not in ("created", "modified")}
    if ecosystem == "pypi":
        return {v: files[0].get("upload_time_iso_8601") or files[0].get("upload_time")
                for v, files in (body.get("releases") or {}).items() if files}
    if ecosystem == "crates":
        return {v.get("num"): v.get("created_at") for v in body.get("versions") or [] if v.get("num")}
    if ecosystem == "go" and body.get("Version"):
        return {body["Version"]: body.get("Time")}
    if ecosystem == "maven":
        docs = (body.get("response") or {}).get("docs") or []
        if docs and docs[0].get("timestamp"):
            stamp = datetime.fromtimestamp(docs[0]["timestamp"] / 1000, timezone.utc).replace(microsecond=0).isoformat()
            return {docs[0].get("latestVersion"): stamp}
    if ecosystem == "swift" and body.get("tag_name"):
        return {body["tag_name"].lstrip("v"): body.get("published_at")}
    return {}


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


class Registry:
    """One GET at a time, with a pause between them; counts the requests it makes."""

    def __init__(self):
        self.requests = 0
        self.token = os.environ.get("GITHUB_TOKEN") or None

    def get(self, url: str, as_text: bool = False):
        if self.requests:
            time.sleep(0.3)
        self.requests += 1
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if self.token and url.startswith("https://api.github.com/"):
            headers["Authorization"] = f"Bearer {self.token}"
        if url.startswith("https://registry.npmjs.org/") and "/-/package/" not in url:
            headers["Accept"] = "application/json"  # the full document, which carries publish times
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
                raw = response.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, ValueError):
            return None
        if as_text:
            return raw
        try:
            return json.loads(raw)
        except ValueError:
            return None


def look_up(registry: Registry, ecosystem: str, name: str, source: Optional[str], resolved: list, dates: bool) -> dict:
    """The latest version and, with dates, when it and the resolved versions were published."""
    if ecosystem == "npm" and dates:
        body = registry.get("https://registry.npmjs.org/" + urllib.parse.quote(name, safe="@"))
    elif ecosystem == "maven" and name.startswith(GOOGLE_MAVEN):
        group, artifact = name.split(":", 1)
        xml = registry.get(f"https://dl.google.com/android/maven2/{group.replace('.', '/')}/{artifact}/maven-metadata.xml", as_text=True)
        release = re.search(r"<release>([^<]+)</release>", xml or "") or re.search(r"<latest>([^<]+)</latest>", xml or "")
        return {"latest": release.group(1) if release else None}
    else:
        url = latest_url(ecosystem, name, source)
        body = registry.get(url) if url else None
    if not body:
        return {"latest": None}
    out = {"latest": latest_from(ecosystem, body)}
    if not dates:
        return out
    known = publish_dates(ecosystem, body)
    wanted = [v for v in resolved if v and v not in known][:1]
    for version in wanted:
        extra = None
        if ecosystem == "go":
            extra = registry.get(f"https://proxy.golang.org/{go_escape(name)}/@v/{version}.info")
            if extra:
                known[version] = extra.get("Time")
        elif ecosystem == "maven" and ":" in name:
            group, artifact = name.split(":", 1)
            query = urllib.parse.quote(f'g:"{group}" AND a:"{artifact}" AND v:"{version}"')
            extra = registry.get(f"https://search.maven.org/solrsearch/select?q={query}&core=gav&rows=1&wt=json")
            docs = ((extra or {}).get("response") or {}).get("docs") or []
            if docs and docs[0].get("timestamp"):
                known[version] = datetime.fromtimestamp(docs[0]["timestamp"] / 1000, timezone.utc).replace(microsecond=0).isoformat()
        elif ecosystem == "swift" and github_repo(source):
            for tag in (version, f"v{version}"):
                extra = registry.get(f"https://api.github.com/repos/{github_repo(source)}/releases/tags/{tag}")
                if extra and extra.get("published_at"):
                    known[version] = extra["published_at"]
                    break
    out["latest_published"] = known.get(out["latest"]) if out["latest"] else None
    out["resolved_published"] = {v: known.get(v) for v in resolved if v}
    first = next((known.get(v) for v in resolved if known.get(v)), None)
    if first and out["latest_published"]:
        out["days_between"] = (parse_iso(out["latest_published"]) - parse_iso(first)).days
        # Stable releases published after the shipped one, up to the latest: how many steps behind.
        stable = [v for v, when in known.items() if when and not re.search(r"[-+][A-Za-z]", v or "")]
        out["stable_releases_since"] = sum(1 for v in stable if parse_iso(first) < parse_iso(known[v]) <= parse_iso(out["latest_published"]))
    return out


# ---------- scan ----------

def scan(root: Path) -> list:
    rows, npm_locks, py_locks, cargo_locks, catalogs, gradle_files = [], {}, {}, {}, {}, []
    for path in iter_files(root):
        name, folder = path.name, path.parent
        if name not in MANIFESTS and name not in LOCKS and not REQUIREMENTS.match(name) and not CATALOG.search(name):
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
        elif name == "Package.swift":
            found = from_package_swift(text)
        elif name == "project.pbxproj":
            found = from_pbxproj(text)
        elif name in ("project.yml", "project.yaml"):
            found = from_xcodegen(text)
        elif name == "Podfile.lock":
            found = from_podfile_lock(text)
        elif CATALOG.search(name):
            catalogs[where] = gradle_catalog(text)
        elif name in ("build.gradle", "build.gradle.kts"):
            gradle_files.append((where, folder, text))
        elif name in ("package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock"):
            npm_locks[folder] = (where, NpmLock(name, text))
        elif name in ("poetry.lock", "uv.lock"):
            py_locks[folder] = (where, {norm_py(k): v for k, v in toml_packages(text).items()})
        elif name == "Cargo.lock":
            cargo_locks[folder] = (where, toml_packages(text))
        for row in found:
            row["manifest"] = where
            row["_folder"] = folder
        rows.extend(found)

    for path in iter_vendored(root):
        if re.search(r"(\.cdx\.json|\.spdx\.json|^bom\.json|^sbom\.json)$", path.name, re.I):
            for row in from_sbom(read_text(path, limit=50_000_000) or ""):
                row["manifest"], row["_folder"] = rel(path, root), path.parent
                rows.append(row)

    catalog = {}
    for entries in catalogs.values():
        catalog.update(entries)
    for where, folder, text in gradle_files:
        for row in from_gradle(text, catalog):
            row["manifest"], row["_folder"] = where, folder
            rows.append(row)

    def nearest(locks: dict, folder: Path):
        for candidate in [folder, *folder.parents]:
            if candidate in locks:
                return candidate, locks[candidate]
            if candidate == root:
                break
        return None, None

    swift_pins = {r["name"]: r["resolved"] for r in rows if r["ecosystem"] == "swift" and r.get("resolved")}
    for row in rows:
        folder = row.pop("_folder")
        if row.get("resolved"):
            continue
        version, lock = None, None
        if row["ecosystem"] == "npm":
            lock_folder, lock = nearest(npm_locks, folder)
            if lock:
                importer = folder.relative_to(lock_folder).as_posix() if folder != lock_folder else ""
                version = lock[1].resolve(row["name"], row["declared"], importer)
        elif row["ecosystem"] == "pypi":
            _, lock = nearest(py_locks, folder)
            versions = lock[1].get(norm_py(row["name"])) if lock else None
            version = versions[0] if versions else None
        elif row["ecosystem"] == "crates":
            _, lock = nearest(cargo_locks, folder)
            versions = lock[1].get(row["name"]) if lock else None
            version = ", ".join(sorted(set(versions))) if versions else None
        elif row["ecosystem"] == "swift" and row["name"] in swift_pins:
            row["resolved"] = swift_pins[row["name"]]
        elif row["ecosystem"] == "swift" and row["declared"].startswith("exact "):
            row["resolved"] = row["declared"][len("exact "):]
        if version:
            row["resolved"], row["lockfile"] = version, lock[0]
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo", type=Path)
    parser.add_argument("--at", help="read this branch, tag or commit instead of the working tree, without a checkout")
    parser.add_argument("--only", nargs="+", default=[], help="shell patterns of dependency names to keep")
    parser.add_argument("--prod-only", action="store_true", help="drop development dependencies and indirect requirements")
    parser.add_argument("--check-latest", action="store_true", help="look up the latest upstream version (network)")
    parser.add_argument("--dates", action="store_true", help="with --check-latest, add publish dates and the days between")
    parser.add_argument("--max-lookups", type=int, default=40, help="cap on the components looked up, one at a time")
    parser.add_argument("--rows", action="store_true", help="also print one row per manifest")
    args = parser.parse_args()
    root = args.repo.resolve()
    if not root.is_dir():
        parser.error(f"{root} is not a folder")

    with tree_at(root, args.at) as tree:
        scanned = scan(tree)
    rows = [r for r in scanned if not args.prod_only or r["kind"] not in ("dev", "indirect")]
    if args.only:
        rows = [r for r in rows if any(fnmatch.fnmatch(r["name"], p) for p in args.only)]
    rows.sort(key=lambda r: (r["ecosystem"], r["name"].lower(), r["manifest"]))

    components = {}
    for row in rows:
        entry = components.setdefault((row["ecosystem"], row["name"]), {
            "ecosystem": row["ecosystem"], "name": row["name"], "kinds": [], "declared": [], "resolved": [],
            "manifests": 0, "example_manifest": row["manifest"]})
        entry["manifests"] += 1
        for field, value in (("kinds", row["kind"]), ("declared", row["declared"]), ("resolved", row.get("resolved"))):
            if value and value not in entry[field]:
                entry[field].append(value)
        if row.get("source") and "source" not in entry:
            entry["source"] = row["source"]

    registry, looked_up = Registry(), 0
    if args.check_latest:
        for entry in components.values():
            if entry["ecosystem"] == "cocoapods" or (entry["ecosystem"] == "swift" and not github_repo(entry.get("source"))):
                entry["behind"] = "not looked up"
                continue
            if looked_up >= args.max_lookups:
                entry["behind"] = "not looked up (cap reached)"
                continue
            looked_up += 1
            found = look_up(registry, entry["ecosystem"], entry["name"], entry.get("source"), entry["resolved"], args.dates)
            entry.update(found)
            reference = entry["resolved"][0] if entry["resolved"] else (entry["declared"][0] if entry["declared"] else None)
            entry["behind"] = behind(reference, found.get("latest")) if found.get("latest") else "unknown"

    by_ecosystem = defaultdict(int)
    for ecosystem, _ in components:
        by_ecosystem[ecosystem] += 1
    print_json({
        "taken_at": now_utc(),
        "root": str(root),
        "at": args.at or "working tree",
        "components": list(components.values()),
        **({"rows": rows} if args.rows else {}),
        "counts": dict(sorted(by_ecosystem.items())),
        "components_looked_up": looked_up,
        "registry_requests": registry.requests,
        "notes": [
            "declared is the range in the manifest; resolved is the version the lockfile pins, which is what ships.",
            "A component with several resolved versions ships different versions in different workspace packages.",
            "behind compares the first resolved version (or the declared one, without a lockfile) with the latest release.",
            "Read the upstream changelog between the two versions before you call anything a weakness.",
        ],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
