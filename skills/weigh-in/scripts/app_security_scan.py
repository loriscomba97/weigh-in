#!/usr/bin/env python3
"""Hardening signals for desktop, mobile and web apps: entitlements, signing, updates, web
security settings and secrets committed by mistake.

Usage:
  python3 app_security_scan.py <repo> [--at REV] [--include-tests]

Reads files only. Prints JSON with signals grouped by area, each with file and line:
  - macOS: entitlements and the risky ones (library validation off, dyld variables allowed,
    unsigned executable memory, JIT, get-task-allow), app sandbox, hardened runtime in Xcode
    projects, Sparkle update keys;
  - Electron: fuses, BrowserWindow web preferences (nodeIntegration, contextIsolation, sandbox,
    webSecurity), electron-builder signing, notarization and update-signature settings;
  - Tauri: updater public key, content security policy;
  - Android and iOS: cleartext traffic, debuggable builds, App Transport Security exceptions,
    privacy manifests;
  - web: Content-Security-Policy, permissive CORS, and servers bound to every network interface
    (0.0.0.0), which other machines on the network can reach;
  - secrets: tokens and keys that look real, shown masked, and files that should never be
    committed.
A signal is a lead, not a finding: read the configuration in context (a debug-only setting is not
a shipped one) before you report it. Never print a secret's value.
"""
from __future__ import annotations

import argparse
import plistlib
import re
import sys
from collections import defaultdict
from pathlib import Path

from common import SKIP_DIRS, is_test_path, iter_files, mask, print_json, read_text, rel, tree_at

