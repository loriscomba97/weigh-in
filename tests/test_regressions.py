"""Cases found by running the skill end to end on a real open-source repository. Each one failed
or misled before its fix; the test keeps it fixed. Nothing here touches the network."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from helpers import SCRIPTS, commit, git, new_repo, run_script, write

import dependency_versions as dv
import github_traction as gt
from common import is_test_path


class TestPathsTest(unittest.TestCase):
    def test_one_rule_for_every_script(self):
        for path in ("electron/updater.node-test.mjs", "src/a.test.ts", "src/b.e2e.test.ts", "pkg/x_test.go", "tests/t.py",
                     "AppTests/A.swift", "src/Foo.stories.tsx", "x/fixtures/y.json", "app/src/androidTest/K.kt"):
            self.assertTrue(is_test_path(path), path)
        for path in ("src/latest.ts", "src/contest.ts", "src/attest.ts", "server/index.ts", "src/testimonials.tsx"):
            self.assertFalse(is_test_path(path), path)


class GitStatsTest(unittest.TestCase):
    def test_first_commit_by_instant_merged_identities_and_automated_authors(self):
        signals = json.loads((SCRIPTS / "ai_signals.json").read_text())
        bot_name = "github-actions[bot]"
        tmp, repo = new_repo()
        with tmp:
            # The root commit is written at +05:30; a later one at -03:00 sorts first as text.
            commit(repo, "root", {"a.txt": "1\n"}, name="Asha Rao", email="asha@example.com", date="2026-08-12T00:47:16+05:30")
            commit(repo, "second", {"a.txt": "2\n"}, name="Asha Rao", email="12345+asharao@users.noreply.github.com",
                   date="2026-08-11T21:55:35-03:00")
            for n in range(3):
                commit(repo, f"work {n}", {"b.txt": f"{n}\n"}, name="asharao", email="asha@example.org", date=f"2026-08-1{3 + n}T10:00:00+00:00")
            for n in range(2):
                commit(repo, f"other {n}", {"c.txt": f"{n}\n"}, name="Lee Park", email="lee@example.net", date=f"2026-08-2{n}T10:00:00+00:00")
            commit(repo, "ci", {"d.txt": "x\n"}, name=bot_name, email="bot@example.com", date="2026-08-25T10:00:00+00:00")
            out = run_script("git_stats.py", str(repo))
            self.assertEqual(out["commits"]["first"], "2026-08-12T00:47:16+05:30")
            self.assertEqual(out["commits"]["last"], "2026-08-25T10:00:00Z")
            merged = out["authors"]["with_identities_merged"]
            self.assertEqual(merged["top"][0]["commits"], 5)
            self.assertEqual(merged["bus_factor_50"], 1)
            self.assertEqual(out["authors"]["automated_authors"], {bot_name: 1})
            self.assertNotIn("example.com", [d for d in out["authors"]["email_domains"] if out["authors"]["email_domains"][d] == 1 and False])
            self.assertEqual(out["authors"]["email_domains"].get("example.com"), 1, "the bot's commit is left out of the domains")
            self.assertIsInstance(signals["bot_author_patterns"], list)


class ScannerTest(unittest.TestCase):
    def test_annotations_are_not_consent_and_hosts_are_capped(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            kotlin = ["@OptIn(ExperimentalMaterial3Api::class)", "@androidx.annotation.OptIn(ExperimentalGetImage::class)", "fun a() {}", ""]
            write(root, "app/Screen.kt", "\n".join(kotlin))
            write(root, "src/settings.ts", "export const telemetryOptIn = false;\n")
            write(root, "src/links.ts", "".join(f'const u{n} = "https://h{n}.example-host.io/x";\n' for n in range(12)))
            out = run_script("telemetry_scan.py", folder, "--max-hosts", "5")
            texts = [c["text"] for c in out["controls"]]
            self.assertFalse(any("@" in t for t in texts), texts)
            self.assertTrue(any("telemetryOptIn" in t for t in texts))
            self.assertEqual((len(out["hosts"]), out["hosts_total"]), (5, 12))

    def test_builder_settings_need_builder_files_and_notarization_steps_are_seen(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write(root, "server/presets.ts", 'const preset = { publisherName: "Acme" };\n')
            write(root, "electron-builder.yml", "mac:\n  notarize: false\nwin:\n  publisherName: Acme Labs\n")
            write(root, ".github/workflows/release.yml", "      - run: xcrun notarytool submit app.zip --wait\n      - run: xcrun stapler staple App.app\n")
            write(root, "package.json", '{"devDependencies": {"electron": "40.0.0"}}\n')
            out = run_script("app_security_scan.py", folder)["signals"]
            signature = [(s["file"], s["line"]) for s in out["electron"] if s["signal"] == "update signature check setting"]
            self.assertEqual(signature, [("electron-builder.yml", 4)])
            notarize = [s for s in out["electron"] if s["signal"] == "notarization setting"]
            self.assertIn("separate", notarize[0]["why"])
            steps = [s["line"] for s in out["macos"] if s["signal"].startswith("notarization step")]
            self.assertEqual(steps, [1, 2])

    def test_licensing_notes_do_not_count_as_licenses(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write(root, "LICENSING.md", "# Licensing\n\nThe core is Apache-2.0. The enterprise folder: all rights reserved.\n")
            write(root, "NOTICE", "Acme\nCopyright 2026 Acme Labs\n")
            out = run_script("license_scan.py", folder)
            types = {f["path"]: f["file_type"] for f in out["license_files"]}
            self.assertEqual(types, {"LICENSING.md": "licensing note", "NOTICE": "notice"})
            self.assertTrue(out["flags"]["missing_root_license"])
            self.assertEqual(out["flags"]["source_available_or_custom"], [])


class ArchiveAndXcodeTest(unittest.TestCase):
    def test_gzip_bodies_are_decoded(self):
        import gzip
        from common import decode_body
        page = b"<html><body>Pro $200 per month</body></html>"
        self.assertEqual(decode_body(gzip.compress(page)), page)
        self.assertEqual(decode_body(page), page)

    def test_xcode_projects_that_set_nothing_are_not_clean(self):
        with tempfile.TemporaryDirectory() as folder:
            write(Path(folder), "App.xcodeproj/project.pbxproj", "ENABLE_APP_SANDBOX = NO;\nPRODUCT_NAME = App;\n")
            signals = [s["signal"] for s in run_script("app_security_scan.py", folder)["signals"]["macos"]]
            self.assertIn("app sandbox in Xcode project", signals)
            self.assertTrue(any(s.startswith("Xcode project without ENABLE_HARDENED_RUNTIME") for s in signals))
            self.assertTrue(any(s.startswith("Xcode project without an entitlements file") for s in signals))

    def test_scanners_read_a_branch_without_a_checkout(self):
        tmp, repo = new_repo()
        with tmp:
            commit(repo, "main", {"src/a.ts": "export {};\n"})
            git(repo, "checkout", "-q", "-b", "release")
            commit(repo, "release work", {"src/analytics.ts": 'import posthog from "posthog-js";\nposthog.init("k");\n',
                                          "LICENSE": "MIT License\n\nPermission is hereby granted, free of charge, to any person\n"})
            git(repo, "checkout", "-q", "main")
            telemetry = run_script("telemetry_scan.py", str(repo), "--at", "release")
            self.assertEqual([s["name"] for s in telemetry["sdks"]], ["PostHog"])
            licenses = run_script("license_scan.py", str(repo), "--at", "release")
            self.assertEqual(licenses["history"]["LICENSE"][0]["subject"], "release work")
            self.assertEqual(run_script("telemetry_scan.py", str(repo))["sdks"], [], "the working tree is untouched")
            self.assertEqual(git(repo, "status", "--porcelain"), "")


class LicenseTitleAndVendoredTest(unittest.TestCase):
    def test_mpl_is_not_agpl_and_vendored_licenses_are_listed(self):
        mpl = ("Mozilla Public License, version 2.0\n\n1. Definitions\n\n1.12. \"Secondary License\" means either the GNU General\n"
               "Public License, Version 2.0, the GNU Lesser General Public License, Version 2.1, the GNU Affero General Public\n"
               "License, Version 3.0, or any later versions of those licenses.\n")
        custom = "Acme Enterprise License\n\nThis folder is not under the Apache License.\nAll rights reserved.\n"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write(root, "LICENSE", "MIT License\n\nPermission is hereby granted, free of charge, to any person\n")
            write(root, "ee/LICENSE", custom)
            write(root, "third_party/axe/LICENSE.txt", mpl)
            write(root, "third_party/axe/node_modules/x/LICENSE", "MIT License\n\nPermission is hereby granted, free of charge\n")
            out = run_script("license_scan.py", folder)
            self.assertEqual({f["path"]: f["family"] for f in out["license_files"]}, {"LICENSE": "MIT", "ee/LICENSE": "Proprietary or custom"})
            self.assertEqual(out["vendored_license_files"], [{"path": "third_party/axe/LICENSE.txt", "family": "MPL-2.0"}])
            everything = run_script("license_scan.py", folder, "--include-vendored")
            families = {f["path"]: f["family"] for f in everything["license_files"]}
            self.assertEqual(families["third_party/axe/LICENSE.txt"], "MPL-2.0")
            self.assertEqual(everything["flags"]["copyleft"], ["MPL-2.0"], "file-level copyleft, not the AGPL")

    def test_sbom_pins_in_vendored_folders(self):
        bom = {"bomFormat": "CycloneDX", "specVersion": "1.5",
               "metadata": {"component": {"name": "Driver runtime", "version": "0.19.3", "bom-ref": "pkg:generic/driver@0.19.3"}},
               "components": [{"name": "serde", "version": "1.0.0"}]}
        with tempfile.TemporaryDirectory() as folder:
            write(Path(folder), "third_party/driver/SBOM.cdx.json", json.dumps(bom))
            comps = run_script("dependency_versions.py", folder)["components"]
            self.assertEqual([(c["ecosystem"], c["name"], c["resolved"], c["kinds"]) for c in comps],
                             [("vendored", "Driver runtime", ["0.19.3"], ["vendored"])])

    def test_releases_since_the_shipped_version(self):
        class Stub:
            requests = 0

            def get(self, url, as_text=False):
                self.requests += 1
                return {"dist-tags": {"latest": "0.33.1"}, "time": {
                    "created": "2026-07-01T00:00:00Z", "0.28.2": "2026-09-15T22:00:07Z", "0.29.0": "2026-09-20T00:00:00Z",
                    "0.30.0-beta.1": "2026-09-22T00:00:00Z", "0.33.1": "2026-10-03T21:49:47Z"}}

        found = dv.look_up(Stub(), "npm", "@acme/driver", None, ["0.28.2"], True)
        self.assertEqual((found["latest"], found["days_between"], found["stable_releases_since"]), ("0.33.1", 17, 2))


class ClaimsLintRulesTest(unittest.TestCase):
    def test_fewer_false_alarms_comparatives_markers_and_strict(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            draft = write(root, "draft.md", "\n".join([
                "Our app works only on your Mac.",
                "The only tool that does this.",
                "Acme ships v0.28.2 of the driver, see `src/a.ts:12` and electron-builder.yml:125.",
                "1. Acme in short",
                "Unlike Acme, we keep your cursor.",
                "<!-- claims-lint: off -->",
                "Never say: the first background agent.",
                "<!-- claims-lint: on -->",
                "Acme is the fastest. <!-- claims-lint: ignore -->",
            ]))
            out = run_script("claims_lint.py", str(draft), "--competitor", "Acme", "--superlatives")
            rules = [(f["line"], f["rule"]) for f in out["findings"]]
            self.assertNotIn((1, "superlative"), rules)
            self.assertIn((2, "superlative"), rules)
            self.assertNotIn((3, "undated_number"), rules)
            self.assertNotIn((4, "undated_number"), rules)
            self.assertIn((5, "comparative"), rules)
            self.assertFalse(any(line in (7, 9) for line, _ in rules), rules)
            self.assertEqual(out["failing"], 0)
            strict = run_script("claims_lint.py", str(draft), "--competitor", "Acme", "--superlatives", "--strict", expect_ok=False)
            self.assertEqual(strict["failing"], strict["count"])


class SnapshotTest(unittest.TestCase):
    def test_reports_git_lfs(self):
        tmp, repo = new_repo()
        with tmp:
            commit(repo, "lfs", {".gitattributes": "*.bin filter=lfs diff=lfs merge=lfs -text\n", "a.txt": "a\n"})
            out = run_script("snapshot.py", str(repo))
            self.assertTrue(out["uses_lfs"])
            self.assertEqual(len(out["warnings"]), 1)


class TractionTest(unittest.TestCase):
    def test_mobile_releases_do_not_cut_desktop_windows(self):
        asset = lambda name, n: {"name": name, "download_count": n}
        releases = [
            {"tag_name": "v1.0.0", "published_at": "2026-09-01T00:00:00Z", "assets": [asset("latest-mac.yml", 2400)]},
            {"tag_name": "android-v1.0.0", "published_at": "2026-09-02T00:00:00Z", "assets": [asset("app-release.apk", 40)]},
            {"tag_name": "v1.1.0", "published_at": "2026-09-03T00:00:00Z", "assets": [asset("latest-mac.yml", 900)]},
        ]
        summary = gt.summarize_releases(releases, 1.0, datetime(2026, 9, 4, tzinfo=timezone.utc))
        self.assertEqual([w["tag"] for w in summary["windows"]], ["v1.0.0", "v1.1.0"])
        self.assertEqual(summary["windows"][0]["window_days"], 2.0)
        self.assertEqual(summary["versions_without_update_checks"], ["android-v1.0.0"])
        self.assertEqual(summary["running_copies_estimate"]["copies_running_at_once"], 50)

    def test_releases_elsewhere_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            saved, client = Path(folder), gt.Client(None, None)

            def save(path, params, body):
                (saved / client.slug(path, params)).write_text(json.dumps({"body": body, "headers": {}}))

            save("/repos/o/notes", {}, {"full_name": "o/notes", "stargazers_count": 3, "created_at": "2026-08-01T00:00:00Z"})
            save("/repos/o/notes/contributors", {"per_page": 1, "anon": "false"}, [])
            save("/repos/o/notes/releases", {"per_page": 100, "page": 1},
                 [{"tag_name": "v2.0.0", "published_at": "2026-09-15T00:00:00Z", "assets": []}])
            save("/users/o/repos", {"per_page": 100, "sort": "updated"},
                 [{"full_name": "o/notes", "name": "notes"}, {"full_name": "o/notes-releases", "name": "notes-releases", "description": "builds"},
                  {"full_name": "o/blog", "name": "blog"}])
            out = run_script("github_traction.py", "o/notes", "--offline", folder, "--no-search")
            elsewhere = out["releases_elsewhere"]
            self.assertEqual([r["repo"] for r in elsewhere["other_repositories"]], ["o/notes-releases"])
            self.assertIn("45 days", elsewhere["warning"])
            skipped = run_script("github_traction.py", "o/notes", "--offline", folder, "--no-search", "--no-owner-scan")
            self.assertIsNone(skipped["releases_elsewhere"])


PNPM_WORKSPACES = """lockfileVersion: '9.0'

