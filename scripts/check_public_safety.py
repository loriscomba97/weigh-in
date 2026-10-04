#!/usr/bin/env python3
"""Public-safety scan. Runs before every commit and push, and in CI.

This repository is public: whatever lands in it, including history and commit messages, is
published for good. The scan fails when it finds:
  - credentials (Notion, Stripe, GitHub, AWS, Google, Slack, npm, Hugging Face and sk- style
    API keys, JWTs, private keys);
  - files that must never be committed (.env files, keys, service-account JSON);
  - email addresses other than example.* and GitHub noreply ones in files;
  - with --identities: commit author or committer emails that are not GitHub noreply, and any
    email address in commit messages;
  - terms from the maintainer's private denylist (names, internal ids, domains), in file
    contents, file paths and commit messages. The denylist lives OUTSIDE the repository, so the
    list itself is never published.

Usage:
  python3 scripts/check_public_safety.py             working tree (tracked + untracked, not ignored)
  python3 scripts/check_public_safety.py --history   every blob, path and commit message in every ref
  --unpushed           with --history: only what no remote has yet
  --identities         with --history: commit identities too (maintainer hooks)
  --require-denylist   fail when the private denylist is missing (maintainer hooks)

CI runs --history without --identities: contributors commit with whatever email they like, and
the maintainer's own identity is checked by the hooks before anything leaves their machine.

Private denylist: the path in $PUBLIC_SAFETY_DENYLIST, else "<repo-folder>.denylist.txt" next to
the repository folder. One case-insensitive literal per line, "re:<regex>" for a pattern, and an
optional " @allow=path1,path2" suffix that permits the term in those files only. An entry that
starts with "/" names one file from the repository root ("/README.md"); any other entry matches
that path or any path ending with "/<entry>". Commit messages match no entry. Lines starting
with "#" are comments. The scan reports which entry matched, never the denylist itself.

Standard library only, Python 3.9 or later.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ARGS = set(sys.argv[1:])
KNOWN = {"--history", "--unpushed", "--identities", "--require-denylist"}
if ARGS - KNOWN:
    sys.exit(f"check_public_safety: unknown option(s) {sorted(ARGS - KNOWN)}; see the header of this script.")
HISTORY = "--history" in ARGS
UNPUSHED = "--unpushed" in ARGS
IDENTITIES = "--identities" in ARGS
REQUIRE_DENYLIST = "--require-denylist" in ARGS


def git(*args: str, data: bytes = None) -> bytes:
    return subprocess.run(["git", *args], input=data, capture_output=True, check=True, cwd=ROOT).stdout


ROOT = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip())

SECRET_RULES = [
    ("Notion token", re.compile(r"\b(?:secret_[A-Za-z0-9]{43}|ntn_[A-Za-z0-9]{40,})\b")),
    ("Stripe key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{10,}\b")),
    ("Stripe webhook secret", re.compile(r"\bwhsec_[A-Za-z0-9]{10,}\b")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("npm token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{34,}\b")),
    ("sk- style API key", re.compile(r"\bsk-(?:[a-z]+-)*[A-Za-z0-9_-]{32,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("Private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ALLOWED_EMAIL = re.compile(r"(?:@example\.(?:com|org|net)|@users\.noreply\.github\.com|^noreply@github\.com)$", re.I)
IDENTITY_EMAIL = re.compile(r"(?:@users\.noreply\.github\.com|^noreply@github\.com)$", re.I)
FORBIDDEN_FILE = re.compile(
    r"(?:^|/)(?:\.env(?!\.example$)[^/]*|[^/]*\.(?:pem|key|p12|pfx)|id_(?:rsa|ecdsa|ed25519)[^/]*|[^/]*service[-_]?account[^/]*\.json)$",
    re.I,
)

findings = []


def report(where: str, line: int, rule: str, detail: str = "") -> None:
    findings.append(f"{where}{f':{line}' if line else ''}  {rule}{f'  {detail}' if detail else ''}")


def mask(value: str) -> str:
    return f"{value[:4]}... ({len(value)} chars)"


def is_binary(data: bytes) -> bool:
    return b"\0" in data[:8000]


def allowed(rule: dict, file: str) -> bool:
    """A denylist term with @allow entries is permitted in the matching files only, never in commit messages."""
    if not file:
        return False
    return any(file == a[1:] if a.startswith("/") else (file == a or file.endswith("/" + a)) for a in rule["allow"])


def load_denylist():
    path = Path(os.environ.get("PUBLIC_SAFETY_DENYLIST") or ROOT.parent / f"{ROOT.name}.denylist.txt")
    if not path.exists():
        return None
    rules = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^(.*?)\s+@allow=(\S+)$", line)
        term = (match.group(1) if match else line).strip()
        allow = match.group(2).split(",") if match else []
        pattern = re.compile(term[3:], re.I) if term.startswith("re:") else re.compile(re.escape(term), re.I)
        rules.append({"label": f'private denylist "{term}"', "re": pattern, "allow": allow})
    return rules


DENY = load_denylist()
if DENY is None:
    message = "private denylist not found (see the header of this script)"
    if REQUIRE_DENYLIST:
        sys.exit(f"check_public_safety: {message}; refusing to continue.")
    print(f"check_public_safety: {message}; running the generic checks only.", file=sys.stderr)


def scan_text(text: str, where: str, file: str, emails: bool = True) -> None:
    for number, line in enumerate(text.split("\n"), 1):
        for label, pattern in SECRET_RULES:
            match = pattern.search(line)
            if match:
                report(where, number, label, mask(match.group(0)))
        if emails:
            for address in EMAIL.findall(line):
                if not ALLOWED_EMAIL.search(address):
                    report(where, number, "email address", mask(address))
        for rule in DENY or []:
            if not allowed(rule, file) and rule["re"].search(line):
                report(where, number, rule["label"])


def scan_path(file: str, where: str) -> None:
    for rule in DENY or []:
        if not allowed(rule, file) and rule["re"].search(file):
            report(where, 0, f"{rule['label']} in the file path")


def scan_history() -> None:
    # Every ref, or with --unpushed only what no remote-tracking ref already has: commits merged on
    # the remote (a contributor's pull request, say) are public already and never block a push.
    refs = ["--all", "--not", "--remotes"] if UNPUSHED else ["--all"]
    path_of = {}
    for line in git("rev-list", "--objects", *refs).decode("utf-8", "replace").split("\n"):
        sha, _, path = line.partition(" ")
        if sha and path and sha not in path_of:
            path_of[sha] = path
    types = git("cat-file", "--batch-check=%(objectname) %(objecttype)", data="\n".join(path_of).encode() + b"\n") if path_of else b""
    seen_paths = set()
    for line in types.decode().split("\n"):
        sha, _, kind = line.partition(" ")
        if kind != "blob":
            continue
        file = path_of[sha]
        if FORBIDDEN_FILE.search(file):
            report(f"{file} (history)", 0, "file that must never be committed")
        if file not in seen_paths:
            seen_paths.add(file)
            scan_path(file, f"{file} (history)")
        data = git("cat-file", "blob", sha)
        if not is_binary(data):
            scan_text(data.decode("utf-8", "replace"), f"{file} (history {sha[:7]})", file)
    if not git("rev-list", *refs, "--max-count=1").strip():
        return
    if IDENTITIES:
        for address in sorted(set(git("log", *refs, "--format=%ae%n%ce").decode().split())):
            if not IDENTITY_EMAIL.search(address):
                report("commit identity", 0, "author/committer email is not GitHub noreply", mask(address))
    for entry in git("log", *refs, "--format=%h%x00%B%x01").decode("utf-8", "replace").split("\x01"):
        sha, _, body = entry.lstrip("\n").partition("\0")
        if sha and body:
            scan_text(body, f"commit message {sha}", "", emails=IDENTITIES)


def scan_working_tree() -> None:
    files = [f for f in git("ls-files", "-z", "--cached", "--others", "--exclude-standard").decode().split("\0") if f]
    for file in files:
        if FORBIDDEN_FILE.search(file):
            report(file, 0, "file that must never be committed")
        scan_path(file, file)
        path = ROOT / file
        if not path.is_file():
            continue
        data = path.read_bytes()
        if not is_binary(data):
            scan_text(data.decode("utf-8", "replace"), file, file)


if HISTORY:
    scan_history()
else:
    scan_working_tree()

if findings:
    print(f"check_public_safety: {len(findings)} finding(s). Nothing may be committed or pushed until they are fixed.", file=sys.stderr)
    for finding in findings:
        print(f"  {finding}", file=sys.stderr)
    sys.exit(1)
print(f"check_public_safety: clean ({'history' if HISTORY else 'working tree'}{', private denylist applied' if DENY else ''}).")
