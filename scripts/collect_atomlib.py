#!/usr/bin/env python3
"""Collect the public NullAtom catalog for Terraria and Rusted Warfare.

Only metadata and original source-page URLs are written. No package bytes are
Downloaded or copied into this repository.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/source-snapshots/non-minecraft/atomlib.json"
CACHE = ROOT / "data/cache/atomlib"
API = "https://res.nullatom.com/api/fetch"
SITE = "https://res.nullatom.com"
UA = "game-version-library/1.0 (+https://github.com/WolfeOvO/game-version-library)"


def fetch_dir(path: str, refresh: bool) -> list[dict]:
    cache = CACHE / (re.sub(r"[^0-9A-Za-z._-]+", "_", path.strip("/")) or "root")
    cache = cache.with_suffix(".json")
    if cache.exists() and not refresh and time.time() - cache.stat().st_mtime < 1800:
        return json.loads(cache.read_text(encoding="utf-8"))
    body = json.dumps({"path": path}).encode()
    request = Request(API, data=body, method="POST", headers={"Content-Type": "application/json", "User-Agent": UA})
    with urlopen(request, timeout=45) as response:
        payload = json.loads(response.read())
    if payload.get("code") != 200:
        raise RuntimeError(f"{path}: upstream code={payload.get('code')}")
    items = payload.get("list") or []
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return items


def walk(root: str, refresh: bool) -> list[dict]:
    files: list[dict] = []
    frontier = [root]
    seen: set[str] = set()
    while frontier:
        with ThreadPoolExecutor(max_workers=6) as pool:
            batches = list(pool.map(lambda path: (path, fetch_dir(path, refresh)), frontier))
        frontier = []
        for _path, items in batches:
            for item in items:
                path = str(item.get("path") or "")
                if not path or path in seen:
                    continue
                seen.add(path)
                if item.get("is_file"):
                    files.append(item)
                elif path.count("/") < 10:
                    frontier.append(path)
    return files


def version_key(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", value)
    return tuple(int(number) for number in numbers) if numbers else (0,)


def make_file(item: dict, version: str, variant: str = "", os_name: str = "", arch: str = "", note: str = "") -> dict:
    path = str(item.get("path") or "")
    return {
        "name": str(item.get("name") or ""),
        "path": path,
        "url": SITE + quote(path, safe="/"),
        "size": int(item.get("size") or 0) or None,
        "created": str(item.get("created_at") or "")[:10],
        "version": version,
        "variant": variant,
        "os": os_name,
        "arch": arch,
        "note": note,
    }


def parse_files(files: list[dict]) -> dict:
    groups: dict[str, dict] = {}
    def group(key: str, label: str, kind: str) -> dict:
        return groups.setdefault(key, {"key": key, "label": label, "kind": kind, "files": []})

    for item in files:
        path = str(item.get("path") or "")
        match = re.fullmatch(r"/Terraria/PE/(\d[\d.]*)\.apk", path, re.I)
        if match:
            group("client-android", "Android（PE）", "client")["files"].append(make_file(item, match.group(1), "APK", "Android")); continue
        match = re.fullmatch(r"/Terraria/Windows/setup_terraria_v?([\d.]+)\.exe", path, re.I)
        if match:
            group("client-windows", "Windows", "client")["files"].append(make_file(item, match.group(1), "安装包", "Windows")); continue
        match = re.fullmatch(r"/Terraria/Server/PC/terraria-server-([\d.]+)\.zip", path, re.I)
        if match:
            group("server-pc", "原版（PC）", "server")["files"].append(make_file(item, match.group(1), os_name="Windows / Linux")); continue
        match = re.fullmatch(r"/Terraria/Server/PE/Terraria-Mobile-Server-([\d.]+)\.zip", path, re.I)
        if match:
            group("server-mobile", "手机版", "server")["files"].append(make_file(item, match.group(1), os_name="Android")); continue
        match = re.fullmatch(r"/Terraria/Server/TModLoader/tModLoader-([\d.]+)\.zip", path, re.I)
        if match:
            group("server-tmodloader", "tModLoader", "server")["files"].append(make_file(item, match.group(1), note="tModLoader 服务端")); continue
        match = re.fullmatch(r"/Terraria/Server/TShock/AtomCraft/TShock([\d.]+)_Terraria([\d.]+)\.zip", path, re.I)
        if match:
            group("server-tshock-atomcraft", "AtomCraft", "server")["files"].append(make_file(item, match.group(1), variant=f"Terraria {match.group(2)}", note=f"TShock {match.group(1)} + Terraria {match.group(2)}")); continue
        match = re.fullmatch(r"/Terraria/Server/TShock/(Linux|Windows)/Terraria-([\d.]+)-(linux|win)-x64-Release\.zip", path, re.I)
        if match:
            group("server-tshock", "TShock", "server")["files"].append(make_file(item, match.group(2), os_name=match.group(1), arch="x64", note="TShock 服务端")); continue

        match = re.fullmatch(r"/RustedWarfare/Android/(\d[\d.]*)\.apk", path, re.I)
        if match:
            group("client-android", "Android", "client")["files"].append(make_file(item, match.group(1), "APK", "Android")); continue
        match = re.fullmatch(r"/RustedWarfare/Server/RW-HPS/([\d.]+)\.jar", path, re.I)
        if match:
            group("server-rwhps", "RW-HPS 服务端", "server")["files"].append(make_file(item, match.group(1), note="RW-HPS Java 服务端")); continue

    for value in groups.values():
        value["files"].sort(key=lambda item: (version_key(item["version"]), item["os"], item["arch"]), reverse=True)
    return groups


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    terraria_groups = parse_files(walk("/Terraria", args.refresh))
    rusted_groups = parse_files(walk("/RustedWarfare", args.refresh))
    libraries = {}
    libraries["terraria"] = {"name": "泰拉瑞亚", "slug": "terraria", "intro": "泰拉瑞亚客户端与服务端安装包。", "groups": list(terraria_groups.values())}
    libraries["rustedwarfare"] = {"name": "铁锈战争", "slug": "rustedwarfare", "intro": "铁锈战争 Android 客户端与 RW-HPS 服务端。", "groups": list(rusted_groups.values())}
    output = {"generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "source": {"name": "NullAtom 原子资源", "site": SITE, "api": API}, "libraries": libraries}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    file_count = sum(len(group["files"]) for library in libraries.values() for group in library["groups"])
    print(f"wrote {OUT} files={file_count} groups={sum(len(value['groups']) for value in libraries.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
