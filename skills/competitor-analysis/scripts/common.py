"""Shared helpers for the competitor-analysis scripts.

Standard library only, Python 3.9 or later. Every script in this folder is read-only: it never
writes to the repository it analyzes, never signs in anywhere and never sends data anywhere
except the read-only requests it documents.
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Optional

# Folders that hold dependencies, build output or other people's code. Counting them would
# inflate size, telemetry and license results with code the project did not write.
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "bower_components", "jspm_packages", "vendor", "vendors",
    "third_party", "third-party", "thirdparty", "external", "Pods", "Carthage", ".build", "DerivedData",
    "target", "dist", "build", "out", "release", "releases", ".next", ".nuxt", ".svelte-kit", ".output",
    "__pycache__", ".venv", "venv", ".tox", ".nox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "site-packages", "coverage", ".coverage", ".gradle", ".idea", ".vscode", ".yarn", ".pnpm-store",
    ".cache", ".turbo", ".parcel-cache", ".angular", ".expo", ".dart_tool", "elm-stuff", "_build", "deps",
}

USER_AGENT = "competitor-analysis-skill (read-only research script)"


def now_utc() -> str:
    """The current time in UTC, ISO 8601, to the second."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(value: str) -> datetime:
    """An ISO 8601 timestamp as git and the GitHub API print it, "Z" included (Python 3.9 rejects "Z")."""
    return datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)


def iter_files(root: Path, skip_dirs: Iterable[str] = SKIP_DIRS, extra_skip: Iterable[str] = ()) -> Iterator[Path]:
    """Every file under root, in a stable order, without the skipped folders."""
    skip = set(skip_dirs) | set(extra_skip)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip)
        for name in sorted(filenames):
            yield Path(dirpath) / name


def is_binary(data: bytes) -> bool:
    return b"\0" in data[:8000]


def read_text(path: Path, limit: Optional[int] = None) -> Optional[str]:
    """The file as text, or None when it is binary or unreadable."""
    try:
        with open(path, "rb") as handle:
            data = handle.read() if limit is None else handle.read(limit)
    except OSError:
        return None
    if is_binary(data):
        return None
    return data.decode("utf-8", errors="replace")


def rel(path: Path, root: Path) -> str:
    """A path relative to root, with forward slashes."""
    return path.relative_to(root).as_posix()


def git(repo: Path, *args: str, check: bool = True) -> str:
    """Run a read-only git command in repo and return its standard output."""
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def is_git_repo(path: Path) -> bool:
    result = subprocess.run(["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    return result.returncode == 0 and result.stdout.strip() == "true"


def mask(value: str) -> str:
    """Show that a sensitive value exists without printing it."""
    return f"{value[:4]}... ({len(value)} chars)"


def print_json(data) -> None:
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False, default=str)
    sys.stdout.write("\n")


def html_to_text(markup: str) -> str:
    """Readable text from an HTML page: title, scripts, styles and SVG removed, blocks on their own lines."""
    text = re.sub(r"(?is)<(title|script|style|svg|noscript|template)\b.*?</\1>", " ", markup)
    text = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6]|/tr|/section|/article|/header|/footer|/td|/th|/dt|/dd)\b[^>]*>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    lines = (line.strip() for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


def html_title(markup: str) -> Optional[str]:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", markup)
    return html.unescape(re.sub(r"\s+", " ", match.group(1))).strip() if match else None
