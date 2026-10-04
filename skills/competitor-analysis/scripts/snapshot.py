#!/usr/bin/env python3
"""Pin the snapshot an analysis refers to: clone a repository when given a URL, then record it.

Usage:
  python3 snapshot.py https://github.com/owner/repo --dest work/repo
  python3 snapshot.py path/to/an/existing/clone

With a URL, clones the full history into --dest, which must not exist yet. With a path, reads
the clone as it is: no fetch, no checkout, no reset. Prints JSON with the remote, the HEAD
commit and its date, the branch, the default branch, the counts of commits, branches and tags,
the first commit date, whether the working tree has local changes, and the time of the snapshot.
Every number in the analysis then refers to this commit.

It also says whether the clone is shallow or partial (made with --depth or --filter). The other
scripts read history and file contents: in a shallow clone the history stops early, and in a
partial clone git fetches missing objects from the network as they are read, or fails offline.
Clone again without those options for the analysis.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from common import git, is_git_repo, now_utc, print_json


def looks_like_url(value: str) -> bool:
    return "://" in value or value.startswith("git@")


def describe(repo: Path) -> dict:
    head = git(repo, "rev-parse", "HEAD").strip()
    roots = git(repo, "rev-list", "--max-parents=0", "HEAD").split()
    first_date = git(repo, "log", "-1", "--format=%cI", roots[-1]).strip() if roots else None
    remote = git(repo, "config", "--get", "remote.origin.url", check=False).strip() or None
    default = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False).strip() or None
    return {
        "taken_at": now_utc(),
        "path": str(repo.resolve()),
        "remote": remote,
        "head": head,
        "head_short": head[:8],
        "head_date": git(repo, "log", "-1", "--format=%cI", "HEAD").strip(),
        "head_subject": git(repo, "log", "-1", "--format=%s", "HEAD").strip(),
        "branch": git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip(),
        "default_branch": default.split("/", 1)[-1] if default else None,
        "commits_on_head": int(git(repo, "rev-list", "--count", "HEAD").strip()),
        "remote_branches": len([b for b in git(repo, "branch", "-r").splitlines() if "->" not in b and b.strip()]),
        "tags": len(git(repo, "tag").splitlines()),
        "first_commit_date": first_date,
        "local_changes": bool(git(repo, "status", "--porcelain").strip()),
        **clone_kind(repo),
    }


def clone_kind(repo: Path) -> dict:
    shallow = git(repo, "rev-parse", "--is-shallow-repository", check=False).strip() == "true"
    partial = git(repo, "config", "--get", "remote.origin.partialclonefilter", check=False).strip() or None
    warnings = []
    if shallow:
        warnings.append("Shallow clone: history stops early, so commit counts, authors and growth are incomplete.")
    if partial:
        warnings.append(f"Partial clone ({partial}): git fetches missing objects while scripts read them, or fails offline.")
    return {"shallow": shallow, "partial_clone_filter": partial, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="repository URL to clone, or path to an existing clone")
    parser.add_argument("--dest", help="where to clone a URL; must not exist yet")
    args = parser.parse_args()

    if looks_like_url(args.source):
        if not args.dest:
            parser.error("a URL needs --dest")
        dest = Path(args.dest)
        if dest.exists():
            parser.error(f"{dest} already exists; pass the existing clone as the source instead")
        result = subprocess.run(["git", "clone", "--quiet", args.source, str(dest)], capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stderr.strip(), file=sys.stderr)
            return 1
        repo = dest
    else:
        repo = Path(args.source)
        if not is_git_repo(repo):
            parser.error(f"{repo} is not a git working tree")

    print_json(describe(repo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