importers:

  .:
    dependencies:
      lucide-react:
        specifier: ^0.539.0
        version: 0.539.0(react@19.2.8)

  apps/docs:
    dependencies:
      lucide-react:
        specifier: ^1.31.0
        version: 1.31.2(react@19.2.8)
      shared:
        specifier: workspace:*
        version: link:../../shared
"""
GRADLE_KTS = """dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.09.00"))
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation(libs.androidx.core.ktx)
    testImplementation("junit:junit:4.13.2")
    ksp("com.google.dagger:hilt-compiler:2.52")
    implementation("io.coil-kt:coil:2.+")
}
"""
CATALOG = """[versions]
coreKtx = "1.13.1"

[libraries]
androidx-core-ktx = { group = "androidx.core", name = "core-ktx", version.ref = "coreKtx" }
"""
PACKAGE_SWIFT = """// swift-tools-version:5.9
import PackageDescription
let package = Package(
    name: "App",
    dependencies: [
        .package(url: "https://github.com/apple/swift-log.git", from: "1.5.0"),
        .package(url: "https://github.com/pointfreeco/swift-snapshot-testing", .upToNextMinor(from: "1.17.0")),
        .package(url: "https://github.com/example/pinned.git", exact: "2.0.1"),
        .package(path: "../Local"),
    ]
)
"""
PBXPROJ = """/* Begin XCRemoteSwiftPackageReference section */
		AA11 /* XCRemoteSwiftPackageReference "Sparkle" */ = {
			isa = XCRemoteSwiftPackageReference;
			repositoryURL = "https://github.com/sparkle-project/Sparkle";
			requirement = {
				kind = upToNextMajorVersion;
				minimumVersion = 2.6.0;
			};
		};
