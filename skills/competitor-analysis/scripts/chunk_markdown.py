#!/usr/bin/env python3
"""Split converted documents into chunks small enough for one upload call each.

Usage:
  python3 chunk_markdown.py notion/01.nmd notion/02.nmd --out notion/chunks [--limit 18000]

Cuts only at a line starting with "## " or "### " that is outside a table, a callout and a code
block, so no block is ever split. Among the valid cuts it takes the fewest chunks, then the most
even sizes. Writes <name>.<n>.nmd files and prints JSON with each chunk's size and first line.
Upload chunk 1 by replacing the page content, then append the others in order, then read the
page back and check the joins. Lower --limit if the destination rejects a chunk.
"""
from __future__ import annotations

import argparse
import functools
import json
import re
import sys
from pathlib import Path


def cut_points(text: str) -> list:
    offsets, position = [], 0
    in_table = in_callout = in_code = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if in_code:
            if stripped.startswith("```"):
                in_code = False
        elif stripped.startswith("```"):
            in_code = True
        else:
            if not (in_table or in_callout) and (line.startswith("## ") or line.startswith("### ")) and position > 0:
                offsets.append(position)
            if re.match(r"<table[\s>]", stripped):
                in_table = True
            if stripped.startswith("</table>"):
                in_table = False
            if stripped.startswith("<callout"):
                in_callout = True
            if stripped.startswith("</callout>"):
                in_callout = False
        position += len(line)
    if in_table or in_callout or in_code:
        raise ValueError("unbalanced table, callout or code block")
    return offsets


def best_split(total: int, cuts: list, limit: int) -> list:
    points = [0] + sorted(c for c in cuts if 0 < c < total) + [total]

    @functools.lru_cache(maxsize=None)
    def solve(i: int):
        if points[i] == total:
            return (0, 0, ())
        best = None
        for j in range(i + 1, len(points)):
            size = points[j] - points[i]
            if size > limit:
                break
            count, largest, path = solve(j)
            if count is None:
                continue
            candidate = (count + 1, max(largest, size), (points[j],) + path)
            if best is None or candidate[:2] < best[:2]:
                best = candidate
        return best or (None, None, None)

    count, _, path = solve(0)
    if count is None:
        raise ValueError(f"a section is longer than {limit} characters with no heading to cut at")
    return [0] + list(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=18000)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    report = []
    for path in args.files:
        text = path.read_text(encoding="utf-8")
        points = best_split(len(text), cut_points(text), args.limit)
        chunks = list(zip(points, points[1:]))
        assert "".join(text[a:b] for a, b in chunks) == text
        for n, (a, b) in enumerate(chunks, 1):
            target = args.out / f"{path.stem}.{n}.nmd"
            target.write_text(text[a:b], encoding="utf-8")
            report.append({"source": str(path), "chunk": n, "file": str(target), "chars": b - a,
                           "first_line": text[a:b].split("\n", 1)[0][:80]})
    json.dump({"limit": args.limit, "chunks": report}, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
