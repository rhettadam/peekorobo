#!/usr/bin/env python3
"""Print a Neon pooled DB_URL from a direct Neon URL (no secrets written).

Usage:
  python scripts/neon_pooler_url.py "postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/neondb"
"""
from __future__ import annotations

import sys
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def to_pooler(url: str) -> str:
    raw = url.strip().replace("postgres://", "postgresql://", 1)
    u = urlparse(raw)
    host = u.hostname or ""
    if "-pooler." not in host and host.startswith("ep-"):
        # ep-name.region.aws.neon.tech -> ep-name-pooler.region.aws.neon.tech
        parts = host.split(".", 1)
        host = parts[0] + "-pooler." + (parts[1] if len(parts) > 1 else "")
    q = dict(parse_qsl(u.query, keep_blank_values=True))
    q.setdefault("sslmode", "require")
    netloc = u.netloc
    if u.hostname:
        # rebuild netloc with possible userinfo/port
        auth = ""
        if u.username is not None:
            auth = u.username
            if u.password is not None:
                auth += f":{u.password}"
            auth += "@"
        port = f":{u.port}" if u.port else ""
        netloc = f"{auth}{host}{port}"
    return urlunparse((u.scheme, netloc, u.path, u.params, urlencode(q), u.fragment))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(2)
    print(to_pooler(sys.argv[1]))