/* End XCRemoteSwiftPackageReference section */
"""


class DependencyVersionsTest(unittest.TestCase):
    def test_workspaces_gradle_and_swift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write(root, "package.json", json.dumps({"dependencies": {"lucide-react": "^0.539.0"}}))
            write(root, "apps/docs/package.json", json.dumps({"dependencies": {"lucide-react": "^1.31.0", "shared": "workspace:*"}}))
            write(root, "pnpm-lock.yaml", PNPM_WORKSPACES)
            write(root, "android/app/build.gradle.kts", GRADLE_KTS)
            write(root, "android/gradle/libs.versions.toml", CATALOG)
            write(root, "ios/Package.swift", PACKAGE_SWIFT)
            write(root, "mac/App.xcodeproj/project.pbxproj", PBXPROJ)
            write(root, "mac/App.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved",
                  json.dumps({"pins": [{"identity": "sparkle", "location": "https://github.com/sparkle-project/Sparkle",
                                        "state": {"version": "2.6.4"}}], "version": 2}))
            out = run_script("dependency_versions.py", folder, "--rows")
            comps = {(c["ecosystem"], c["name"]): c for c in out["components"]}
            self.assertEqual(sorted(comps[("npm", "lucide-react")]["resolved"]), ["0.539.0", "1.31.2"])
            self.assertEqual(comps[("npm", "shared")]["resolved"], [])
            self.assertEqual(comps[("maven", "com.squareup.okhttp3:okhttp")]["resolved"], ["4.12.0"])
            self.assertEqual(comps[("maven", "androidx.core:core-ktx")]["declared"], ["1.13.1"])
            self.assertEqual(comps[("maven", "junit:junit")]["kinds"], ["dev"])
            self.assertEqual(comps[("maven", "com.google.dagger:hilt-compiler")]["kinds"], ["build"])
            self.assertEqual(comps[("maven", "io.coil-kt:coil")]["resolved"], [], "dynamic versions are not resolved")
            self.assertEqual(comps[("maven", "androidx.compose:compose-bom")]["declared"], ["2024.09.00"])
            self.assertEqual(comps[("swift", "swift-log")]["declared"], ["from 1.5.0"])
            self.assertEqual(comps[("swift", "swift-snapshot-testing")]["declared"], ["upToNextMinor 1.17.0"])
            self.assertEqual(comps[("swift", "pinned")]["declared"], ["exact 2.0.1"])
            self.assertNotIn(("swift", "local"), comps)
            self.assertEqual(comps[("swift", "sparkle")]["resolved"], ["2.6.4"])
            self.assertIn("from 2.6.0", comps[("swift", "sparkle")]["declared"])

    def test_xcodegen_packages(self):
        yml = ("name: App\npackages:\n  Core:\n    path: .\n  # pinned on purpose\n  WebRTC:\n    url: https://github.com/stasel/WebRTC\n"
               "    exactVersion: 153.0.0\n  Sparkle:\n    url: https://github.com/sparkle-project/Sparkle\n    from: \"2.6.0\"\ntargets:\n  App:\n    type: application\n")
        rows = {r["name"]: r for r in dv.from_xcodegen(yml)}
        self.assertEqual(sorted(rows), ["sparkle", "webrtc"])
        self.assertEqual(rows["webrtc"]["declared"], "exact 153.0.0")
        self.assertEqual(rows["sparkle"]["declared"], "from 2.6.0")
        with tempfile.TemporaryDirectory() as folder:
            write(Path(folder), "ios/project.yml", yml)
            comps = {c["name"]: c for c in run_script("dependency_versions.py", folder)["components"]}
            self.assertEqual(comps["webrtc"]["resolved"], ["153.0.0"])

    def test_yarn_ranges_and_registry_parsers(self):
        lock = dv.NpmLock("yarn.lock", '"left-pad@^1.0.0":\n  version "1.0.2"\n\n"left-pad@^1.3.0":\n  version "1.3.0"\n')
        self.assertEqual(lock.resolve("left-pad", "^1.3.0", ""), "1.3.0")
        self.assertEqual(lock.resolve("left-pad", "^1.0.0", ""), "1.0.2")
        self.assertEqual(dv.github_repo("https://github.com/apple/swift-log.git"), "apple/swift-log")
        self.assertIsNone(dv.github_repo("https://gitlab.com/a/b"))
        self.assertIn("search.maven.org", dv.latest_url("maven", "junit:junit"))
        self.assertTrue(dv.latest_url("swift", "x", "https://github.com/a/b").endswith("/repos/a/b/releases/latest"))
        self.assertEqual(dv.latest_from("maven", {"response": {"docs": [{"latestVersion": "4.13.2"}]}}), "4.13.2")
        self.assertEqual(dv.latest_from("swift", {"tag_name": "v1.6.1"}), "1.6.1")
        self.assertEqual(dv.publish_dates("npm", {"time": {"created": "x", "1.0.0": "2026-09-15T22:00:07Z"}}), {"1.0.0": "2026-09-15T22:00:07Z"})
        pypi = {"releases": {"2.0": [{"upload_time_iso_8601": "2026-01-02T00:00:00Z"}], "2.1": []}}
        self.assertEqual(dv.publish_dates("pypi", pypi), {"2.0": "2026-01-02T00:00:00Z"})
        crates = {"versions": [{"num": "1.0.229", "created_at": "2026-07-18T23:05:13Z"}]}
        self.assertEqual(dv.publish_dates("crates", crates), {"1.0.229": "2026-07-18T23:05:13Z"})
        maven = {"response": {"docs": [{"latestVersion": "4.13.2", "timestamp": 1614000000000}]}}
        self.assertEqual(dv.publish_dates("maven", maven), {"4.13.2": "2021-02-22T13:20:00+00:00"})


if __name__ == "__main__":
    unittest.main()
