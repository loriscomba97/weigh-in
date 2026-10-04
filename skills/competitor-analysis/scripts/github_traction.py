#!/usr/bin/env python3
"""Public traction numbers for a GitHub repository, and what its release downloads really mean.

Usage:
  python3 github_traction.py owner/repo [--releases-repo owner/other] [--check-interval-hours 1]
                             [--star-history 12] [--max-release-pages 5] [--save raw/] [--offline raw/]
                             [--no-search]

Reads the public GitHub REST API with GET requests only. Unauthenticated calls are limited
(60 an hour, 10 searches a minute); set GITHUB_TOKEN in the environment to raise the limit.
The token is sent to api.github.com only and never printed.

Prints JSON with:
  - repository facts: stars, forks, watchers, default branch, license, dates, topics;
  - open issues and open pull requests counted apart (the repository's open_issues_count
    adds the two together), totals and merged pull requests, through the search API;
  - the number of contributors GitHub lists (it counts linked accounts, not people);
  - every release asset classified as installer (with a stable or versioned file name),
    update check, update delta, checksum or signature, package, archive or other, per platform;
  - per-release windows: installers per day and update checks per day;
  - with --check-interval-hours H, an estimate of copies running at once:
    update checks per day * H / 24. It is an estimate; say so wherever you quote it;
  - with --star-history N, star milestones and their dates from N sampled pages of the stargazer
    list (GitHub returns it oldest first), and the pace in stars per day between milestones. It
    costs N calls and needs GITHUB_TOKEN: GitHub lists stargazers to signed-in callers only.
    GitHub also stops paging very large lists; the output says when it did.
--save writes every API response to a folder, and --offline reads them back, so a run can be
reproduced and audited later.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from common import USER_AGENT, now_utc, parse_iso, print_json

API = "https://api.github.com"

INSTALLER_EXT = {
    ".dmg": "macos", ".pkg": "macos", ".exe": "windows", ".msi": "windows", ".msix": "windows",
    ".appx": "windows", ".appimage": "linux", ".deb": "linux", ".rpm": "linux", ".flatpak": "linux",
    ".snap": "linux", ".apk": "android", ".aab": "android", ".ipa": "ios",
}
UPDATE_CHECK = re.compile(r"(^latest[\w.-]*\.ya?ml$|^appcast[\w.-]*\.xml$|^releases$|^update[\w.-]*\.json$|^latest\.json$)", re.I)
UPDATE_DELTA = re.compile(r"(\.blockmap$|\.delta$|-delta\.nupkg$|\.patch$)", re.I)
CHECKSUM = re.compile(r"(\.sha(1|256|512)(sum)?$|^sha(1|256|512)sums?(\.txt)?$|checksums?(\.txt)?$|\.sig$|\.asc$|\.minisig$|\.sbom|\.spdx|\.cdx\.json$|\.intoto\.jsonl$)", re.I)
PACKAGE = re.compile(r"(\.whl$|\.nupkg$|\.gem$|\.crate$|\.jar$|\.vsix$|\.xpi$|\.crx$|^[\w.-]+-\d[\w.-]*\.tgz$)", re.I)
ARCHIVE = re.compile(r"(\.zip$|\.tar\.gz$|\.tgz$|\.tar\.xz$|\.tar\.bz2$|\.tar\.zst$|\.7z$)", re.I)
VERSION_IN_NAME = re.compile(r"(^|[-_.v])\d+\.\d+(\.\d+)?([-_.][0-9A-Za-z]+)*")
PLATFORM_HINTS = [
    ("macos", re.compile(r"(mac|darwin|osx|apple)", re.I)),
    ("windows", re.compile(r"(win|windows|\.exe$|\.msi$)", re.I)),
    ("linux", re.compile(r"(linux|appimage|\.deb$|\.rpm$|ubuntu|debian|fedora)", re.I)),
    ("android", re.compile(r"(android|\.apk$|\.aab$)", re.I)),
    ("ios", re.compile(r"(\bios\b|\.ipa$|iphone)", re.I)),
]


def platform_of(name: str) -> str:
    lower = name.lower()
    for ext, platform in INSTALLER_EXT.items():
        if lower.endswith(ext):
            return platform
    for platform, pattern in PLATFORM_HINTS:
        if pattern.search(name):
            return platform
    return "any"


def classify_asset(name: str, tag: str = "") -> dict:
    """Category, platform and whether the file name carries a version.

    Update checks are downloaded by running copies, often at every launch and then on a timer, so
    they measure activity, not people. Installers with a version in the name can also be fetched
    by an updater (a Windows setup file, say), so stable-name installers are the cleanest count of
    new installs.
    """
    lower = name.lower()
    versioned = bool(VERSION_IN_NAME.search(name)) or (bool(tag) and tag.lstrip("v") in name)
    if UPDATE_CHECK.search(name):
        category = "update-check"
    elif UPDATE_DELTA.search(name):
        category = "update-delta"
    elif CHECKSUM.search(name):
        category = "checksum-or-signature"
    elif any(lower.endswith(ext) for ext in INSTALLER_EXT):
        category = "installer"
    elif PACKAGE.search(name):
        category = "package"
    elif ARCHIVE.search(name):
        category = "update-payload-or-archive" if platform_of(name) == "macos" else "archive"
    else:
        category = "other"
    return {"category": category, "platform": platform_of(name), "versioned_name": versioned}


def last_page(link_header: Optional[str]) -> Optional[int]:
    """The page number of rel="last" in a GitHub Link header."""
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="last"' in part:
            match = re.search(r"[?&]page=(\d+)", part)
            if match:
                return int(match.group(1))
    return None


class Client:
    def __init__(self, save: Optional[Path], offline: Optional[Path]):
        self.save, self.offline = save, offline
        self.token = os.environ.get("GITHUB_TOKEN") or None
        self.calls = 0

    @staticmethod
    def slug(path: str, params: dict) -> str:
        raw = path.strip("/") + ("?" + urllib.parse.urlencode(sorted(params.items())) if params else "")
        return re.sub(r"[^A-Za-z0-9._-]+", "_", raw)[:180] + ".json"

    def get(self, path: str, params: Optional[dict] = None, search: bool = False, accept: str = "application/vnd.github+json",
            tolerate: tuple = ()):
        params = params or {}
        name = self.slug(path, params)
        if self.offline:
            if not (self.offline / name).exists() and tolerate:
                return None, {}
            with open(self.offline / name, encoding="utf-8") as handle:
                saved = json.load(handle)
            return saved["body"], saved.get("headers", {})
        url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
        request = urllib.request.Request(url, headers={
            "Accept": accept, "User-Agent": USER_AGENT, "X-GitHub-Api-Version": "2022-11-28",
            **({"Authorization": f"Bearer {self.token}"} if self.token else {}),
        })
        if self.calls:
            time.sleep(2.5 if search and not self.token else 0.5)
        self.calls += 1
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
                headers = {k: v for k, v in response.headers.items() if k.lower() in ("link", "x-ratelimit-remaining", "x-ratelimit-reset", "date")}
        except urllib.error.HTTPError as error:
            if error.code in tolerate:
                return None, {}
            if error.code in (403, 429):
                reset = error.headers.get("x-ratelimit-reset")
                when = datetime.fromtimestamp(int(reset), timezone.utc).isoformat() if reset else "unknown"
                raise SystemExit(f"GitHub rate limit reached on {path}; it resets at {when}. Set GITHUB_TOKEN or retry later.")
            raise SystemExit(f"GitHub API error {error.code} on {path}")
        if self.save:
            self.save.mkdir(parents=True, exist_ok=True)
            with open(self.save / name, "w", encoding="utf-8") as handle:
                json.dump({"url": url, "fetched_at": now_utc(), "headers": headers, "body": body}, handle, indent=1)
        return body, headers


def search_count(client: Client, query: str) -> Optional[int]:
    body, _ = client.get("/search/issues", {"q": query, "per_page": 1}, search=True)
    return body.get("total_count")


def merge_by_tag(releases: list) -> list:
    """One entry per tag: a version published in a mirror repository too counts once, with its
    assets added together and the earliest publish date."""
    merged = {}
    for r in releases:
        if not r.get("published_at"):
            continue
        tag = r.get("tag_name") or r["published_at"]
        entry = merged.setdefault(tag, {"tag_name": tag, "published_at": r["published_at"], "assets": []})
        entry["published_at"] = min(entry["published_at"], r["published_at"])
        entry["assets"].extend(r.get("assets", []))
    return sorted(merged.values(), key=lambda r: r["published_at"])


def release_windows(releases: list, now: datetime) -> list:
    """Each release is "the latest" from its publish date until the next one. Update checks on its
    assets accrue in that window, so checks per day approximate the copies checking per day."""
    rows = []
    published = merge_by_tag(releases)
    for i, r in enumerate(published):
        start = parse_iso(r["published_at"])
        end = parse_iso(published[i + 1]["published_at"]) if i + 1 < len(published) else now
        days = max((end - start).total_seconds() / 86400, 1 / 24)
        counts = Counter()
        for asset in r["assets"]:
            kind = classify_asset(asset["name"], r["tag_name"])
            counts[kind["category"]] += asset.get("download_count", 0)
            if kind["category"] == "installer" and not kind["versioned_name"]:
                counts["installer-stable-name"] += asset.get("download_count", 0)
        rows.append({
            "tag": r["tag_name"], "published_at": r["published_at"], "window_days": round(days, 2),
            "installers": counts["installer"], "installers_stable_name": counts["installer-stable-name"],
            "update_checks": counts["update-check"],
            "installers_per_day": round(counts["installer"] / days, 1),
            "update_checks_per_day": round(counts["update-check"] / days, 1),
        })
    return rows


def summarize_releases(releases: list, check_interval_hours: Optional[float], now: datetime) -> dict:
    by_category = Counter()
    by_platform = defaultdict(Counter)
    for r in releases:
        for asset in r.get("assets", []):
            kind = classify_asset(asset["name"], r.get("tag_name", ""))
            n = asset.get("download_count", 0)
            key = kind["category"]
            if key == "installer":
                key = "installer-versioned-name" if kind["versioned_name"] else "installer-stable-name"
            by_category[key] += n
            by_platform[kind["platform"]][key] += n
    total = sum(by_category.values())
    windows = release_windows(releases, now)
    estimate = None
    if check_interval_hours and windows:
        recent = [w for w in windows[:-1] if w["window_days"] >= 0.5][-5:] or windows[-5:]
        days = sum(w["window_days"] for w in recent)
        checks = sum(w["update_checks"] for w in recent)
        estimate = {
            "check_interval_hours": check_interval_hours,
            "update_checks_per_day_recent": round(checks / days, 1) if days else None,
            "copies_running_at_once": round(checks / days * check_interval_hours / 24) if days else None,
            "basis": "the last five closed release windows of at least half a day; copies = checks per day * interval / 24",
        }
    return {
        "release_entries": len(releases),
        "versions": len(merge_by_tag(releases)),
        "assets_total_downloads": total,
        "by_category": dict(by_category.most_common()),
        "by_platform": {p: dict(c.most_common()) for p, c in sorted(by_platform.items())},
        "installers_share_pct": round(100 * (by_category["installer-stable-name"] + by_category["installer-versioned-name"]) / total, 1) if total else 0.0,
        "update_checks_share_pct": round(100 * by_category["update-check"] / total, 1) if total else 0.0,
        "windows": windows,
        "running_copies_estimate": estimate,
    }


def sample_pages(total_pages: int, samples: int) -> list:
    """Evenly spaced page numbers from 1 to total_pages, both included."""
    if total_pages <= 0:
        return []
    if samples <= 1 or total_pages == 1:
        return [1]
    return sorted({1 + round(i * (total_pages - 1) / (samples - 1)) for i in range(samples)})


def star_pace(points: list) -> list:
    """Stars per day between consecutive dated milestones."""
    segments = []
    for a, b in zip(points, points[1:]):
        days = (parse_iso(b["starred_at"]) - parse_iso(a["starred_at"])).total_seconds() / 86400
        if b["star"] > a["star"] and days > 0:
            segments.append({"from": a["starred_at"][:10], "to": b["starred_at"][:10], "stars": b["star"] - a["star"],
                             "days": round(days, 1), "stars_per_day": round((b["star"] - a["star"]) / days, 1)})
    return segments


def star_history(client: "Client", repo: str, stars: Optional[int], samples: int) -> Optional[dict]:
    if not stars:
        return None
    if not client.token and not client.offline:
        return {"skipped": "GitHub lists stargazers to signed-in callers only; set GITHUB_TOKEN to sample them."}
    total_pages = (stars + 99) // 100
    points, stopped_at = [], None
    for page in sample_pages(total_pages, samples):
        body, _ = client.get(f"/repos/{repo}/stargazers", {"per_page": 100, "page": page},
                             accept="application/vnd.github.star+json", tolerate=(401, 404, 422))
        if not body:
            stopped_at = page
            break
        if body[0].get("starred_at"):
            points.append({"star": (page - 1) * 100 + 1, "starred_at": body[0]["starred_at"]})
        if page == total_pages and len(body) > 1 and body[-1].get("starred_at"):
            points.append({"star": (page - 1) * 100 + len(body), "starred_at": body[-1]["starred_at"]})
    return {
        "milestones": points,
        "pace": star_pace(points),
        "stopped_at_page": stopped_at,
        "note": "Star numbers count current stargazers in the order they starred; people who removed a star are gone from the list.",
    }


def fetch_releases(client: Client, repo: str, max_pages: int) -> list:
    releases = []
    for page in range(1, max_pages + 1):
        body, _ = client.get(f"/repos/{repo}/releases", {"per_page": 100, "page": page})
        releases.extend(body)
        if len(body) < 100:
            break
    return releases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo", help="owner/name")
    parser.add_argument("--releases-repo", action="append", default=[], help="another owner/name that also hosts releases; repeatable")
    parser.add_argument("--check-interval-hours", type=float, help="how often a running copy checks for updates, read from the product's code")
    parser.add_argument("--max-release-pages", type=int, default=5, help="pages of 100 releases to read per repository")
    parser.add_argument("--star-history", type=int, default=0, metavar="N", help="sample N pages of stargazers to date star milestones")
    parser.add_argument("--no-search", action="store_true", help="skip the search API calls (issues and pull requests)")
    parser.add_argument("--save", type=Path, help="folder to save every API response in")
    parser.add_argument("--offline", type=Path, help="folder of saved responses to read instead of the network")
    args = parser.parse_args()

    if not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repo):
        parser.error("repo must look like owner/name")
    client = Client(args.save, args.offline)
    repo, _ = client.get(f"/repos/{args.repo}")
    facts = {
        "full_name": repo.get("full_name"), "description": repo.get("description"),
        "stars": repo.get("stargazers_count"), "forks": repo.get("forks_count"), "watchers": repo.get("subscribers_count"),
        "open_issues_plus_prs": repo.get("open_issues_count"), "default_branch": repo.get("default_branch"),
        "license": (repo.get("license") or {}).get("spdx_id"), "created_at": repo.get("created_at"),
        "pushed_at": repo.get("pushed_at"), "archived": repo.get("archived"), "topics": repo.get("topics", []),
        "homepage": repo.get("homepage"),
    }
    listed, headers = client.get(f"/repos/{args.repo}/contributors", {"per_page": 1, "anon": "false"})
    contributors = last_page(headers.get("Link") or headers.get("link")) or len(listed)
    issues = None
    if not args.no_search:
        q = f"repo:{args.repo}"
        issues = {
            "open_issues": search_count(client, f"{q} is:issue is:open"),
            "open_pull_requests": search_count(client, f"{q} is:pr is:open"),
            "all_issues": search_count(client, f"{q} is:issue"),
            "all_pull_requests": search_count(client, f"{q} is:pr"),
            "merged_pull_requests": search_count(client, f"{q} is:pr is:merged"),
        }
    releases = []
    for name in [args.repo, *args.releases_repo]:
        releases.extend(fetch_releases(client, name, args.max_release_pages))
    print_json({
        "taken_at": now_utc(),
        "repo": facts,
        "contributors_listed": contributors,
        "issues_and_prs": issues,
        "release_repos": [args.repo, *args.releases_repo],
        "release_downloads": summarize_releases(releases, args.check_interval_hours, datetime.now(timezone.utc)),
        "star_history": star_history(client, args.repo, facts["stars"], args.star_history) if args.star_history else None,
        "notes": [
            "Download counts are lifetime totals per asset; they include bots, mirrors and retries.",
            "Update checks measure running copies, not people. Installers with a stable name are the cleanest count of new installs.",
            "Stars measure attention, not use. Quote every number with this run's date.",
        ],
        "api_calls": client.calls,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
