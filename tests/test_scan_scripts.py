"""Tests for the scanners: telemetry_scan, license_scan and app_security_scan."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from helpers import commit, new_repo, run_script, write

MIT = "MIT License\n\nCopyright (c) 2026 Example Person\n\nPermission is hereby granted, free of charge, to any person\n"
APACHE = "Apache License\nVersion 2.0, January 2004\nhttp://www.apache.org/licenses/\n"
AGPL = "GNU AFFERO GENERAL PUBLIC LICENSE\nVersion 3, 19 November 2007\n"
CUSTOM = "Example Enterprise License\nAll rights reserved. Production use requires a valid license key.\n"


class TelemetryScanTest(unittest.TestCase):
    def test_finds_sdks_hosts_and_controls_but_not_tests_or_lookalikes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write(root, "package.json", '{"dependencies": {"posthog-js": "1.0.0"}}\n')
            write(root, "src/analytics.ts", 'posthog.init(TOKEN, { api_host: "https://us.i.posthog.com" });\nconst optOut = settings.telemetryEnabled === false;\n')
            write(root, "src/ui.css", ".panel { overflow: auto; } /* scrollbar styling */\n")
            write(root, "src/ui.ts", "const scrollbar = 12;\n")
            write(root, "src/api.ts", 'fetch("https://api.example-vendor.io/v1/things");\n')
            write(root, "tests/analytics.test.ts", 'import * as Sentry from "@sentry/node";\n')
            out = run_script("telemetry_scan.py", folder)
            names = {s["name"] for s in out["sdks"]}
            self.assertEqual(names, {"PostHog"})
            hosts = {h["host"]: h for h in out["hosts"]}
            self.assertEqual(hosts["us.i.posthog.com"]["telemetry"], "PostHog")
            self.assertIn("api.example-vendor.io", hosts)
            self.assertTrue(any("optOut" in c["text"] for c in out["controls"]))
            with_tests = run_script("telemetry_scan.py", folder, "--include-tests")
            self.assertIn("Sentry", {s["name"] for s in with_tests["sdks"]})


    def test_a_domain_in_an_integration_catalog_is_a_mention_not_usage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write(root, "server/catalog.ts", '{ slug: "sentry", label: "Sentry", domain: "sentry.io" },\n')
            write(root, "src/errors.ts", 'import * as Sentry from "@sentry/electron";\nSentry.init({});\n')
            write(root, "web/index.html", '<script defer src="https://plausible.io/js/script.js"></script>\n')
            out = run_script("telemetry_scan.py", folder)
            strength = {s["name"]: s["strength"] for s in out["sdks"]}
            self.assertEqual(strength["Sentry"], "usage")
            self.assertEqual(strength["Plausible"], "usage")
            catalog = [h for s in out["sdks"] for h in s["hits"] if h["file"] == "server/catalog.ts"]
            self.assertEqual([h["match"] for h in catalog], ["mention"])
            write(root, "src/errors.ts", "export {};\n")
            again = run_script("telemetry_scan.py", folder)
            self.assertEqual({s["name"]: s["strength"] for s in again["sdks"]}["Sentry"], "mention only")


class LicenseScanTest(unittest.TestCase):
    def test_families_flags_manifests_lockfiles_and_history(self):
        tmp, repo = new_repo()
        with tmp:
            commit(repo, "Add MIT license", {"LICENSE": MIT})
            commit(repo, "Relicense to Apache 2.0", {
                "LICENSE": APACHE, "enterprise/LICENSE": CUSTOM, "vision/LICENSE": AGPL,
                "package.json": '{"name": "x", "license": "Apache-2.0"}\n',
                "pnpm-lock.yaml": "lockfileVersion: '9.0'\n\npackages:\n\n  '@scope/a@1.0.0':\n    resolution: {}\n\n  b@2.0.0:\n    resolution: {}\n",
                "src/main.ts": "// SPDX-License-Identifier: Apache-2.0\nexport {};\n",
                "CONTRIBUTING.md": "Sign every commit with Signed-off-by (the Developer Certificate of Origin).\n",
                ".github/workflows/license-check.yml": "name: license check\n",
            })
            out = run_script("license_scan.py", str(repo))
            families = {f["path"]: f["family"] for f in out["license_files"]}
            self.assertEqual(families["LICENSE"], "Apache-2.0")
            self.assertEqual(families["enterprise/LICENSE"], "Proprietary or custom")
            self.assertEqual(families["vision/LICENSE"], "AGPL-3.0")
            self.assertNotIn(".github/workflows/license-check.yml", families)
            self.assertEqual(out["flags"]["copyleft"], ["AGPL-3.0"])
            self.assertIn("Proprietary or custom", out["flags"]["source_available_or_custom"])
            self.assertTrue(out["flags"]["more_than_one_family"])
            self.assertEqual(out["manifests"], [{"path": "package.json", "license": "Apache-2.0"}])
            self.assertEqual(out["lockfiles"][0]["entries"], 2)
            self.assertEqual(out["spdx_headers"]["by_identifier"], {"Apache-2.0": 1})
            self.assertEqual([h["subject"] for h in out["history"]["LICENSE"]], ["Relicense to Apache 2.0", "Add MIT license"])
            self.assertTrue(out["contribution_terms"][0]["mentions"])

    def test_missing_root_license(self):
        with tempfile.TemporaryDirectory() as folder:
            write(Path(folder), "src/a.py", "x = 1\n")
            self.assertTrue(run_script("license_scan.py", folder)["flags"]["missing_root_license"])


class AppSecurityScanTest(unittest.TestCase):
    def test_entitlements_electron_secrets_and_placeholders(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write(root, "build/entitlements.mac.plist", (
                '<?xml version="1.0" encoding="UTF-8"?>\n<plist version="1.0"><dict>\n'
                "<key>com.apple.security.cs.disable-library-validation</key><true/>\n"
                "<key>com.apple.security.cs.allow-jit</key><true/>\n"
                "<key>com.apple.security.device.audio-input</key><true/>\n</dict></plist>\n"))
            write(root, "package.json", '{"devDependencies": {"electron": "40.0.0", "electron-updater": "6.0.0"}}\n')
            write(root, "electron/main.js", "new BrowserWindow({ webPreferences: { contextIsolation: false, nodeIntegration: true } });\n")
            token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9"
            write(root, "src/config.ts", f'const token = "{token}";\n')
            write(root, "docs/setup.ts", 'const key = "AKIA" + "REDACTEDREDACTED";\nconst k2 = "' + "AKIA" + "REDACTEDREDACTED" + '";\n')
            write(root, ".env", "SECRET=1\n")
            write(root, "server/main.ts", 'http.createServer(handler).listen(8787, "0.0.0.0");\nconst local = { host: "127.0.0.1" };\n')
            write(root, "server/app.py", 'app.run(host="0.0.0.0", port=8000)\n')
            out = run_script("app_security_scan.py", folder)["signals"]
            macos = [s["signal"] for s in out["macos"]]
            self.assertIn("risky entitlement com.apple.security.cs.disable-library-validation", macos)
            self.assertIn("privacy-sensitive entitlements", macos)
            electron = [s["signal"] for s in out["electron"]]
            self.assertIn("contextIsolation disabled", electron)
            self.assertIn("nodeIntegration enabled", electron)
            self.assertTrue(any("no fuses" in s for s in electron))
            exposed = [(s["file"], s["line"]) for s in out["web"] if s["signal"] == "server bound to every network interface"]
            self.assertEqual(exposed, [("server/app.py", 1), ("server/main.ts", 1)])
            secrets = out["secrets"]
            self.assertTrue(any(s["signal"] == "GitHub token" for s in secrets))
            self.assertFalse(any(token in str(s) for s in secrets), "the value must be masked")
            self.assertFalse(any(s["signal"] == "AWS access key" for s in secrets), "placeholders are not leaks")
            self.assertTrue(any(s["signal"] == "file that should never be committed" for s in secrets))


if __name__ == "__main__":
    unittest.main()