RISKY_ENTITLEMENTS = {
    "com.apple.security.cs.disable-library-validation": "loads code not signed by the same team; with TCC grants, other code can ride the app's permissions",
    "com.apple.security.cs.allow-dyld-environment-variables": "DYLD_* variables can inject libraries at launch",
    "com.apple.security.cs.allow-unsigned-executable-memory": "writable and executable memory without signing",
    "com.apple.security.cs.disable-executable-page-protection": "turns off executable page protection",
    "com.apple.security.cs.allow-jit": "JIT memory; normal for JavaScript engines, note it",
    "com.apple.security.get-task-allow": "debuggable build; must not ship",
}
TCC_HINTS = ("com.apple.security.device.audio-input", "com.apple.security.device.camera", "com.apple.security.personal-information")
SECRET_RULES = [
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("Stripe secret key", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{10,}\b")),
    ("OpenAI-style secret key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b")),
    ("Private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]
FORBIDDEN_FILE = re.compile(r"(^|/)(\.env(?!\.example$|\.sample$|\.template$)[^/]*|[^/]*\.(pem|key|p12|pfx|keystore|jks)|id_(rsa|ecdsa|ed25519)[^/]*|[^/]*service[-_]?account[^/]*\.json)$", re.I)
EXAMPLE_DIRS = re.compile(r"(^|/)(examples?|samples?|demos?)(/|$)", re.I)
# Electron and Xcode projects keep signing resources (entitlements, icons) in build/ and release/,
# so this scan reads them; the other skipped folders still hold dependencies or output.
SCAN_SKIP = SKIP_DIRS - {"build", "release", "releases"}
LOCKFILES = {"package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "Cargo.lock", "poetry.lock", "uv.lock", "Package.resolved", "Podfile.lock", "go.sum"}

# electron-builder settings with generic names (publisherName) count only in its configuration files.
BUILDER_CONFIG = re.compile(r"(^|/)(electron-builder(\.[\w-]+)?\.(ya?ml|json|js|cjs|mjs|ts|toml)|package\.json)$")
LINE_RULES = [
    ("electron", "nodeIntegration enabled", re.compile(r"nodeIntegration\s*:\s*true")),
    ("electron", "contextIsolation disabled", re.compile(r"contextIsolation\s*:\s*false")),
    ("electron", "renderer sandbox disabled", re.compile(r"\bsandbox\s*:\s*false")),
    ("electron", "webSecurity disabled", re.compile(r"webSecurity\s*:\s*false")),
    ("electron", "fuses configured", re.compile(r"@electron/fuses|flipFuses|FuseV1Options")),
    ("electron", "hardened runtime setting", re.compile(r"hardenedRuntime\s*[:=]\s*(true|false)")),
    ("electron", "notarization setting", re.compile(r"\bnotarize\s*[:=]")),
    ("electron", "Windows signing settings", re.compile(r"\b(certificateFile|signtoolOptions|azureSignOptions|certificateSubjectName)\b")),
    ("electron", "update signature check setting", re.compile(r"\b(verifyUpdateCodeSignature|publisherName)\b"), BUILDER_CONFIG),
    ("macos", "hardened runtime in Xcode project", re.compile(r"ENABLE_HARDENED_RUNTIME\s*=\s*(YES|NO)")),
    ("macos", "entitlements file in Xcode project", re.compile(r"CODE_SIGN_ENTITLEMENTS\s*=")),
    ("macos", "app sandbox in Xcode project", re.compile(r"ENABLE_APP_SANDBOX\s*=\s*(YES|NO)")),
    ("macos", "Sparkle update feed", re.compile(r"SUFeedURL")),
    ("macos", "Sparkle EdDSA public key", re.compile(r"SUPublicEDKey")),
    ("macos", "notarization step (notarytool or stapler)", re.compile(r"\bnotarytool\s+submit\b|\bstapler\s+staple\b|\baltool\b.*--notarize")),
    ("tauri", "updater public key", re.compile(r'"pubkey"\s*:')),
    ("tauri", "content security policy disabled", re.compile(r'"csp"\s*:\s*null')),
    ("android", "cleartext traffic allowed", re.compile(r'usesCleartextTraffic\s*=\s*"true"|cleartextTrafficPermitted\s*=\s*"true"')),
    ("android", "debuggable build", re.compile(r'android:debuggable\s*=\s*"true"')),
    ("ios", "App Transport Security exception", re.compile(r"NSAllowsArbitraryLoads")),
    ("web", "Content-Security-Policy set", re.compile(r"Content-Security-Policy", re.I)),
    ("web", "permissive CORS", re.compile(r"Access-Control-Allow-Origin['\"]?\s*[:,=]\s*['\"]\*['\"]", re.I)),
    ("web", "server bound to every network interface", re.compile(r"""(listen|bind|serve|run)\w*\(.*['"]0\.0\.0\.0['"]|\bhost\w*['"]?\s*[:=]\s*['"]0\.0\.0\.0['"]|\[::\]:\d+""", re.I)),
]
LINE_SUFFIXES = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".json", ".yml", ".yaml", ".pbxproj", ".plist", ".xml",
                 ".toml", ".conf", ".rs", ".go", ".py", ".rb", ".php", ".swift", ".kt", ".java", ".html", ".config"}


def looks_like_placeholder(value: str, line: str) -> bool:
    """Documentation keys, redaction markers and test values are not leaks."""
    core = re.sub(r"^(gh[pousr]_|github_pat_|AKIA|AIza|xox[abprs]-|(sk|rk)_live_|sk-(proj-)?)", "", value)
    if "PRIVATE KEY" in value:
        return bool(re.search(r"example|dummy|fake|test", line, re.I))
    return len(set(core)) <= 6 or bool(re.search(r"example|redact|dummy|fake|placeholder|xxxx|0000|your[_-]?key", value + " " + line, re.I))


def entitlements(path: Path, relative: str, out: dict) -> None:
    try:
        data = plistlib.loads(path.read_bytes())
    except Exception:
        out["macos"].append({"file": relative, "signal": "entitlements file could not be parsed"})
        return
    keys = sorted(k for k, v in data.items() if v)
    out["macos"].append({"file": relative, "signal": "entitlements", "keys": keys,
                         "app_sandbox": bool(data.get("com.apple.security.app-sandbox"))})
    for key, why in RISKY_ENTITLEMENTS.items():
        if data.get(key):
            out["macos"].append({"file": relative, "signal": f"risky entitlement {key}", "why": why})
    tcc = [k for k in keys if k.startswith(TCC_HINTS)]
    if tcc:
        out["macos"].append({"file": relative, "signal": "privacy-sensitive entitlements", "keys": tcc})


def scan(root: Path, include_tests: bool) -> dict:
    out = defaultdict(list)
    electron_dependency = False
    projects = set()
    for path in iter_files(root, skip_dirs=SCAN_SKIP):
        relative = rel(path, root)
        if not include_tests and (is_test_path(relative) or EXAMPLE_DIRS.search(relative)):
            continue
        name = path.name
        if FORBIDDEN_FILE.search(relative):
            out["secrets"].append({"file": relative, "signal": "file that should never be committed"})
        if name.endswith(".entitlements") or (name.endswith(".plist") and "entitlements" in name.lower()):
            entitlements(path, relative, out)
            continue
        if name == "PrivacyInfo.xcprivacy":
            out["ios"].append({"file": relative, "signal": "privacy manifest present"})
        if name == "package.json":
            text = read_text(path) or ""
            if re.search(r'"electron"\s*:', text):
                electron_dependency = True
                out["electron"].append({"file": relative, "signal": "Electron dependency"})
            if '"electron-updater"' in text:
                out["electron"].append({"file": relative, "signal": "electron-updater dependency"})
        if name == "project.pbxproj":
            projects.add(relative)
        if name in LOCKFILES or (path.suffix.lower() not in LINE_SUFFIXES and name not in ("AndroidManifest.xml", "Info.plist")):
            continue
        text = read_text(path, limit=3_000_000)
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if len(line) > 3000:
                continue
            for area, label, pattern, *only in LINE_RULES:
                if only and not only[0].search(relative):
                    continue
                if pattern.search(line):
                    signal = {"file": relative, "line": number, "signal": label, "text": line.strip()[:140]}
                    if label == "notarization setting" and re.search(r"\bfalse\b", line):
                        signal["why"] = ("electron-builder's own notarization is off; notarization may run as a separate "
                                         "step, so look for a 'notarization step' signal or read the release workflow")
                    out[area].append(signal)
            for label, pattern in SECRET_RULES:
                match = pattern.search(line)
                if match and not looks_like_placeholder(match.group(0), line):
                    out["secrets"].append({"file": relative, "line": number, "signal": label, "value": mask(match.group(0))})
    if electron_dependency and not any(s["signal"] == "fuses configured" for s in out["electron"]):
        out["electron"].append({"signal": "Electron app with no fuses configured in the repository (verify in the build output)"})
    # A native Mac app whose project never sets these reads as clean when the answer is "not configured".
    xcode = [s for s in out["macos"] if s.get("file", "").endswith(".pbxproj")]
    if any(rel_path.endswith(".pbxproj") for rel_path in projects):
        hardened = [s for s in xcode if s["signal"] == "hardened runtime in Xcode project"]
        if not any("YES" in s.get("text", "") for s in hardened):
            out["macos"].append({"signal": "Xcode project without ENABLE_HARDENED_RUNTIME = YES: notarization needs the hardened runtime",
                                 "files": sorted(projects)})
        if not any(s["signal"] == "entitlements file in Xcode project" for s in xcode):
            out["macos"].append({"signal": "Xcode project without an entitlements file (CODE_SIGN_ENTITLEMENTS)", "files": sorted(projects)})
    return {area: signals[:200] for area, signals in sorted(out.items())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo")
    parser.add_argument("--at", help="scan this branch, tag or commit instead of the working tree, without a checkout")
    parser.add_argument("--include-tests", action="store_true", help="also scan tests, fixtures and examples")
    args = parser.parse_args()
    root = Path(args.repo)
    with tree_at(root, args.at) as tree:
        signals = scan(tree, args.include_tests)
    print_json({
        "repo": str(root.resolve()),
        "at": args.at or "working tree",
        "signals": signals,
        "how_to_confirm": [
            "Check whether each setting applies to the release build or only to development.",
            "For macOS apps holding privacy permissions (Accessibility, Screen Recording, camera, microphone), risky entitlements matter more.",
            "For update settings, confirm that release builds verify signatures.",
            "Report a secret by file and line only; never print or use it. If it looks live, tell the owner privately.",
        ],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
