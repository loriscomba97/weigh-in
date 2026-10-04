#!/usr/bin/env python3
"""Build "Acme Notes", a fictional competitor, as a small git repository with planted signals, so you
can try the skill's scripts in a minute, with no network and no accounts.

Usage:
  python3 docs/example/make_acme.py /tmp/acme                      # the repository
  python3 docs/example/make_acme.py /tmp/acme --raw /tmp/acme-raw  # plus saved GitHub API responses

What is planted, so you know what the scripts should find:
  - an open core: the root license changes from Apache-2.0 to MIT after a CLA arrives, a sync
    server under the AGPL and an enterprise folder under custom terms;
  - PostHog started at launch with no consent check and an identify call, while the README says
    "no tracking", and Sentry named only in an integration catalog;
  - an Electron window with context isolation off, no fuses, risky macOS entitlements, and a sync
    server that listens on every network interface;
  - Electron pinned at an old major version in the lockfile;
  - three people over ten weeks (one with two emails), fix commits, three version tags and one
    commit with an assistant co-author trailer;
  - with --raw: repository facts and three releases whose downloads are mostly update checks, for
    `github_traction.py --offline`.

Everything is fictional: the names, numbers and dates are made up for the example.
Standard library only, Python 3.9 or later.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "skills" / "competitor-analysis" / "scripts"
sys.path.insert(0, str(SCRIPTS))

PEOPLE = {
    "dana": ("Dana Reyes", "dana@example.com"),
    "dana2": ("Dana Reyes", "dana.reyes@example.org"),
    "sam": ("Sam Okafor", "sam@example.com"),
    "ivy": ("Ivy Chen", "ivy@example.net"),
}

APACHE = "Apache License\nVersion 2.0, January 2004\nhttp://www.apache.org/licenses/\n\nCopyright 2026 Acme Labs\n"
MIT = ("MIT License\n\nCopyright (c) 2026 Acme Labs\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\n"
       "of this software, to deal in the Software without restriction, subject to the following conditions.\n")
AGPL = "GNU AFFERO GENERAL PUBLIC LICENSE\nVersion 3, 19 November 2007\n\nCopyright (C) 2026 Acme Labs\n"
ENTERPRISE = ("Acme Enterprise License\n\nCopyright (c) 2026 Acme Labs. All rights reserved.\n\n"
              "Production use of the files in this folder requires a valid Acme Enterprise license key.\n")

ENTITLEMENTS = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.cs.allow-unsigned-executable-memory</key><true/>
  <key>com.apple.security.cs.disable-library-validation</key><true/>
  <key>com.apple.security.device.audio-input</key><true/>
</dict>
</plist>
"""


def git(repo: Path, *args: str, env: dict = None) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True, env=env).stdout


def commit(repo: Path, who: str, date: str, message: str, files: dict) -> None:
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    name, email = PEOPLE[who]
    stamp = f"{date}T10:00:00+00:00"
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
           "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email,
           "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
    git(repo, "commit", "-q", "-m", message, env=env)


def package_json(electron: str) -> str:
    return json.dumps({
        "name": "acme-notes", "version": "1.0.0", "license": "MIT", "main": "electron/main.js",
        "dependencies": {"posthog-js": "^1.200.0", "electron-updater": "^6.3.0"},
        "devDependencies": {"electron": f"^{electron}", "electron-builder": "^25.1.0"},
    }, indent=2) + "\n"


