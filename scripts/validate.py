#!/usr/bin/env python3
"""Check every skill in skills/ against the Agent Skills specification (agentskills.io) and our own
limits, so a skill that would not load, or would load badly, never ships:
  - SKILL.md starts with YAML frontmatter holding only the fields the specification defines;
  - name: 1 to 64 lowercase letters, digits and single hyphens, equal to the folder name;
  - description: 1 to 1024 characters; compatibility: at most 500;
  - SKILL.md: at most 500 lines;
  - every relative link resolves inside the skill, at most one folder deep from SKILL.md, and
    links in references/ stay inside references/;
  - every script in scripts/ compiles, has a docstring with a "Usage:" section, and is named
    in SKILL.md or a reference, and every scripts/<name> that the text names exists;
  - every JSON file in scripts/ parses;
  - Markdown in the repository uses no long dashes (house style).

Usage: python3 scripts/validate.py [--root DIR]   (default: this repository)
Standard library only, Python 3.9 or later.
"""
from __future__ import annotations

import ast
import json
import os
import py_compile
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[sys.argv.index("--root") + 1]).resolve() if "--root" in sys.argv else Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
ALLOWED = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
LONG_DASH = re.compile("[\u2013\u2014]")
problems = []


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def frontmatter(text: str, where: str):
    """The small YAML subset our SKILL.md files use: "key: value" lines and one nested "metadata:" map."""
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        problems.append(f"{where}: no frontmatter")
        return None
    data, nested = {}, None
    for line in match.group(1).split("\n"):
        if not line.strip():
            continue
        top = re.match(r"^([a-z][a-z-]*):\s*(.*)$", line)
        if top:
            key, value = top.groups()
            if value == "":
                data[key] = nested = {}
            else:
                data[key], nested = unquote(value), None
            continue
        inner = re.match(r"^\s+([A-Za-z0-9_.-]+):\s*(.*)$", line)
        if inner and nested is not None:
            nested[inner.group(1)] = unquote(inner.group(2))
        else:
            problems.append(f'{where}: cannot read frontmatter line "{line}"')
    return data


def prose(text: str) -> str:
    """Text outside fenced code blocks and inline code."""
    return re.sub(r"`[^`\n]*`", "", re.sub(r"```.*?```", "", text, flags=re.S))


def relative_links(text: str) -> list:
    hrefs = re.findall(r"\]\(([^)\s]+)\)", prose(text))
    return [h for h in hrefs if not re.match(r"^(https?:|mailto:|#)", h, re.I)]


def check_links(base: Path, skill_file: Path, where: str) -> None:
    for href in relative_links(skill_file.read_text(encoding="utf-8")):
        path = os.path.normpath(href.split("#")[0])
        if path.startswith("..") or len(path.split("/")) > 2:
            problems.append(f'{where}: link "{href}" leaves the skill or is more than one folder deep')
        elif not (base / path).exists():
            problems.append(f'{where}: link "{href}" does not resolve')
    refs = base / "references"
    if refs.is_dir():
        for file in sorted(refs.glob("*.md")):
            for href in relative_links(file.read_text(encoding="utf-8")):
                path = os.path.normpath(href.split("#")[0])
                if "/" in path or not (refs / path).exists():
                    problems.append(f'{file.relative_to(ROOT)}: link "{href}" does not resolve inside references/')


def check_scripts(base: Path, name: str) -> None:
    scripts = base / "scripts"
    if not scripts.is_dir():
        return
    texts = [(base / "SKILL.md").read_text(encoding="utf-8")]
    texts += [f.read_text(encoding="utf-8") for f in sorted((base / "references").glob("*.md"))] if (base / "references").is_dir() else []
    corpus = "\n".join(texts)
    with tempfile.TemporaryDirectory() as tmp:
        for script in sorted(scripts.glob("*.py")):
            where = f"skills/{name}/scripts/{script.name}"
            try:
                py_compile.compile(str(script), cfile=str(Path(tmp) / (script.name + "c")), doraise=True)
            except py_compile.PyCompileError as error:
                problems.append(f"{where}: does not compile: {error.msg.strip()}")
                continue
            doc = ast.get_docstring(ast.parse(script.read_text(encoding="utf-8"))) or ""
            if script.name != "common.py" and "Usage:" not in doc:
                problems.append(f'{where}: the docstring has no "Usage:" section')
            if script.name != "common.py" and f"scripts/{script.name}" not in corpus:
                problems.append(f"{where}: not named in SKILL.md or any reference")
    for data in sorted(scripts.glob("*.json")):
        try:
            json.loads(data.read_text(encoding="utf-8"))
        except ValueError as error:
            problems.append(f"skills/{name}/scripts/{data.name}: invalid JSON: {error}")
    for mentioned in sorted(set(re.findall(r"scripts/([\w.-]+\.(?:py|json|sh))", corpus))):
        if not (scripts / mentioned).exists():
            problems.append(f"skills/{name}: the text names scripts/{mentioned}, which does not exist")


def check_style() -> None:
    skip = {".git", "node_modules", "__pycache__"}
    for path in sorted(ROOT.rglob("*.md")):
        if skip & set(path.relative_to(ROOT).parts):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            if LONG_DASH.search(line):
                problems.append(f"{path.relative_to(ROOT)}:{number}: long dash (house style: use a comma, a colon or two sentences)")


skills = sorted(d for d in SKILLS.iterdir() if d.is_dir()) if SKILLS.is_dir() else []
if not skills:
    problems.append("skills/: no skills found")

for base in skills:
    where = f"skills/{base.name}/SKILL.md"
    skill_file = base / "SKILL.md"
    if not skill_file.exists():
        problems.append(f"{where}: missing")
        continue
    text = skill_file.read_text(encoding="utf-8")
    data = frontmatter(text, where)
    if data is not None:
        for key in data:
            if key not in ALLOWED:
                problems.append(f'{where}: unknown frontmatter field "{key}"')
        name = data.get("name", "")
        if not isinstance(name, str) or not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", name) or len(name) > 64:
            problems.append(f'{where}: invalid name "{name}"')
        elif name != base.name:
            problems.append(f'{where}: name "{name}" does not match the folder "{base.name}"')
        description = data.get("description", "")
        if not isinstance(description, str) or not 1 <= len(description) <= 1024:
            problems.append(f"{where}: description must be 1 to 1024 characters (it is {len(description) if isinstance(description, str) else 0})")
        if isinstance(data.get("compatibility"), str) and len(data["compatibility"]) > 500:
            problems.append(f"{where}: compatibility is over 500 characters")
        if "metadata" in data and (not isinstance(data["metadata"], dict) or not all(isinstance(v, str) for v in data["metadata"].values())):
            problems.append(f"{where}: metadata must map strings to strings")
    lines = len(text.split("\n"))
    if lines > 500:
        problems.append(f"{where}: {lines} lines (limit 500)")
    check_links(base, skill_file, where)
    check_scripts(base, base.name)

check_style()

if problems:
    print(f"validate: {len(problems)} problem(s).", file=sys.stderr)
    for problem in problems:
        print(f"  {problem}", file=sys.stderr)
    sys.exit(1)
print(f"validate: {len(skills)} skill(s) follow the Agent Skills format; scripts compile and are documented.")
