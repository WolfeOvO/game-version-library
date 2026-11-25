#!/usr/bin/env python3
"""Collect Stardew Valley Android package metadata from its public JSON feed."""
from __future__ import annotations

import argparse
import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/source-snapshots/non-minecraft/stardew.json"
CACHE = ROOT / "data/source-cache/stardew/versions.json"
URL = "https://data.stardewvalley.spectrollay.com/repository/database/versions.json"
UA = "game-version-library-stardew/1.0 (+https://github.com/WolfeOvO/game-version-library)"


def strip_jsonc(text: str) -> str:
    result = []
    index = 0
    quoted = False
    while index < len(text):
        char = text[index]
        if quoted:
            result.append(char)
            if char == "\\" and index + 1 < len(text):
                result.append(text[index + 1])
                index += 2
                continue
            if char == '"':
                quoted = False
            index += 1
            continue
        if char == '"':
            quoted = True
            result.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < len(text) and text[index + 1] == "/":
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        result.append(char)
        index += 1
    return "".join(result)


def fetch(refresh: bool) -> list[dict]:
    if CACHE.exists() and not refresh and time.time() - CACHE.stat().st_mtime < 3600:
        return json.loads(strip_jsonc(CACHE.read_text(encoding="utf-8")))
    request = Request(URL, headers={"User-Agent": UA, "Accept": "application/json"})
    with urlopen(request, timeout=60) as response:
        text = response.read().decode("utf-8")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(text, encoding="utf-8")
    return json.loads(strip_jsonc(text))


def date(value: object) -> str:
    parts = re.split(r"[.\-/]", str(value or "").strip())
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return ""
    return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"


def source_offer(url: str, label: str, size: int, note: str, requires_password: bool) -> dict:
    # The source may provide a share code. It is intentionally not copied into
    # the public snapshot; access mode is enough for the normalized catalog.
    return {
        "source": "stardew",
        "provider": label,
        "kind": "share",
        "url": url,
        "arch": "",
        "size": size or None,
        "checksum_type": "",
        "checksum": "",
        "scope": "file",
        "note": note,
        "access_mode": "password" if requires_password else "public",
    }


def normalize(rows: list[dict]) -> dict:
    versions = []
    for index, row in enumerate(rows):
        version = str(row.get("version") or "").strip()
        if not version:
            continue
        released = date(row.get("date"))
        description = re.sub(r"<[^>]+>", " ", str(row.get("description") or ""))
        description = re.sub(r"\s+", " ", html.unescape(description)).strip()
        offers = []
        for key, label in (("originalPackage", "原版"), ("repackedPackage", "重打包")):
            package = row.get(key) or {}
            files = package.get("files") or []
            links = [item for item in package.get("links") or [] if str(item.get("url") or "").startswith("http")]
            if not files or not links:
                continue
            size = sum(int(item.get("size") or 0) for item in files if str(item.get("size") or "0").isdigit())
            architectures = []
            for file_item in files:
                for architecture in file_item.get("architectures") or []:
                    if architecture not in architectures:
                        architectures.append(architecture)
            note = f"{label}包 {len(files)} 个文件（{'/'.join(architectures) or '通用'}）"
            for link in links:
                offers.append(source_offer(str(link["url"]), label, size, note, bool(str(link.get("code") or "").strip())))
        if offers:
            versions.append({
                "v": version,
                "device": "stardew",
                "channel": "release",
                "channels": ["release"],
                "released": released,
                "notes": description[:160],
                "meta": {
                    "versionCode": row.get("versionCode"),
                    "targetSdk": row.get("targetSdk"),
                    "minSdk": row.get("minSdk"),
                    "idx": index,
                    "size": max((item.get("size") or 0) for item in offers),
                },
                "sources": ["stardew"],
                "offers": offers,
                "major": "1.x",
                "size": max((item.get("size") or 0) for item in offers),
                "offer_count": len(offers),
                "providers": sorted({item["provider"] for item in offers}),
            })
    return {"device": "stardew", "name": "星露谷物语 · Android", "generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "versions": versions, "directories": []}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    result = normalize(fetch(args.refresh))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT} versions={len(result['versions'])} offers={sum(len(item['offers']) for item in result['versions'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
