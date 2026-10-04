"""Tests for the repository tooling: the public-safety scan and the skill validator.
Secrets and email addresses are assembled at run time, so none sits in this file."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import GIT_ENV, ROOT, commit, git, new_repo, write

SAFETY = ROOT / "scripts" / "check_public_safety.py"
VALIDATE = ROOT / "scripts" / "validate.py"
TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9"
PRIVATE_EMAIL = "alice" + "@" + "corp.test"
NOREPLY = "12345+alice" + "@" + "users.noreply.github.com"


def safety(repo: Path, *args: str, denylist: Path = None) -> subprocess.CompletedProcess:
    env = {**GIT_ENV, "PUBLIC_SAFETY_DENYLIST": str(denylist) if denylist else str(repo.parent / "missing.txt")}
    return subprocess.run([sys.executable, str(SAFETY), *args], cwd=repo, capture_output=True, text=True, env=env)


class PublicSafetyTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.repo = new_repo()
        self.denylist = write(Path(self.tmp.name), "deny.txt",
                              "# comment\nprojectzebra\nre:\\bnightjar\\b @allow=/NOTES.md\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_tree_passes(self):
        write(self.repo, "README.md", "Contact: someone" + "@" + "example.com\n")
        result = safety(self.repo, "--require-denylist", denylist=self.denylist)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("private denylist applied", result.stdout)

    def test_working_tree_findings(self):
        write(self.repo, "src/config.ts", f'const token = "{TOKEN}";\n')
        write(self.repo, "docs/team.md", f"Write to {PRIVATE_EMAIL} about projectzebra.\n")
        write(self.repo, "NOTES.md", "nightjar is allowed here\n")
        write(self.repo, "other.md", "but nightjar is not allowed here\n")
        write(self.repo, ".env.local", "X=1\n")
        result = safety(self.repo, denylist=self.denylist)
        self.assertEqual(result.returncode, 1)
        report = result.stderr
        self.assertIn("src/config.ts:1  GitHub token", report)
        self.assertNotIn(TOKEN, report, "values are masked")
        self.assertIn("docs/team.md:1  email address", report)
        self.assertIn('docs/team.md:1  private denylist "projectzebra"', report)
        self.assertIn("other.md:1  private denylist", report)
        self.assertNotIn("NOTES.md", report)
        self.assertIn(".env.local  file that must never be committed", report)

    def test_missing_denylist(self):
        self.assertEqual(safety(self.repo, "--require-denylist").returncode, 1)
        self.assertEqual(safety(self.repo).returncode, 0)

    def test_history_messages_and_identities(self):
        commit(self.repo, "Add notes for projectzebra", {"a.txt": TOKEN + "\n"})
        commit(self.repo, "Remove the token", {"a.txt": "clean\n"}, email=PRIVATE_EMAIL)
        tree = safety(self.repo, denylist=self.denylist)
        self.assertEqual(tree.returncode, 0, "the working tree is clean now")
        history = safety(self.repo, "--history", denylist=self.denylist)
        self.assertEqual(history.returncode, 1)
        self.assertIn("a.txt (history", history.stderr)
        self.assertIn("commit message", history.stderr)
        self.assertNotIn("commit identity", history.stderr)
        identities = safety(self.repo, "--history", "--identities", denylist=self.denylist)
        self.assertIn("author/committer email is not GitHub noreply", identities.stderr)

    def test_unpushed_skips_what_a_remote_has(self):
        commit(self.repo, "Old work with projectzebra", {"a.txt": "a\n"})
        remote = Path(self.tmp.name) / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True, env=GIT_ENV)
        git(self.repo, "remote", "add", "origin", str(remote))
        git(self.repo, "push", "-q", "origin", "main")
        commit(self.repo, "New work", {"b.txt": "b\n"}, email=NOREPLY)
        result = safety(self.repo, "--history", "--unpushed", "--identities", "--require-denylist", denylist=self.denylist)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unknown_option(self):
        self.assertNotEqual(safety(self.repo, "--histroy").returncode, 0)


class ValidateTest(unittest.TestCase):
    def test_this_repository_is_valid(self):
        result = subprocess.run([sys.executable, str(VALIDATE)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_broken_skill_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            skill = root / "skills" / "demo"
            write(skill, "SKILL.md", "---\nname: Demo_Skill\ndescription: \nauthor: me\n---\n\n# Demo \u2014 a skill\n\n"
                                     "See [missing](references/none.md) and [far](../outside.md). Run `scripts/ghost.py`.\n")
            write(skill, "references/a.md", "Link to [b](../SKILL.md).\n")
            write(skill, "scripts/tool.py", '"""A tool without a usage section."""\nprint(1)\n')
            write(skill, "scripts/broken.py", "def f(:\n")
            write(skill, "scripts/data.json", "{not json}\n")
            result = subprocess.run([sys.executable, str(VALIDATE), "--root", folder], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            report = result.stderr
            for expected in ('unknown frontmatter field "author"', 'invalid name "Demo_Skill"', "description must be 1 to 1024",
                             'link "references/none.md" does not resolve', 'link "../outside.md" leaves the skill',
                             "does not resolve inside references/", 'tool.py: the docstring has no "Usage:" section',
                             "tool.py: not named in SKILL.md", "broken.py: does not compile", "data.json: invalid JSON",
                             "names scripts/ghost.py, which does not exist", "long dash"):
                self.assertIn(expected, report)


if __name__ == "__main__":
    unittest.main()
