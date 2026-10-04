#!/usr/bin/env python3
"""Public adoption counts from package registries and community platforms, dated, in one run.

Usage:
  python3 public_counts.py [--npm NAME] [--pypi NAME] [--crate NAME] [--brew FORMULA] [--cask TOKEN]
                           [--docker NAMESPACE/REPO] [--open-vsx NAMESPACE/NAME] [--discord INVITE]
                           [--save raw/] [--offline raw/]

Every option is repeatable. GET requests only, one at a time, no credentials. Prints JSON with:
  - npm: downloads in the last day, week and month (api.npmjs.org);
  - PyPI: downloads in the last day, week and month, as pypistats.org reports them;
  - crates.io: all-time downloads and downloads in the last 90 days;
  - Homebrew formula or cask: installs in the last 30, 90 and 365 days, from Homebrew's opt-out
    analytics (users who turned analytics off are not counted);
  - Docker Hub: all-time pulls and stars;
  - Open VSX: all-time downloads, rating and reviews;
  - Discord: approximate members and members online, read from a public invite code.
Downloads count machines, CI runs, mirrors and caches as well as people; members count accounts.
Quote every number with this run's date and say what it measures.
--save writes every response to a folder, and --offline reads them back, so a run can be audited.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from common import USER_AGENT, now_utc, print_json

SOURCES = {
    "npm": ["https://api.npmjs.org/downloads/point/last-day/{name}",
            "https://api.npmjs.org/downloads/point/last-week/{name}",
            "https://api.npmjs.org/downloads/point/last-month/{name}"],
    "pypi": ["https://pypistats.org/api/packages/{name}/recent"],
    "crate": ["https://crates.io/api/v1/crates/{name}"],
    "brew": ["https://formulae.brew.sh/api/formula/{name}.json"],
    "cask": ["https://formulae.brew.sh/api/cask/{name}.json"],
    "docker": ["https://hub.docker.com/v2/repositories/{name}/"],
    "open_vsx": ["https://open-vsx.org/api/{name}"],
    "discord": ["https://discord.com/api/v10/invites/{name}?with_counts=true"],
}
NAME = {
    "npm": re.compile(r"^(@[\w.-]+/)?[\w.-]+$"), "pypi": re.compile(r"^[\w.-]+$"), "crate": re.compile(r"^[\w-]+$"),
    "brew": re.compile(r"^[\w.+@-]+$"), "cask": re.compile(r"^[\w.+@-]+$"), "docker": re.compile(r"^[\w.-]+/[\w.-]+$"),
    "open_vsx": re.compile(r"^[\w.-]+/[\w.-]+$"), "discord": re.compile(r"^[\w-]+$"),
}


def slug(url: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("://", 1)[-1])[:180] + ".json"


class Fetcher:
    def __init__(self, save: Optional[Path], offline: Optional[Path]):
        self.save, self.offline, self.calls = save, offline, 0

    def get(self, url: str):
        if self.offline:
            path = self.offline / slug(url)
            return json.loads(path.read_text(encoding="utf-8"))["body"] if path.exists() else {"_error": "not saved"}
        if self.calls:
            time.sleep(0.5)
        self.calls += 1
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = {"_error": f"HTTP {error.code}"}
        except (urllib.error.URLError, ValueError, TimeoutError) as error:
            body = {"_error": str(error)[:120]}
        if self.save:
            self.save.mkdir(parents=True, exist_ok=True)
            (self.save / slug(url)).write_text(json.dumps({"url": url, "fetched_at": now_utc(), "body": body}, indent=1), encoding="utf-8")
        return body


def summarize(kind: str, name: str, bodies: list) -> dict:
    """The numbers that matter from each source's responses, or the error."""
    errors = [b["_error"] for b in bodies if isinstance(b, dict) and "_error" in b]
    if errors:
        return {"error": errors[0]}
    if kind == "npm":
        day, week, month = bodies
        return {"downloads_last_day": day.get("downloads"), "downloads_last_week": week.get("downloads"),
                "downloads_last_month": month.get("downloads"), "period_end": month.get("end")}
    if kind == "pypi":
        data = bodies[0].get("data") or {}
        return {"downloads_last_day": data.get("last_day"), "downloads_last_week": data.get("last_week"),
                "downloads_last_month": data.get("last_month")}
    if kind == "crate":
        crate = bodies[0].get("crate") or {}
        return {"downloads_all_time": crate.get("downloads"), "downloads_last_90_days": crate.get("recent_downloads"),
                "latest_version": crate.get("max_stable_version") or crate.get("newest_version"), "updated_at": crate.get("updated_at")}
    if kind in ("brew", "cask"):
        installs = (bodies[0].get("analytics") or {}).get("install") or {}
        out = {}
        for period in ("30d", "90d", "365d"):
            values = installs.get(period) or {}
            out[f"installs_{period}"] = values.get(name, sum(v for v in values.values() if isinstance(v, int)) if values else None)
        return out
    if kind == "docker":
        body = bodies[0]
        return {"pulls_all_time": body.get("pull_count"), "stars": body.get("star_count"), "last_updated": body.get("last_updated")}
    if kind == "open_vsx":
        body = bodies[0]
        return {"downloads_all_time": body.get("downloadCount"), "average_rating": body.get("averageRating"),
                "reviews": body.get("reviewCount"), "version": body.get("version")}
    if kind == "discord":
        body = bodies[0]
        return {"server": (body.get("guild") or {}).get("name"), "members_approximate": body.get("approximate_member_count"),
                "online_approximate": body.get("approximate_presence_count")}
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for kind in SOURCES:
        parser.add_argument("--" + kind.replace("_", "-"), dest=kind, action="append", default=[], metavar="NAME")
    parser.add_argument("--save", type=Path, help="folder to save every response in")
    parser.add_argument("--offline", type=Path, help="folder of saved responses to read instead of the network")
    args = parser.parse_args()
    wanted = [(kind, name) for kind in SOURCES for name in getattr(args, kind)]
    if not wanted:
        parser.error("name at least one package, image, extension or invite")
    fetcher = Fetcher(args.save, args.offline)
    results = []
    for kind, name in wanted:
        if kind == "discord":
            name = name.rstrip("/").rsplit("/", 1)[-1]
        if not NAME[kind].match(name):
            results.append({"source": kind, "name": name, "error": "unexpected name format"})
            continue
        quoted = urllib.parse.quote(name, safe="@/")
        bodies = [fetcher.get(url.format(name=quoted)) for url in SOURCES[kind]]
        results.append({"source": kind, "name": name, **summarize(kind, name, bodies)})
    print_json({
        "taken_at": now_utc(),
        "results": results,
        "requests": fetcher.calls,
        "notes": [
            "Downloads and pulls count machines, CI runs, mirrors and caches, not people.",
            "Homebrew counts only users who keep analytics on; Discord counts accounts, and online is a moment.",
            "Compare like with like: the same source, the same period, the same date.",
        ],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
