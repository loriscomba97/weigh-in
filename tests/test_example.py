"""The example in docs/example.md quotes what the scripts print on Acme Notes. This test rebuilds
the fictional repository and checks those numbers, so the example cannot drift from the scripts."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, run_script

MAKE_ACME = ROOT / "docs" / "example" / "make_acme.py"


class ExampleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ca-acme-")
        cls.repo = Path(cls.tmp.name) / "acme"
        cls.raw = Path(cls.tmp.name) / "raw"
        subprocess.run([sys.executable, str(MAKE_ACME), str(cls.repo), "--raw", str(cls.raw)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_history(self):
        snap = run_script("snapshot.py", str(self.repo))
        self.assertEqual((snap["head_short"], snap["commits_on_head"], snap["tags"]), ("c739bf75", 13, 3))
        stats = run_script("git_stats.py", str(self.repo))
        same = stats["authors"]["possible_same_person"]
        self.assertEqual([(g["names"], g["identities"], g["commits"]) for g in same], [(["Dana Reyes"], 2, 8)])
        self.assertEqual(stats["authors"]["bus_factor_50"], 1)
        self.assertEqual((stats["fixes"]["non_merge_fix_commits"], stats["fixes"]["share_pct"]), (3, 23.1))
        self.assertEqual(stats["releases"]["version_tags"], 3)
        self.assertEqual(stats["ai_assisted"]["non_merge_commits_with_assistant_trailer"], 1)

    def test_licenses(self):
        out = run_script("license_scan.py", str(self.repo))
        families = {f["path"]: f["family"] for f in out["license_files"]}
        self.assertEqual(families, {"LICENSE": "MIT", "ee/LICENSE": "Proprietary or custom", "sync-server/LICENSE": "AGPL-3.0"})
        self.assertEqual(out["history"]["LICENSE"][0]["subject"], "Relicense the core from Apache-2.0 to MIT")
        self.assertIn("CLA", out["contribution_terms"][0]["mentions"][0])

    def test_telemetry_and_security(self):
        telemetry = run_script("telemetry_scan.py", str(self.repo))
        strength = {s["name"]: s["strength"] for s in telemetry["sdks"]}
        self.assertEqual(strength, {"PostHog": "usage", "Sentry": "mention only"})
        hits = {(h["file"], h["line"]) for s in telemetry["sdks"] for h in s["hits"]}
        self.assertIn(("src/analytics.ts", 4), hits)
        self.assertIn(("src/integrations/catalog.ts", 3), hits)
        self.assertIn(("src/analytics.ts", 5), {(c["file"], c["line"]) for c in telemetry["controls"]})
        self.assertIn(("src/settings.ts", 1), {(c["file"], c["line"]) for c in telemetry["controls"]})
        security = run_script("app_security_scan.py", str(self.repo))["signals"]
        electron = {s["signal"] for s in security["electron"]}
        self.assertTrue({"contextIsolation disabled", "nodeIntegration enabled"} <= electron)
        self.assertTrue(any("no fuses" in s for s in electron))
        self.assertEqual([(s["file"], s["line"]) for s in security["web"] if "interface" in s["signal"]], [("sync-server/server.ts", 4)])

    def test_dependencies_and_traction(self):
        deps = {c["name"]: c for c in run_script("dependency_versions.py", str(self.repo))["components"]}
        self.assertEqual(deps["electron"]["resolved"], ["37.2.0"])
        out = run_script("github_traction.py", "acme/acme-notes", "--offline", str(self.raw), "--no-search", "--check-interval-hours", "4")
        self.assertEqual((out["repo"]["stars"], out["repo"]["watchers"], out["repo"]["open_issues_plus_prs"]), (1234, 21, 64))
        self.assertEqual(out["contributors_listed"], 3)
        downloads = out["release_downloads"]
        self.assertEqual(downloads["assets_total_downloads"], 171800)
        self.assertEqual((downloads["update_checks_share_pct"], downloads["installers_share_pct"]), (97.2, 1.6))
        estimate = downloads["running_copies_estimate"]
        self.assertEqual((estimate["update_checks_per_day_recent"], estimate["copies_running_at_once"]), (1908.9, 318))
        per_day = [w["installers_per_day"] for w in downloads["windows"][:2]]
        self.assertEqual(per_day, [72.4, 19.4])


if __name__ == "__main__":
    unittest.main()
