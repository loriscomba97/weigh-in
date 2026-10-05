"""Tests for removals.py: what disappeared between two commits and between two captures of a page."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import SCRIPTS, commit, git, new_repo, run_script, write

README_BEFORE = (
    "# Acme\n\n## Install\n\nnpm i acme\n\n## Teams plan\n\nShared notes for teams.\n\n"
    "## Works with [Slack](https://example.com/slack)\n\n```\n# a comment, not a heading\n```\n"
)
GUIDE_BODY = "".join(f"Step {n}: share a note with a link and pick who can edit it.\n" for n in range(1, 9))
README_AFTER = "# Acme\n\n## Install\n\nnpm i acme\n\n```\n# a comment, not a heading\n```\n"


class CommitsTest(unittest.TestCase):
    def test_removed_folders_files_and_headings_with_renames_and_moves_apart(self):
        tmp, repo = new_repo()
        with tmp:
            commit(repo, "first", {
                "README.md": README_BEFORE,
                "src/teams/invite.ts": "export const invite = 1;\n",
                "src/teams/roles.ts": "export const roles = 1;\n",
                "src/core.ts": "export const core = 'a line long enough to keep the rename detectable';\n",
                "docs/teams.md": "# Teams\n\nInvite your team.\n",
                "docs/install.md": "# Install\n\n## macOS\n",
                "docs/guide.md": "# Guide\n\n## Sharing\n\n" + GUIDE_BODY,
                "tests/teams.test.ts": "test('invite', () => {});\n",
                "lib/old/a.py": "A = 1\n" * 20,
                "lib/old/b.py": "B = 2\n" * 20,
            })
            old = git(repo, "rev-parse", "HEAD").strip()
            git(repo, "rm", "-q", "-r", "src/teams", "docs/teams.md", "tests/teams.test.ts")
            git(repo, "mv", "src/core.ts", "src/engine.ts")
            git(repo, "mv", "lib/old", "lib/new")
            git(repo, "mv", "docs/guide.md", "docs/handbook.md")
            commit(repo, "second", {
                "README.md": README_AFTER,
                "docs/install.md": "# Install\n\n## macOS\n\n## Windows\n",
                "docs/handbook.md": "# Guide\n\n" + GUIDE_BODY,
                "src/new.ts": "export const fresh = 1;\n",
            })
            out = run_script("removals.py", "commits", str(repo), old)

            self.assertEqual(out["old"]["commit"], old)
            self.assertEqual(out["new"]["commit"], git(repo, "rev-parse", "HEAD").strip())
            removed = {d["path"]: (d["files"], d["kind"]) for d in out["removed_dirs"]}
            self.assertEqual(removed, {"src/teams": (2, "source_and_other"), "tests": (1, "tests")})
            self.assertEqual(out["moved_dirs"], [{"from": "lib/old", "to": "lib/new", "files": 2, "renamed": 2}])

            deleted = out["deleted_files"]
            self.assertEqual(deleted["by_kind"], {"source_and_other": 2, "docs": 1, "tests": 1})
            self.assertEqual(deleted["docs"], ["docs/teams.md"])
            self.assertEqual(deleted["source_and_other"], ["src/teams/invite.ts", "src/teams/roles.ts"])
            self.assertNotIn("src/core.ts", deleted["source_and_other"])
            self.assertEqual(out["files"]["renamed"], 4)
            self.assertEqual(out["files"]["added"], 1)

            headings = {(h["file"], h["heading"], h["level"], h.get("was")) for h in out["removed_headings"]}
            self.assertEqual(headings, {
                ("README.md", "Teams plan", 2, None),
                ("README.md", "Works with [Slack](https://example.com/slack)", 2, None),
                ("docs/handbook.md", "Sharing", 2, "docs/guide.md"),
            })
            self.assertEqual(out["rename_detection"], "complete")

    def test_nothing_removed_renumbered_sections_and_a_bad_revision(self):
        tmp, repo = new_repo()
        with tmp:
            commit(repo, "first", {"README.md": "# Acme\n\n## 1. Install\n\n## 2. Reading the code safely\n"})
            commit(repo, "second", {"README.md": "# Acme\n\n## 1. Install\n\n## 2. Sync\n\n## 3. Reading the code safely\n",
                                    "src/sync.ts": "x\n"})
            out = run_script("removals.py", "commits", str(repo), "HEAD~1", "HEAD")
            self.assertEqual((out["removed_dirs"], out["removed_headings"], out["files"]["deleted"]), ([], [], 0))
            self.assertEqual(out["warnings"], [])
            result = subprocess.run([sys.executable, str(SCRIPTS / "removals.py"), "commits", str(repo), "no-such-rev"],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no-such-rev", result.stderr)


    def test_partial_clones_are_flagged(self):
        tmp, repo = new_repo()
        with tmp:
            commit(repo, "first", {"docs/a.md": "# A\n\n## Old\n"})
            commit(repo, "second", {"docs/a.md": "# A\n"})
            git(repo, "config", "uploadpack.allowfilter", "true")
            git(Path(tmp.name), "clone", "-q", "--filter=blob:none", f"file://{repo}", "partial")
            out = run_script("removals.py", "commits", str(Path(tmp.name) / "partial"), "HEAD~1")
            self.assertEqual(len(out["warnings"]), 1)
            self.assertEqual([h["heading"] for h in out["removed_headings"]], ["Old"])


class PagesTest(unittest.TestCase):
    def test_removed_reworded_added_and_short_lines(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = write(root, "pricing-0901.txt", "Pricing\nFree for one person\nTeam plan: $49 per seat a month\n"
                                                  "Self-hosted option for companies\nSign in\nSelf-hosted option for companies\n")
            new = write(root, "pricing-1005.txt", "Pricing\nFree for  one PERSON\nTeam plan: $59 per seat a month\n"
                                                  "Enterprise: contact us\nSign in\n")
            out = run_script("removals.py", "pages", str(old), str(new))
            self.assertEqual(out["removed"], [{"line": 4, "text": "Self-hosted option for companies"}])
            self.assertEqual(len(out["reworded"]), 1)
            self.assertEqual((out["reworded"][0]["before"], out["reworded"][0]["after"]),
                             ("Team plan: $49 per seat a month", "Team plan: $59 per seat a month"))
            self.assertEqual(out["added_total"], 1)
            self.assertEqual(out["kept_total"], 1)
            everything = run_script("removals.py", "pages", str(old), str(new), "--min-chars", "0", "--similarity", "1")
            self.assertEqual(everything["removed_total"], 2)
            self.assertEqual(everything["reworded_total"], 0)

    def test_html_captures_are_read_as_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = write(root, "features-old.html", "<html><head><title>Features</title><script>var a = 1;</script></head>"
                                                   "<body><h2>Teams</h2><p>Shared workspaces for teams</p><p>Offline mode for every note</p></body></html>")
            new = write(root, "features-new.html", "<html><body><p>Offline mode for every note</p></body></html>")
            out = run_script("removals.py", "pages", str(old), str(new))
            self.assertEqual([r["text"] for r in out["removed"]], ["Shared workspaces for teams"])
            self.assertEqual(out["kept_total"], 1)


if __name__ == "__main__":
    unittest.main()
