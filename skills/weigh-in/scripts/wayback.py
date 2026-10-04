#!/usr/bin/env python3
"""See how a public page looked in the past, through the Internet Archive's Wayback Machine.

Usage:
  python3 wayback.py list https://example.com/pricing [--from 20260101] [--to 20261001] [--per day|month]
  python3 wayback.py fetch https://example.com/pricing 20260920054828 --out pricing-0920.html [--text]

`list` asks the CDX API which snapshots exist (status 200 only), one per day or month.
`fetch` downloads one snapshot as originally archived (the "id_" form, without the Wayback
toolbar) and, with --text, also writes a plain-text copy next to it. Use it to date a price
change, a claim, a partner list or a star count shown on a site. One GET request per call.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from common import USER_AGENT, decode_body, html_to_text, now_utc, print_json

CDX = "https://web.archive.org/cdx/search/cdx"


def parse_cdx(rows: list) -> list:
    """CDX JSON output: a header row, then one row per capture."""
    if not rows:
        return []
    header, *captures = rows
    out = []
    for row in captures:
        item = dict(zip(header, row))
        ts = item.get("timestamp", "")
        item["archive_url"] = f"https://web.archive.org/web/{ts}/{item.get('original', '')}"
        item["date"] = f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}" if len(ts) >= 8 else None
        out.append(item)
    return out


def get(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return decode_body(response.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="list the snapshots of a URL")
    listing.add_argument("url")
    listing.add_argument("--from", dest="start", help="YYYYMMDD")
    listing.add_argument("--to", dest="end", help="YYYYMMDD")
    listing.add_argument("--per", choices=["day", "month", "all"], default="day", help="keep one snapshot per day or month")
    fetch = sub.add_parser("fetch", help="download one snapshot")
    fetch.add_argument("url")
    fetch.add_argument("timestamp", help="the snapshot's timestamp from `list`, e.g. 20260920054828")
    fetch.add_argument("--out", required=True, type=Path)
    fetch.add_argument("--text", action="store_true", help="also write a plain-text copy (.txt)")
    args = parser.parse_args()

    if args.command == "list":
        params = {"url": args.url, "output": "json", "filter": "statuscode:200"}
        if args.start:
            params["from"] = args.start
        if args.end:
            params["to"] = args.end
        if args.per != "all":
            params["collapse"] = "timestamp:8" if args.per == "day" else "timestamp:6"
        rows = json.loads(get(CDX + "?" + urllib.parse.urlencode(params)).decode("utf-8") or "[]")
        snapshots = parse_cdx(rows)
        print_json({"taken_at": now_utc(), "url": args.url, "snapshots": len(snapshots), "items": snapshots})
        return 0

    target = f"https://web.archive.org/web/{args.timestamp}id_/{args.url}"
    data = get(target)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    result = {"taken_at": now_utc(), "url": args.url, "timestamp": args.timestamp, "archive_url": target,
              "saved": str(args.out), "bytes": len(data)}
    if args.text:
        text_path = args.out.with_suffix(".txt")
        text_path.write_text(html_to_text(data.decode("utf-8", errors="replace")), encoding="utf-8")
        result["text"] = str(text_path)
    print_json(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
