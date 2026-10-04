#!/usr/bin/env python3
"""Save a public web page as dated evidence: the HTML, a plain-text copy and the metadata.

Usage:
  python3 capture_page.py https://example.com/pricing --out-dir evidence/ [--max-bytes 5000000]

One GET request, redirects followed, no cookies and no credentials. Writes three files named
after the URL and the UTC time of the capture:
  <slug>-<YYYYMMDDTHHMMSSZ>.html   the page as served
  <slug>-<YYYYMMDDTHHMMSSZ>.txt    readable text, scripts and styles removed
  <slug>-<YYYYMMDDTHHMMSSZ>.json   URL, final URL, status, content type, size, SHA-256, title, time
Quote prices, plans, claims and partner lists from these files, with their capture time.
Pages that render in the browser may need a browser tool instead; the text file shows when
the served HTML is nearly empty.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from common import USER_AGENT, decode_body, html_title, html_to_text, print_json


def slug_for(url: str) -> str:
    stripped = re.sub(r"^https?://", "", url).rstrip("/")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", stripped)[:120] or "page"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-bytes", type=int, default=5_000_000)
    args = parser.parse_args()
    if not re.match(r"^https?://", args.url):
        parser.error("the URL must start with http:// or https://")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    request = urllib.request.Request(args.url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(args.max_bytes + 1)
            status, final_url = response.status, response.geturl()
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        data, status, final_url = error.read(args.max_bytes + 1), error.code, error.geturl()
        content_type = error.headers.get("Content-Type", "")
    truncated = len(data) > args.max_bytes
    data = data[: args.max_bytes]
    markup = data.decode("utf-8", errors="replace")
    text = html_to_text(markup)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{slug_for(args.url)}-{stamp}"
    paths = {ext: args.out_dir / f"{stem}.{ext}" for ext in ("html", "txt", "json")}
    data = decode_body(data)
    paths["html"].write_bytes(data)
    paths["txt"].write_text(text, encoding="utf-8")
    meta = {
        "url": args.url, "final_url": final_url, "status": status, "captured_at": stamp,
        "content_type": content_type, "bytes": len(data), "truncated": truncated,
        "sha256": hashlib.sha256(data).hexdigest(), "title": html_title(markup),
        "text_chars": len(text),
        "warning": "little text in the served HTML: the page may render in the browser" if len(text) < 300 else None,
        "files": {"html": str(paths["html"]), "text": str(paths["txt"])},
    }
    paths["json"].write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print_json(meta)
    return 0 if status < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