def build(repo: Path) -> None:
    if repo.exists():
        sys.exit(f"{repo} already exists; pick a new folder")
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    signals = json.loads((SCRIPTS / "ai_signals.json").read_text(encoding="utf-8"))
    trailer = f"{signals['trailer_keys'][0]}: {signals['assistants'][0]['example']}"

    commit(repo, "dana", "2026-06-01", "Initial commit", {
        "LICENSE": APACHE,
        "README.md": "# Acme Notes\n\nPrivate notes that sync between your devices. No tracking, ever.\n",
        "package.json": package_json("37.2.0"),
        "electron/main.js": (
            'const { app, BrowserWindow } = require("electron");\n'
            'const { autoUpdater } = require("electron-updater");\n\n'
            "function createWindow() {\n"
            "  const win = new BrowserWindow({ width: 1200, height: 800, webPreferences: { contextIsolation: false, nodeIntegration: true } });\n"
            '  win.loadFile("index.html");\n}\n\n'
            "app.whenReady().then(() => {\n  createWindow();\n  autoUpdater.checkForUpdatesAndNotify();\n"
            "  // check again every four hours\n"
            "  setInterval(() => autoUpdater.checkForUpdatesAndNotify(), 4 * 60 * 60 * 1000);\n});\n"),
        "src/index.ts": 'import { defaults } from "./settings";\n\nexport function start() {\n  return defaults;\n}\n',
        "src/settings.ts": 'export const defaults = { theme: "system", telemetryEnabled: true };\n',
    })
    commit(repo, "dana2", "2026-06-03", "Add the note editor", {
        "src/editor.ts": "export function wordCount(text: string): number {\n  return text.split(/\\s+/).filter(Boolean).length;\n}\n",
    })
    commit(repo, "sam", "2026-06-08", "Add the sync server", {
        "sync-server/LICENSE": AGPL,
        "sync-server/server.ts": 'import http from "node:http";\n\nhttp.createServer((req, res) => res.end("ok")).listen(8787, "0.0.0.0");\n',
    })
    commit(repo, "sam", "2026-06-10", "fix: crash when the sync server is offline", {
        "sync-server/server.ts": 'import http from "node:http";\n\n// retry instead of crashing\nhttp.createServer((req, res) => res.end("ok")).listen(8787, "0.0.0.0");\n',
    })
    commit(repo, "dana", "2026-06-15", "Add product analytics", {
        "src/analytics.ts": (
            'import posthog from "posthog-js";\n\n'
            "export function startAnalytics(userId: string) {\n"
            '  posthog.init("phc_example_project", { api_host: "https://us.i.posthog.com" });\n'
            "  posthog.identify(userId);\n}\n"),
        "src/index.ts": ('import { defaults } from "./settings";\nimport { startAnalytics } from "./analytics";\n\n'
                         "export function start(userId: string) {\n  startAnalytics(userId);\n  return defaults;\n}\n"),
    })
    git(repo, "tag", "v0.1.0")
    commit(repo, "ivy", "2026-06-22", "Add the integrations catalog", {
        "src/integrations/catalog.ts": (
            "export const catalog = [\n"
            '  { slug: "github", label: "GitHub", domain: "github.com" },\n'
            '  { slug: "sentry", label: "Sentry", domain: "sentry.io" },\n];\n'),
    })
    commit(repo, "dana", "2026-06-29", "fix: lost edits on quit", {
        "src/editor.ts": ("export function wordCount(text: string): number {\n  return text.split(/\\s+/).filter(Boolean).length;\n}\n\n"
                          "export function flush(): void {}\n"),
    })
    commit(repo, "ivy", "2026-07-06", "Add tests for the editor and the sync server", {
        "tests/editor.test.ts": 'import { wordCount } from "../src/editor";\n\ntest("counts words", () => expect(wordCount("a b")).toBe(2));\n',
        "tests/sync.test.ts": 'test("server answers", () => expect(true).toBe(true));\n',
    })
    git(repo, "tag", "v0.2.0")
    commit(repo, "dana", "2026-07-13", f"Add enterprise license checks\n\n{trailer}", {
        "ee/LICENSE": ENTERPRISE,
        "ee/licensing.ts": "export function hasValidKey(key: string): boolean {\n  return key.startsWith(\"acme-ent-\");\n}\n",
    })
    commit(repo, "sam", "2026-07-20", "fix: sync conflict when a note is renamed", {
        "sync-server/conflicts.ts": "export function resolve(a: string, b: string): string {\n  return a > b ? a : b;\n}\n",
    })
    commit(repo, "dana", "2026-07-27", "Add macOS signing settings and the lockfile", {
        "build/entitlements.mac.plist": ENTITLEMENTS,
        "package-lock.json": json.dumps({"name": "acme-notes", "lockfileVersion": 3, "packages": {
            "": {"name": "acme-notes"},
            "node_modules/posthog-js": {"version": "1.200.3"},
            "node_modules/electron-updater": {"version": "6.3.9"},
            "node_modules/electron": {"version": "37.2.0"},
            "node_modules/electron-builder": {"version": "25.1.8"},
        }}, indent=2) + "\n",
    })
    commit(repo, "dana", "2026-08-03", "Require a CLA for contributions", {
        "CONTRIBUTING.md": ("# Contributing\n\nBefore we can merge your pull request, you must sign the Acme "
                            "Contributor License Agreement (CLA). It lets Acme Labs license your contribution under other terms.\n"),
    })
    commit(repo, "dana", "2026-08-10", "Relicense the core from Apache-2.0 to MIT", {"LICENSE": MIT})
    git(repo, "tag", "v1.0.0")


