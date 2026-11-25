#!/usr/bin/env python3
"""Remove raw share passwords and signed query parameters from public snapshots."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_QUERY_KEYS = {
    "pwd",
    "password",
    "token",
    "access_token",
    "api_key",
    "apikey",
    "secret",
    "cookie",
    "authorization",
    "signature",
    "sig",
    "auth",
    "e",
}


def sanitize_url(value: str) -> tuple[str, set[str]]:
    if not value.startswith(("http://", "https://")):
        return value, set()
    parts = urlsplit(value)
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    removed = {key.lower() for key, _ in pairs if key.lower() in SENSITIVE_QUERY_KEYS}
    safe_query = [(key, val) for key, val in pairs if key.lower() not in SENSITIVE_QUERY_KEYS]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(safe_query), parts.fragment)), removed


def sanitize(value):
    if isinstance(value, dict):
        result = {}
        removed_from_url: set[str] = set()
        for key, child in value.items():
            if key == "password":
                if child:
                    result["access_mode"] = "password"
                continue
            if key in {"url", "landing_url", "source_url"} and isinstance(child, str):
                cleaned, removed = sanitize_url(child)
                result[key] = cleaned
                removed_from_url.update(removed)
            else:
                result[key] = sanitize(child)
        if removed_from_url and "access_mode" not in result:
            result["access_mode"] = "password" if removed_from_url & {"pwd", "password"} else "signed"
        return result
    if isinstance(value, list):
        return [sanitize(child) for child in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=Path(__file__).resolve().parents[1] / "data" / "source-snapshots")
    args = parser.parse_args()
    changed = 0
    for path in sorted(args.root.rglob("*.json")):
        original = json.loads(path.read_text(encoding="utf-8"))
        cleaned = sanitize(original)
        if cleaned != original:
            path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            changed += 1
    print(f"sanitized {changed} JSON snapshot files")


if __name__ == "__main__":
    main()
