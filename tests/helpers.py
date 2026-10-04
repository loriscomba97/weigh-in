"""Shared helpers for the tests: import the skill's scripts, run them, build throwaway git repos."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "competitor-analysis" / "scripts"
sys.path.insert(0, str(SCRIPTS))

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test Author", "GIT_AUTHOR_EMAIL": "author@example.com",
    "GIT_COMMITTER_NAME": "Test Author", "GIT_COMMITTER_EMAIL": "author@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
}


def run_script(name: str, *args: str, expect_ok: bool = True) -> dict:
    """Run a script from the skill and return its JSON output."""
    result = subprocess.run([sys.executable, str(SCRIPTS / name), *args], capture_output=True, text=True, cwd=SCRIPTS)
    if expect_ok and result.returncode != 0:
        raise AssertionError(f"{name} failed ({result.returncode}): {result.stderr}")
    return json.loads(result.stdout)


def write(root: Path, relative: str, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def git(repo: Path, *args: str, env: dict = None) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True, env=env or GIT_ENV).stdout


def commit(repo: Path, message: str, files: dict, name: str = "Test Author", email: str = "author@example.com", date: str = None) -> None:
    for relative, content in files.items():
        write(repo, relative, content)
    git(repo, "add", "-A")
    env = {**GIT_ENV, "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email}
    if date:
        env.update({"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date})
    git(repo, "commit", "-q", "-m", message, env=env)


def new_repo() -> tuple:
    """A temporary directory holding an empty git repository on branch main."""
    tmp = tempfile.TemporaryDirectory(prefix="ca-test-")
    repo = Path(tmp.name) / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    return tmp, repo