def raw_responses(folder: Path) -> None:
    """GitHub API responses, as github_traction.py --save writes them, for --offline runs."""
    import github_traction as gt
    folder.mkdir(parents=True, exist_ok=True)
    client = gt.Client(None, None)

    def save(path, params, body, headers=None):
        (folder / client.slug(path, params)).write_text(json.dumps({"body": body, "headers": headers or {}}, indent=1), encoding="utf-8")

    def asset(name, count):
        return {"name": name, "download_count": count}

    save("/repos/acme/acme-notes", {}, {
        "full_name": "acme/acme-notes", "description": "Private notes that sync", "stargazers_count": 1234,
        "forks_count": 87, "subscribers_count": 21, "open_issues_count": 64, "default_branch": "main",
        "license": {"spdx_id": "MIT"}, "created_at": "2026-06-01T09:00:00Z", "pushed_at": "2026-08-10T09:00:00Z",
        "archived": False, "topics": ["notes", "electron"], "homepage": "https://acme.example.com"})
    save("/repos/acme/acme-notes/contributors", {"per_page": 1, "anon": "false"}, [{"login": "dana"}],
         {"Link": '<https://api.github.com/repositories/1/contributors?per_page=1&anon=false&page=2>; rel="next", '
                  '<https://api.github.com/repositories/1/contributors?per_page=1&anon=false&page=3>; rel="last"'})
    save("/repos/acme/acme-notes/releases", {"per_page": 100, "page": 1}, [
        {"tag_name": "v1.0.0", "published_at": "2026-08-10T12:00:00Z", "assets": [
            asset("Acme-1.0.0-arm64.dmg", 310), asset("Acme-Setup-1.0.0.exe", 190), asset("Acme-1.0.0-arm64.dmg.blockmap", 2100),
            asset("latest-mac.yml", 41200), asset("latest.yml", 18900)]},
        {"tag_name": "v0.2.0", "published_at": "2026-07-06T12:00:00Z", "assets": [
            asset("Acme-0.2.0-arm64.dmg", 420), asset("Acme-Setup-0.2.0.exe", 260), asset("latest-mac.yml", 52300), asset("latest.yml", 24800)]},
        {"tag_name": "v0.1.0", "published_at": "2026-06-15T12:00:00Z", "assets": [
            asset("Acme-0.1.0-arm64.dmg", 980), asset("Acme-Setup-0.1.0.exe", 540), asset("latest-mac.yml", 20100), asset("latest.yml", 9700)]},
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dest", type=Path, help="folder for the repository; must not exist yet")
    parser.add_argument("--raw", type=Path, help="folder for saved GitHub API responses")
    args = parser.parse_args()
    build(args.dest)
    if args.raw:
        raw_responses(args.raw)
    print(f"Acme Notes is ready in {args.dest}" + (f", with API responses in {args.raw}" if args.raw else "") + ".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
