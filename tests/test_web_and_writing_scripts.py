"""Tests for the scripts that need no repository: github_traction, wayback, capture_page,
claims_lint, md_to_notion and chunk_markdown. Nothing here touches the network."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from helpers import run_script, write

import capture_page
import chunk_markdown
import github_traction as gt
import md_to_notion
import wayback
from common import html_to_text


class ClassifyAssetTest(unittest.TestCase):
    CASES = {
        "latest-mac.yml": ("update-check", "macos"),
        "latest.yml": ("update-check", "windows"),
        "App-1.2.3-arm64-mac.zip.blockmap": ("update-delta", "macos"),
        "App-1.2.3-arm64-mac.zip": ("update-payload-or-archive", "macos"),
        "App.dmg": ("installer", "macos"),
        "App-setup.exe": ("installer", "windows"),
        "App-Setup-1.2.3.exe": ("installer", "windows"),
        "App-amd64.deb": ("installer", "linux"),
        "App.AppImage": ("installer", "linux"),
        "app-release.apk": ("installer", "android"),
        "SHA256SUMS": ("checksum-or-signature", "any"),
        "app-1.2.3.tgz": ("package", "any"),
        "notes.pdf": ("other", "any"),
    }

    def test_categories_and_platforms(self):
        for name, expected in self.CASES.items():
            kind = gt.classify_asset(name, "v1.2.3")
            self.assertEqual((kind["category"], kind["platform"]), expected, name)

    def test_stable_and_versioned_installer_names(self):
        self.assertFalse(gt.classify_asset("App-setup.exe", "v1.2.3")["versioned_name"])
        self.assertTrue(gt.classify_asset("App-Setup-1.2.3.exe", "v1.2.3")["versioned_name"])
        self.assertFalse(gt.classify_asset("App-amd64.deb", "v1.2.3")["versioned_name"])

    def test_last_page_from_link_header(self):
        header = '<https://api.github.com/x?per_page=1&page=2>; rel="next", <https://api.github.com/x?per_page=1&page=104>; rel="last"'
        self.assertEqual(gt.last_page(header), 104)
        self.assertIsNone(gt.last_page(None))

    def test_windows_merge_mirror_releases_and_estimate_running_copies(self):
        asset = lambda name, n: {"name": name, "download_count": n}
        releases = [
            {"tag_name": "v1.0.0", "published_at": "2026-01-01T00:00:00Z", "assets": [asset("App.dmg", 100), asset("latest-mac.yml", 2400)]},
            {"tag_name": "v1.0.0", "published_at": "2026-01-01T00:05:00Z", "assets": [asset("App-setup.exe", 50)]},
            {"tag_name": "v1.1.0", "published_at": "2026-01-02T00:00:00Z", "assets": [asset("App.dmg", 10), asset("latest-mac.yml", 200)]},
        ]
        now = datetime(2026, 1, 3, tzinfo=timezone.utc)
        summary = gt.summarize_releases(releases, 1.0, now)
        self.assertEqual(summary["versions"], 2)
        first = summary["windows"][0]
        self.assertEqual((first["tag"], first["installers"], first["update_checks"]), ("v1.0.0", 150, 2400))
        self.assertEqual(summary["running_copies_estimate"]["copies_running_at_once"], 100)
        self.assertAlmostEqual(summary["update_checks_share_pct"], 94.2, places=1)

    def test_offline_mode_reads_saved_responses(self):
        with tempfile.TemporaryDirectory() as folder:
            saved = Path(folder)
            client = gt.Client(None, None)
            def save(path, params, body, headers=None):
                (saved / client.slug(path, params)).write_text(json.dumps({"body": body, "headers": headers or {}}))
            save("/repos/o/r", {}, {"full_name": "o/r", "stargazers_count": 7, "open_issues_count": 3, "license": {"spdx_id": "MIT"}})
            save("/repos/o/r/contributors", {"per_page": 1, "anon": "false"}, [{"login": "a"}])
            save("/repos/o/r/releases", {"per_page": 100, "page": 1}, [])
            out = run_script("github_traction.py", "o/r", "--offline", folder, "--no-search")
            self.assertEqual(out["repo"]["stars"], 7)
            self.assertEqual(out["contributors_listed"], 1)
            self.assertEqual(out["api_calls"], 0)


class WaybackAndCaptureTest(unittest.TestCase):
    def test_parse_cdx(self):
        rows = [["urlkey", "timestamp", "original", "statuscode"], ["com,example)/", "20260920054828", "https://example.com/", "200"]]
        item = wayback.parse_cdx(rows)[0]
        self.assertEqual(item["date"], "2026-09-20")
        self.assertEqual(item["archive_url"], "https://web.archive.org/web/20260920054828/https://example.com/")
        self.assertEqual(wayback.parse_cdx([]), [])

    def test_html_to_text_and_slug(self):
        html = "<html><head><title>Plans</title><style>p{}</style></head><body><h1>Pro</h1><p>$49 a month</p><script>x()</script></body></html>"
        self.assertEqual(html_to_text(html), "Pro\n$49 a month")
        self.assertEqual(capture_page.slug_for("https://www.example.com/pricing?x=1"), "www.example.com_pricing_x_1")


class ClaimsLintTest(unittest.TestCase):
    def test_forbidden_long_superlative_and_undated(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write(root, "phrases.txt", "# comment\nclone of\nre:\\bkiller\\b\n")
            draft = write(root, "draft.md", "\n".join([
                "> " + " ".join(["word"] * 45),
                "We are not a clone of anything.",
                "The fastest way, 100% of the time.",
                "Acme has 4,000 stars.",
                "Acme had 3,983 stars on 3 Oct 2026.",
                "```", "Acme killer 99", "```",
            ]))
            out = run_script("claims_lint.py", str(draft), "--forbidden", str(root / "phrases.txt"), "--competitor", "Acme",
                             "--superlatives", expect_ok=False)
            rules = [(f["line"], f["rule"]) for f in out["findings"]]
            self.assertIn((1, "too_long"), rules)
            self.assertIn((2, "forbidden"), rules)
            self.assertIn((3, "superlative"), rules)
            self.assertIn((4, "undated_number"), rules)
            self.assertNotIn((5, "undated_number"), rules)
            self.assertFalse(any(line >= 6 for line, _ in rules), "code blocks are skipped")


class NotionTest(unittest.TestCase):
    def convert(self, text, config=None):
        return md_to_notion.Converter(config or {}).convert(text)

    def test_table_escapes_paths_and_title(self):
        out = self.convert("# Title\n\nPrice $29 for <you> in `code` and server/index.ts:12, not @setup.sh.\n\n| A | B |\n|---|---|\n| x \\* y | `p|q` |\n")
        self.assertNotIn("# Title", out)
        self.assertIn("Price \\$29 for \\<you\\>", out)
        self.assertIn("`server/index.ts:12`", out)
        self.assertNotIn("`setup.sh`", out)
        self.assertIn('<table header-row="true">', out)
        self.assertIn("\t\t<td>x \\* y</td>", out)
        self.assertIn("\t\t<td>`p|q`</td>", out)

    def test_mentions_and_nested_lists(self):
        config = {"pages": {"01": "aaa", "A": "bbb"}, "files": {"A": "appendices/A-code.md"},
                  "references": [{"regex": "\\bdocument (0[1-9])\\b", "group": 1}], "mention_url": "https://n/{id}",
                  "literals": [{"text": "the old analysis", "page": "ccc"}]}
        out = self.convert("See document 01, `appendices/A-code.md` and the old analysis.\n\n1. One\n   - nested\n     - deeper\n2. Two\n", config)
        self.assertIn('document <mention-page url="https://n/aaa"/>', out)
        self.assertIn('<mention-page url="https://n/bbb"/>', out)
        self.assertIn('<mention-page url="https://n/ccc"/>', out)
        self.assertIn("\n\t- nested\n\t\t- deeper\n2. Two", out)

    def test_callout_and_warning(self):
        converter = md_to_notion.Converter({"callout_markers": ["Note"]})
        out = converter.convert("> **Note.** Read this.\n\n| A |\n|---|\n| **bold** + more |\n")
        self.assertIn('<callout icon="📌" color="gray_bg">', out)
        self.assertEqual(len(converter.warnings), 1)


class ChunkTest(unittest.TestCase):
    def test_cuts_on_headings_outside_tables(self):
        section = "## Part {n}\n" + "word " * 50 + "\n<table>\n## not a cut\n</table>\n"
        text = "".join(section.format(n=n) for n in range(6))
        cuts = chunk_markdown.cut_points(text)
        self.assertEqual(len(cuts), 5)
        points = chunk_markdown.best_split(len(text), cuts, limit=len(text) // 2 + 50)
        self.assertEqual(points[0], 0)
        self.assertEqual(points[-1], len(text))
        self.assertTrue(all(b - a <= len(text) // 2 + 50 for a, b in zip(points, points[1:])))
        with self.assertRaises(ValueError):
            chunk_markdown.best_split(len(text), [], limit=10)


if __name__ == "__main__":
    unittest.main()
