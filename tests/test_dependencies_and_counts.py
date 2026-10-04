"""Tests for dependency_versions, public_counts and the star history in github_traction.
Nothing here touches the network: lookups are tested through their parsers and saved responses."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from helpers import run_script, write

import dependency_versions as dv
import github_traction as gt
import public_counts as pc

PNPM_LOCK = """lockfileVersion: '9.0'

importers:

  .:
    dependencies:
      react:
        specifier: ^19.1.0
        version: 19.2.8(react-dom@19.2.8)
    devDependencies:
      electron:
        specifier: ^43.4.0
        version: 43.4.0

packages:

  react@19.2.8:
    resolution: {integrity: sha512-x}
"""
YARN_LOCK = '''# yarn lockfile v1

"left-pad@^1.3.0":
  version "1.3.0"
  resolved "https://registry.example.com/left-pad-1.3.0.tgz"

"@scope/tool@^2.0.0", "@scope/tool@^2.1.0":
  version "2.1.4"
'''
PYPROJECT = """[project]
name = "app"
dependencies = [
  "httpx>=0.27",
  "pydantic[email]==2.9.0 ; python_version >= '3.9'",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[tool.poetry.dependencies]
python = "^3.10"
rich = { version = "^13.0", optional = true }
"""
POETRY_LOCK = """[[package]]
name = "httpx"
version = "0.27.2"

[[package]]
name = "pydantic"
version = "2.9.0"
"""
CARGO_TOML = """[package]
name = "core"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
anyhow = "1"
local = { path = "../local" }
tokio.workspace = true

[dependencies.reqwest]
version = "0.12"
default-features = false

[dev-dependencies]
insta = "1.40"
"""
CARGO_LOCK = """[[package]]
name = "serde"
version = "1.0.210"

[[package]]
name = "anyhow"
version = "1.0.89"
"""
GO_MOD = """module example.com/app

go 1.23

require github.com/BurntSushi/toml v1.4.0

require (
\tgolang.org/x/sys v0.25.0 // indirect
\tgithub.com/spf13/cobra v1.8.1
)
"""


class DependencyVersionsTest(unittest.TestCase):
    def build(self, root: Path) -> None:
        write(root, "package.json", json.dumps({"dependencies": {"react": "^19.1.0"}, "devDependencies": {"electron": "^43.4.0"}}))
        write(root, "pnpm-lock.yaml", PNPM_LOCK)
        write(root, "web/package.json", json.dumps({"dependencies": {"left-pad": "^1.3.0", "@scope/tool": "^2.1.0"}}))
        write(root, "web/yarn.lock", YARN_LOCK)
        write(root, "old/package.json", json.dumps({"dependencies": {"lodash": "^4.17.0"}}))
        write(root, "old/package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {
            "": {"name": "old"}, "node_modules/lodash": {"version": "4.17.21"},
            "node_modules/a/node_modules/lodash": {"version": "3.0.0"}}}))
        write(root, "py/pyproject.toml", PYPROJECT)
        write(root, "py/poetry.lock", POETRY_LOCK)
        write(root, "py/requirements-dev.txt", "ruff==0.6.0\n-r base.txt\n")
        write(root, "rs/Cargo.toml", CARGO_TOML)
        write(root, "rs/Cargo.lock", CARGO_LOCK)
        write(root, "go/go.mod", GO_MOD)
        write(root, "ios/Package.resolved", json.dumps({"pins": [{"identity": "swift-log", "location": "https://example.com/swift-log.git",
                                                                  "state": {"version": "1.6.1"}}], "version": 2}))
        write(root, "ios/Podfile.lock", "PODS:\n  - Alamofire (5.9.1)\n\nDEPENDENCIES:\n  - Alamofire\n")
        write(root, "node_modules/x/package.json", json.dumps({"dependencies": {"never": "1"}}))

    def test_declared_and_resolved_across_ecosystems(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.build(root)
            out = run_script("dependency_versions.py", folder)
            comps = {(c["ecosystem"], c["name"]): c for c in out["components"]}
            self.assertEqual(comps[("npm", "react")]["resolved"], ["19.2.8"])
            self.assertEqual(comps[("npm", "electron")]["kinds"], ["dev"])
            self.assertEqual(comps[("npm", "electron")]["resolved"], ["43.4.0"])
            self.assertEqual(comps[("npm", "left-pad")]["resolved"], ["1.3.0"])
            self.assertEqual(comps[("npm", "@scope/tool")]["resolved"], ["2.1.4"])
            self.assertEqual(comps[("npm", "lodash")]["resolved"], ["4.17.21"])
            self.assertNotIn(("npm", "never"), comps, "dependency folders are skipped")
            self.assertEqual(comps[("pypi", "httpx")]["resolved"], ["0.27.2"])
            self.assertEqual(comps[("pypi", "pydantic")]["declared"], ["==2.9.0"])
            self.assertEqual(comps[("pypi", "pytest")]["kinds"], ["dev"])
            self.assertEqual(comps[("pypi", "rich")]["declared"], ["^13.0"])
            self.assertEqual(comps[("pypi", "ruff")]["kinds"], ["dev"])
            self.assertNotIn(("pypi", "python"), comps)
            self.assertEqual(comps[("crates", "serde")]["resolved"], ["1.0.210"])
            self.assertEqual(comps[("crates", "local")]["declared"], ["path"])
            self.assertEqual(comps[("crates", "tokio")]["declared"], ["workspace"])
            self.assertEqual(comps[("crates", "reqwest")]["declared"], ["0.12"])
            self.assertEqual(comps[("crates", "insta")]["kinds"], ["dev"])
            self.assertEqual(comps[("go", "github.com/BurntSushi/toml")]["resolved"], ["v1.4.0"])
            self.assertEqual(comps[("go", "golang.org/x/sys")]["kinds"], ["indirect"])
            self.assertEqual(comps[("swift", "swift-log")]["resolved"], ["1.6.1"])
            self.assertEqual(comps[("cocoapods", "Alamofire")]["resolved"], ["5.9.1"])
            prod = run_script("dependency_versions.py", folder, "--prod-only", "--only", "electron", "react", "golang.org/*")
            self.assertEqual([c["name"] for c in prod["components"]], ["react"])

    def test_behind_and_registry_helpers(self):
        self.assertEqual(dv.behind("43.4.0", "44.5.1"), "major")
        self.assertEqual(dv.behind("19.2.8", "19.3.0"), "minor")
        self.assertEqual(dv.behind("v1.4.0", "v1.4.2"), "patch")
        self.assertEqual(dv.behind("2.0.0", "2.0.0"), "current")
        self.assertEqual(dv.behind("3.0.0", "2.9.0"), "ahead")
        self.assertEqual(dv.behind("workspace", "1.0.0"), "unknown")
        self.assertEqual(dv.go_escape("github.com/BurntSushi/toml"), "github.com/!burnt!sushi/toml")
        self.assertTrue(dv.latest_url("npm", "@scope/tool").endswith("/-/package/@scope%2Ftool/dist-tags"))
        self.assertIsNone(dv.latest_url("swift", "swift-log"))
        self.assertEqual(dv.latest_from("npm", {"latest": "1.2.3"}), "1.2.3")
        self.assertEqual(dv.latest_from("pypi", {"info": {"version": "2.0"}}), "2.0")
        self.assertEqual(dv.latest_from("crates", {"crate": {"max_stable_version": "1.0.229"}}), "1.0.229")
        self.assertEqual(dv.latest_from("go", {"Version": "v1.6.0"}), "v1.6.0")


class PublicCountsTest(unittest.TestCase):
    def test_summaries_for_each_source(self):
        npm = [{"downloads": 1}, {"downloads": 7}, {"downloads": 30, "end": "2026-10-01"}]
        self.assertEqual(pc.summarize("npm", "x", npm)["downloads_last_month"], 30)
        self.assertEqual(pc.summarize("pypi", "x", [{"data": {"last_day": 2, "last_week": 9, "last_month": 40}}])["downloads_last_week"], 9)
        self.assertEqual(pc.summarize("crate", "x", [{"crate": {"downloads": 100, "recent_downloads": 10}}])["downloads_last_90_days"], 10)
        brew = [{"analytics": {"install": {"30d": {"git": 5, "git --HEAD": 1}, "90d": {"git": 9}, "365d": {}}}}]
        self.assertEqual(pc.summarize("brew", "git", brew), {"installs_30d": 5, "installs_90d": 9, "installs_365d": None})
        self.assertEqual(pc.summarize("docker", "a/b", [{"pull_count": 3, "star_count": 1}])["pulls_all_time"], 3)
        self.assertEqual(pc.summarize("open_vsx", "a/b", [{"downloadCount": 4}])["downloads_all_time"], 4)
        discord = [{"guild": {"name": "Example"}, "approximate_member_count": 120, "approximate_presence_count": 15}]
        self.assertEqual(pc.summarize("discord", "abc", discord)["members_approximate"], 120)
        self.assertEqual(pc.summarize("npm", "x", [{"_error": "HTTP 404"}] * 3), {"error": "HTTP 404"})

    def test_offline_run_and_name_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            url = "https://discord.com/api/v10/invites/abc?with_counts=true"
            Path(folder, pc.slug(url)).write_text(json.dumps({"body": {"approximate_member_count": 5}}))
            out = run_script("public_counts.py", "--discord", "https://discord.gg/abc", "--npm", "bad name", "--offline", folder)
            results = {r["source"]: r for r in out["results"]}
            self.assertEqual(results["discord"]["members_approximate"], 5)
            self.assertEqual(results["npm"]["error"], "unexpected name format")
            self.assertEqual(out["requests"], 0)


class StarHistoryTest(unittest.TestCase):
    def test_sampling_and_pace(self):
        self.assertEqual(gt.sample_pages(41, 5), [1, 11, 21, 31, 41])
        self.assertEqual(gt.sample_pages(1, 12), [1])
        self.assertEqual(gt.sample_pages(3, 12), [1, 2, 3])
        pace = gt.star_pace([{"star": 1, "starred_at": "2026-01-01T00:00:00Z"}, {"star": 101, "starred_at": "2026-01-11T00:00:00Z"}])
        self.assertEqual(pace[0]["stars_per_day"], 10.0)

    def test_offline_star_history(self):
        with tempfile.TemporaryDirectory() as folder:
            saved, client = Path(folder), gt.Client(None, None)

            def save(path, params, body):
                (saved / client.slug(path, params)).write_text(json.dumps({"body": body, "headers": {}}))

            save("/repos/o/r", {}, {"full_name": "o/r", "stargazers_count": 250})
            save("/repos/o/r/contributors", {"per_page": 1, "anon": "false"}, [])
            save("/repos/o/r/releases", {"per_page": 100, "page": 1}, [])
            for page, day in ((1, "01"), (2, "11")):
                save("/repos/o/r/stargazers", {"per_page": 100, "page": page}, [{"starred_at": f"2026-03-{day}T00:00:00Z"}] * 100)
            save("/repos/o/r/stargazers", {"per_page": 100, "page": 3}, [{"starred_at": "2026-03-21T00:00:00Z"}] * 50)
            out = run_script("github_traction.py", "o/r", "--offline", folder, "--no-search", "--star-history", "3")
            stars = [m["star"] for m in out["star_history"]["milestones"]]
            self.assertEqual(stars, [1, 101, 201, 250])
            self.assertEqual(out["star_history"]["pace"][0]["stars_per_day"], 10.0)


if __name__ == "__main__":
    unittest.main()
