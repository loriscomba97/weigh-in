#!/usr/bin/env python3
"""Convert the analysis documents from Markdown to Notion-flavored Markdown, with links between
the pages turned into Notion page mentions.

Usage:
  python3 md_to_notion.py --config notion.json --src analysis/ --out notion/
  python3 md_to_notion.py --file analysis/01-company.md --out notion/

The config maps each document to its Notion page and says how documents refer to each other:
  {
    "pages": {"01": "<page id>", "02": "<page id>", "A": "<page id>"},
    "files": {"01": "01-company.md", "02": "02-architecture.md", "A": "appendices/A-code.md"},
    "references": [{"regex": "\\\\bdocument (0[1-9])\\\\b", "group": 1}],
    "literals": [{"text": "the earlier analysis", "page": "<page id>"}],
    "callout_markers": ["Note", "Update"],
    "toc": true,
    "drop_first_h1": true,
    "max_heading_level": 3,
    "mention_url": "https://www.notion.so/{id}"
  }
Create the Notion pages first, empty, so their ids exist; then convert; then upload in order.

What the conversion does, and why:
  - tables become <table> blocks with tab-indented rows, the form Notion's editor accepts;
  - a reference such as "document 03", or a backticked path to another document, becomes a
    mention of that document's page. A reference rule may carry its own "pages" map, for links
    into another analysis; "literals" turn exact phrases into a mention of a given page.
    References are applied in order, so put the most specific rule first;
  - $ ~ < > { } ^ | [ ] are escaped, but an escape already in the text is kept as it is;
  - file paths, with their folders and line numbers, go into inline code: names ending in .md,
    .sh or .py are real domains, and Notion would turn them into links;
  - nested lists use tabs; blockquotes holding a callout marker become gray callouts;
  - the first H1 is dropped (the page title holds it) and a table of contents can be added.
Warnings on standard error point at table cells where "+ " or "* " follows bold or code text:
Notion turns those into bullets, so reword them before you upload.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SPECIAL = set("$~<>{}^|[]")
PUNCT = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
TOKEN = re.compile(r"(@@H\d+@@|`[^`]*`|\[[^\]]+\]\((?:https?://|mailto:)[^)]+\))")
PATH = re.compile(
    r"(?<![\w/`.@-])((?:[\w.-]+/)*[\w.-]+\.(?:md|mdx|rs|swift|json|py|yml|yaml|toml|sh|txt|ts|tsx|mjs|cjs|js|kt|kts|"
    r"plist|xcprivacy|go|rb|java|c|h|cpp|cs|lock)(?::\d+(?:-\d+)?)?)(?![\w/])"
)


def escape(text: str) -> str:
    out, i = [], 0
    while i < len(text):
        char = text[i]
        if char == "\\" and i + 1 < len(text) and text[i + 1] in PUNCT:
            out.append(text[i : i + 2])
            i += 2
            continue
        out.append("\\" + char if char in SPECIAL else char)
        i += 1
    return "".join(out)


class Converter:
    def __init__(self, config: dict):
        self.pages = config.get("pages", {})
        self.files = {Path(v).as_posix(): k for k, v in config.get("files", {}).items()}
        self.references = [(re.compile(r["regex"]), r.get("group", 1), r.get("pages")) for r in config.get("references", [])]
        self.literals = [(l["text"], l["page"]) for l in config.get("literals", [])]
        self.markers = config.get("callout_markers", [])
        self.toc = config.get("toc", True)
        self.drop_h1 = config.get("drop_first_h1", True)
        self.max_heading = config.get("max_heading_level", 3)
        self.mention_url = config.get("mention_url", "https://www.notion.so/{id}")
        self.warnings = []

    def mention(self, key: str, pages: dict = None):
        page = (pages or self.pages).get(key)
        return f'<mention-page url="{self.mention_url.format(id=page.replace("-", ""))}"/>' if page else None

    def inline(self, text: str) -> str:
        holders = {}

        def hold(value: str) -> str:
            key = f"@@H{len(holders)}@@"
            holders[key] = value
            return key

        def code_ref(match):
            target = match.group(1)
            for path, key in self.files.items():
                if target == path or target.endswith("/" + path) or path.endswith("/" + target):
                    mention = self.mention(key)
                    if mention:
                        return hold(mention)
            return match.group(0)

        for literal, page in self.literals:
            if literal in text:
                text = text.replace(literal, hold(self.mention("_", {"_": page})))
        text = re.sub(r"`([^`]+\.md)`", code_ref, text)
        for pattern, group, pages in self.references:
            def ref(match, group=group, pages=pages):
                mention = self.mention(match.group(group), pages)
                if not mention:
                    return match.group(0)
                whole, start, end = match.group(0), match.start(group) - match.start(0), match.end(group) - match.start(0)
                return whole[:start] + hold(mention) + whole[end:]
            text = pattern.sub(ref, text)
        parts = []
        for piece in TOKEN.split(text):
            if not piece:
                continue
            if piece in holders or piece.startswith("`"):
                parts.append(piece)
            elif piece.startswith("[") and "](" in piece:
                label, url = re.match(r"\[([^\]]+)\]\((.+)\)$", piece).groups()
                parts.append(f"[{escape(label)}]({url})")
            else:
                segments = PATH.sub(lambda m: "\x00" + m.group(1) + "\x00", piece).split("\x00")
                parts.append("".join(f"`{s}`" if i % 2 else escape(s) for i, s in enumerate(segments)))
        result = "".join(parts)
        for key, value in holders.items():
            result = result.replace(key, value)
        return result

    @staticmethod
    def cells(row: str) -> list:
        row = row.strip()
        row = row[1:] if row.startswith("|") else row
        row = row[:-1] if row.endswith("|") else row
        out, current, tick = [], "", False
        for char in row:
            if char == "`":
                tick = not tick
            if char == "|" and not tick:
                out.append(current)
                current = ""
            else:
                current += char
        out.append(current)
        return [c.strip() for c in out]

    def table(self, rows: list, where: str) -> list:
        out = ['<table header-row="true">']
        for row in [rows[0]] + rows[2:]:
            out.append("\t<tr>")
            for cell in self.cells(row):
                if re.search(r"(\*\*|`)\s*[+*] ", cell) or re.match(r"[+*] ", cell):
                    self.warnings.append(f"{where}: a cell has '+ ' or '* ' after bold or code text: {cell[:60]}")
                out.append(f"\t\t<td>{self.inline(cell)}</td>")
            out.append("\t</tr>")
        out.append("</table>")
        return out

    def convert(self, text: str, where: str = "") -> str:
        lines = text.split("\n")
        out = ["<table_of_contents/>", ""] if self.toc else []
        i, dropped_h1, in_code, stack = 0, not self.drop_h1, False, []
        while i < len(lines):
            line = lines[i]
            if line.strip().startswith("```"):
                fence = line.strip()
                out.append(fence if in_code or fence != "```" else "```text")
                in_code = not in_code
                i += 1
                continue
            if in_code:
                out.append(line)
                i += 1
                continue
            if not dropped_h1 and line.startswith("# "):
                dropped_h1 = True
                i += 1
                continue
            if line.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
                rows = []
                while i < len(lines) and lines[i].lstrip().startswith("|"):
                    rows.append(lines[i])
                    i += 1
                out += self.table(rows, f"{where}:{i}")
                continue
            if line.startswith(">"):
                group = []
                while i < len(lines) and lines[i].startswith(">"):
                    group.append(lines[i][1:].strip())
                    i += 1
                texts = [g for g in group if g]
                if any(any(m.lower() in g.lower() for m in self.markers) for g in texts):
                    out.append('<callout icon="📌" color="gray_bg">')
                    out += ["\t" + self.inline(g) for g in texts]
                    out.append("</callout>")
                else:
                    out.append("> " + "<br>".join(self.inline(g) for g in texts))
                continue
            heading = re.match(r"^(#{1,6}) (.*)$", line)
            if heading:
                level = min(len(heading.group(1)), self.max_heading)
                out.append("#" * level + " " + self.inline(heading.group(2)))
                stack = []
                i += 1
                continue
            if line.strip() == "---":
                out.append("---")
                i += 1
                continue
            item = re.match(r"^( *)([-*+]|\d+[.)]) (.*)$", line)
            if item:
                indent = len(item.group(1))
                while stack and stack[-1] > indent:
                    stack.pop()
                if not stack or stack[-1] < indent:
                    stack.append(indent)
                depth = len(stack) - 1
                out.append("\t" * depth + item.group(2) + " " + self.inline(item.group(3)))
                i += 1
                continue
            continuation = re.match(r"^( +)(\S.*)$", line)
            if continuation and stack:
                indent = len(continuation.group(1))
                depth = max(0, len([s for s in stack if s < indent]))
                out.append("\t" * depth + self.inline(continuation.group(2)))
                i += 1
                continue
            if not line.strip():
                if i + 1 < len(lines) and not re.match(r"^\s+", lines[i + 1]) and not re.match(r"^([-*+]|\d+[.)]) ", lines[i + 1]):
                    stack = []
            out.append(self.inline(line))
            i += 1
        result = "\n".join(out)
        return re.sub(r"\n{3,}", "\n\n", result).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, help="JSON config with pages, files and reference patterns")
    parser.add_argument("--src", type=Path, help="folder the config's file paths are relative to")
    parser.add_argument("--file", type=Path, help="convert one file without mentions")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    report = []
    if args.file:
        converter = Converter({})
        target = args.out / (args.file.stem + ".nmd")
        target.write_text(converter.convert(args.file.read_text(encoding="utf-8"), str(args.file)), encoding="utf-8")
        report.append({"source": str(args.file), "output": str(target), "chars": target.stat().st_size})
    else:
        if not args.config or not args.src:
            parser.error("pass --config and --src, or --file")
        config = json.loads(args.config.read_text(encoding="utf-8"))
        converter = Converter(config)
        for key, relative in config.get("files", {}).items():
            source = args.src / relative
            target = args.out / f"{key}.nmd"
            target.write_text(converter.convert(source.read_text(encoding="utf-8"), relative), encoding="utf-8")
            report.append({"key": key, "source": str(source), "output": str(target), "chars": len(target.read_text(encoding="utf-8"))})
    for warning in converter.warnings:
        print("warning: " + warning, file=sys.stderr)
    json.dump({"converted": report, "warnings": len(converter.warnings)}, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
