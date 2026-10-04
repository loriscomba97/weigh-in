"""Shared helpers for the competitor-analysis scripts.

Standard library only, Python 3.9 or later. Every script in this folder is read-only: it never
writes to the repository it analyzes, never signs in anywhere and never sends data anywhere
except the read-only requests it documents.
"""
from __future__ import annotations

import contextlib
import gzip
import html
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
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

# Test code, by folder or by file name. Shared by the scripts that count tests apart or leave them out.
TEST_DIRS = re.compile(
    r"(^|/)(__tests__|__test__|tests?|testing|spec|specs|e2e|integration[-_]tests?|androidTest|"
    r"test[-_]?fixtures|fixtures|testdata|test_data|mocks?|__mocks__|[A-Za-z0-9]+Tests|[A-Za-z0-9]+UITests)(/|$)"
)
TEST_FILE = re.compile(
    r"([._-](test|tests|spec|e2e|stories)\.[a-z0-9]+$)|(_test\.(go|py|rs|rb|exs|dart)$)|(^test_.*\.py$)|"
    r"(Tests?\.(swift|kt|java|cs)$)|(_spec\.rb$)"
)


def is_test_path(relative: str) -> bool:
    """True when a repository-relative path is test code, by its folders or its file name."""
    return bool(TEST_DIRS.search(relative) or TEST_FILE.search(relative.rsplit("/", 1)[-1]))


def now_utc() -> str:
    """The current time in UTC, ISO 8601, to the second."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# Folders that hold copies of other projects shipped with the product, unlike package-manager installs.
VENDORED_DIRS = {"vendor", "vendors", "third_party", "third-party", "thirdparty", "external"}


def iter_vendored(root: Path) -> Iterator[Path]:
    """Every file inside vendored folders (third_party/, vendor/ and similar), without the
    package-manager and build folders that may sit inside them."""
    skip = SKIP_DIRS - VENDORED_DIRS
    for current, dirs, files in os.walk(root):
        relative_parts = set(Path(current).relative_to(root).parts)
        dirs[:] = sorted(d for d in dirs if d not in skip)
        if relative_parts & VENDORED_DIRS:
            for name in sorted(files):
                yield Path(current) / name


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


def decode_body(data: bytes) -> bytes:
    """The body as the server meant it: archives sometimes return a page still gzip-compressed, as
    it was stored, without saying so. Plain bodies come back unchanged."""
    if data[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(data)
        except (OSError, EOFError):
            return data
    return data


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


def export_tree(repo: Path, rev: str, target: Path) -> None:
    """Write the tree of rev into target with git archive, without touching the clone."""
    archive = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", rev], capture_output=True)
    if archive.returncode != 0:
        raise RuntimeError(archive.stderr.decode(errors="replace").strip())
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        safe = [m for m in tar.getmembers() if not (m.name.startswith("/") or ".." in Path(m.name).parts) and (m.isfile() or m.isdir())]
        if hasattr(tarfile, "data_filter"):
            tar.extractall(target, members=safe, filter="data")
        else:
            tar.extractall(target, members=safe)


@contextlib.contextmanager
def tree_at(repo: Path, rev: Optional[str]):
    """The folder to scan: the working tree as it is, or with rev a temporary copy of that commit's
    tree (a branch, a tag, an older commit), so a scan never needs a checkout. Files marked
    export-ignore in .gitattributes are left out of the copy."""
    if not rev:
        yield repo
        return
    if not is_git_repo(repo):
        raise SystemExit("--at needs a git repository")
    with tempfile.TemporaryDirectory(prefix="ca-tree-") as tmp:
        export_tree(repo, rev, Path(tmp))
        yield Path(tmp)
