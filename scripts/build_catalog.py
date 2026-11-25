#!/usr/bin/env python3
"""Build the public non-Minecraft catalog from audited source snapshots.

Minecraft is intentionally outside this repository. The public scope is the
three non-Minecraft game libraries: Stardew Valley, Terraria and Rusted Warfare.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "source-snapshots" / "non-minecraft"
OUT = ROOT / "data" / "catalog.json"
NOW_FALLBACK = "1970-01-01T00:00:00Z"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def iso(value: str | None) -> str:
    if not value:
        return NOW_FALLBACK
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return text + "T00:00:00Z"
        return NOW_FALLBACK
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def date_only(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", text) else None


def slug(value: str, prefix: str = "item") -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    if text:
        return text[:100]
    return f"{prefix}-{hashlib.sha256(str(value).encode()).hexdigest()[:16]}"


def digest_id(*parts: object, prefix: str = "item") -> str:
    joined = "\x1f".join(str(part) for part in parts)
    return f"{slug(prefix, prefix)}-{hashlib.sha256(joined.encode()).hexdigest()[:20]}"


def source_url_from_offer(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/" if parsed.scheme and parsed.netloc else "https://example.invalid/"


class SourceRegistry:
    def __init__(self) -> None:
        self.items: dict[str, dict] = {}

    def add(self, source_id: str, name: str, url: str, kind: str, retrieved_at: str) -> str:
        key = slug(source_id, "source")
        if key not in self.items:
            self.items[key] = {
                "source_id": key,
                "name": name or key,
                "url": url or "https://example.invalid/",
                "kind": kind,
                "retrieved_at": iso(retrieved_at),
            }
        else:
            self.items[key]["retrieved_at"] = max(self.items[key]["retrieved_at"], iso(retrieved_at))
            if self.items[key]["url"] == "https://example.invalid/" and url:
                self.items[key]["url"] = url
        return key

    def offer_source(self, source_id: str, url: str, retrieved_at: str, kind: str = "import") -> str:
        key = slug(source_id, "source")
        if key not in self.items:
            self.add(key, source_id, source_url_from_offer(url), kind, retrieved_at)
        return key


def license_block() -> dict:
    return {
        "data": {
            "spdx_id": "LicenseRef-GameVersionLibrary-Metadata",
            "notice": "仅发布版本元数据、来源和入口，不随本目录再分发游戏文件。",
        },
        "code": {"spdx_id": "MIT"},
        "redistribution": "link-only",
    }


def checksum_items(raw: dict) -> list[dict]:
    algorithm = str(raw.get("checksum_type") or "").lower()
    value = str(raw.get("checksum") or "")
    if algorithm in {"md5", "sha1", "sha256", "sha512", "blake3"} and re.fullmatch(r"[0-9a-fA-F]{32,128}", value):
        return [{"algorithm": algorithm, "value": value}]
    return []


def map_offer(raw: dict, source_id: str, verified_at: str, index: int, context: str) -> dict:
    kind = {"file": "direct", "link": "direct", "netdisk": "share"}.get(str(raw.get("kind") or "metadata"), str(raw.get("kind") or "metadata"))
    if kind not in {"official", "direct", "mirror", "share", "page", "directory", "api", "metadata"}:
        kind = "metadata"
    scope = str(raw.get("scope") or "file")
    if scope not in {"file", "package", "directory", "page", "metadata"}:
        scope = "metadata"
    url = str(raw.get("url") or "https://example.invalid/")
    offer = {
        "offer_id": digest_id(context, source_id, url, raw.get("arch"), raw.get("note"), index, prefix="offer"),
        "source_id": source_id,
        "kind": kind,
        "scope": scope,
        "url": url,
        "verification_status": "verified" if checksum_items(raw) else "unknown",
        "last_verified_at": verified_at,
        "access": {"mode": str(raw.get("access_mode") or ("password" if raw.get("password") else "public"))},
    }
    if offer["access"]["mode"] not in {"public", "password", "account", "signed", "unknown"}:
        offer["access"] = {"mode": "unknown"}
    for source_key, target_key in (("provider", "provider"), ("arch", "architecture"), ("note", "label")):
        if raw.get(source_key):
            offer[target_key] = str(raw[source_key])
    if isinstance(raw.get("size"), int) and raw["size"] >= 0:
        offer["size_bytes"] = raw["size"]
    if checksum_items(raw):
        offer["checksums"] = checksum_items(raw)
    return offer


def entry(game_id: str, dataset_id: str, version: str, verified_at: str, source_ids: list[str], raw: dict) -> dict:
    channel = str(raw.get("channel") or "unknown")
    if channel not in {"release", "beta", "preview", "snapshot", "alpha", "nightly", "old", "unknown"}:
        channel = "unknown"
    item = {
        "entry_id": digest_id(dataset_id, version, prefix="entry"),
        "entry_type": "version",
        "version": version,
        "version_raw": str(raw.get("version_raw") or raw.get("v") or version),
        "version_normalized": str(raw.get("version_normalized") or version),
        "channel": channel,
        "availability": "metadata-only",
        "last_verified_at": verified_at,
        "provenance": [{"source_id": source_id, "retrieved_at": verified_at, "method": "import"} for source_id in sorted(set(source_ids))],
    }
    if raw.get("major"):
        item["major"] = str(raw["major"])
    if (release_date := date_only(raw.get("release_date") or raw.get("released") or raw.get("date"))):
        item["release_date"] = release_date
    notes = raw.get("notes")
    if notes:
        item["notes"] = notes if isinstance(notes, str) else " ".join(str(value) for value in notes)
    return item


def finalize(items: dict[str, dict]) -> list[dict]:
    for item in items.values():
        if item.get("offers"):
            unique = {offer["offer_id"]: offer for offer in item["offers"]}
            item["offers"] = [unique[key] for key in sorted(unique)]
            item["availability"] = "downloadable"
        item["provenance"] = sorted(item["provenance"], key=lambda value: (value["source_id"], value["method"]))
    return sorted(items.values(), key=lambda value: (value["version_normalized"], value["entry_id"]), reverse=True)


def dataset(dataset_id: str, game_id: str, name: str, family: str, os_name: str, verified_at: str, source_ids: list[str], entries: list[dict]) -> dict:
    return {
        "dataset_id": dataset_id,
        "game_id": game_id,
        "platform_id": dataset_id,
        "name": name,
        "platform": {"display_name": name, "family": family, "os": os_name},
        "last_verified_at": max([verified_at] + [item["last_verified_at"] for item in entries]),
        "license": license_block(),
        "provenance": {"source_ids": sorted(set(source_ids)), "method": "import", "retrieved_at": verified_at},
        "entries": entries,
    }


def history_sources(registry: SourceRegistry, history: dict) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    generated = iso(history.get("generated"))
    for game_id, game in (history.get("games") or {}).items():
        result[game_id] = [registry.add(f"history-{game_id}-{source.get('label', '')}", source.get("label", game_id), source.get("url", "https://example.invalid/"), "official", generated) for source in game.get("sources") or []]
    return result


def merge_history(items: dict[str, dict], game_id: str, dataset_id: str, history: dict, history_game_id: str, platform_key: str, sources: list[str]) -> None:
    game = (history.get("games") or {}).get(history_game_id) or {}
    platform = next((value for value in game.get("platforms") or [] if value.get("key") == platform_key), None)
    if not platform:
        return
    verified = iso(history.get("generated"))
    for raw in platform.get("versions") or []:
        version = str(raw.get("v") or "unknown")
        item = items.get(version)
        if item is None:
            item = entry(game_id, dataset_id, version, verified, sources, {"version_raw": version, **raw})
            items[version] = item
        else:
            item["last_verified_at"] = max(item["last_verified_at"], verified)
            item["provenance"].extend({"source_id": source_id, "retrieved_at": verified, "method": "import"} for source_id in sources)
        if raw.get("date") and "release_date" not in item:
            item["release_date"] = date_only(raw["date"])
        if raw.get("channel") in {"release", "beta", "preview", "snapshot", "alpha", "nightly", "old"}:
            item["channel"] = raw["channel"]


def build_stardew(registry: SourceRegistry) -> list[dict]:
    raw_doc = read_json(SNAP / "stardew.json")
    history = read_json(SNAP / "game_history.json")
    verified = iso(raw_doc.get("generated"))
    stardew_history_sources = history_sources(registry, history).get("stardew", [])
    items: dict[str, dict] = {}
    sources: list[str] = []
    for raw in raw_doc.get("versions") or []:
        version = str(raw.get("v") or "unknown")
        source_ids = [registry.offer_source(value, "https://example.invalid/", verified) for value in raw.get("sources") or ["stardew"]]
        sources.extend(source_ids)
        item = entry("stardew-valley", "stardew-valley-android", version, verified, source_ids, {**raw, "version_raw": (raw.get("meta") or {}).get("raw", version)})
        for index, raw_offer in enumerate(raw.get("offers") or []):
            source_id = registry.offer_source(raw_offer.get("source", "stardew"), raw_offer.get("url", "https://example.invalid/"), verified)
            item.setdefault("offers", []).append(map_offer(raw_offer, source_id, verified, index, f"stardew-valley-android:{version}"))
        items[version] = item
    merge_history(items, "stardew-valley", "stardew-valley-android", history, "stardew", "android", stardew_history_sources)
    android_dataset = dataset("stardew-valley-android", "stardew-valley", "星露谷物语 Android", "mobile", "Android", verified, sources + stardew_history_sources, finalize(items))
    pc_history: dict[str, dict] = {}
    merge_history(pc_history, "stardew-valley", "stardew-valley-pc", history, "stardew", "pc", stardew_history_sources)
    pc_dataset = dataset("stardew-valley-pc", "stardew-valley", "星露谷物语 PC 版本记录", "desktop", "Windows/macOS/Linux", iso(history.get("generated")), stardew_history_sources, finalize(pc_history))
    return [android_dataset, pc_dataset]


def build_non_minecraft(registry: SourceRegistry) -> list[dict]:
    atom = read_json(SNAP / "atomlib.json")
    history = read_json(SNAP / "game_history.json")
    verified = iso(atom.get("generated"))
    history_ids = history_sources(registry, history)
    nullatom = registry.add("nullatom", "NullAtom 原子资源", (atom.get("source") or {}).get("site", "https://example.invalid/"), "api", verified)
    defaults = {
        "terraria": {
            "client-android": ("terraria-mobile", "泰拉瑞亚 Android", "mobile", "Android"),
            "client-windows": ("terraria-desktop", "泰拉瑞亚桌面版", "desktop", "Windows"),
            "server-pc": ("terraria-server-pc", "泰拉瑞亚原版 PC 服务端", "server", "Windows/Linux"),
            "server-mobile": ("terraria-server-mobile", "泰拉瑞亚手机版服务端", "server", "Android"),
            "server-tmodloader": ("terraria-server-tmodloader", "泰拉瑞亚 tModLoader 服务端", "server", "desktop"),
            "server-tshock": ("terraria-server-tshock", "泰拉瑞亚 TShock 服务端", "server", "desktop"),
            "server-tshock-atomcraft": ("terraria-server-atomcraft", "泰拉瑞亚 AtomCraft 服务端", "server", "desktop"),
        },
        "rustedwarfare": {
            "client-android": ("rusted-warfare-android", "铁锈战争 Android", "mobile", "Android"),
            "server-rwhps": ("rusted-warfare-server", "铁锈战争 RW-HPS 服务端", "server", "Java"),
        },
    }
    output = []
    for source_game, game_id in (("terraria", "terraria"), ("rustedwarfare", "rusted-warfare")):
        for group in (atom.get("libraries") or {}).get(source_game, {}).get("groups") or []:
            key = group.get("key") or slug(group.get("label", "group"))
            dataset_id, name, family, os_name = defaults[source_game].get(key, (f"{game_id}-{slug(key)}", f"{game_id} {key}", "unknown", "unknown"))
            items: dict[str, dict] = {}
            for index, raw_file in enumerate(group.get("files") or []):
                version = str(raw_file.get("version") or "unknown")
                item = items.setdefault(version, entry(game_id, dataset_id, version, verified, [nullatom], {"version_raw": version, "channel": "unknown"}))
                raw_offer = {**raw_file, "kind": "page", "scope": "file", "provider": "NullAtom 原站页", "note": raw_file.get("note") or raw_file.get("name")}
                item.setdefault("offers", []).append(map_offer(raw_offer, nullatom, verified, index, f"{dataset_id}:{version}"))
            if source_game == "terraria" and key in {"client-android", "client-windows"}:
                merge_history(items, game_id, dataset_id, history, source_game, "mobile" if key == "client-android" else "desktop", history_ids.get(source_game, []))
            output.append(dataset(dataset_id, game_id, name, family, os_name, verified, [nullatom], finalize(items)))
    rw_history: dict[str, dict] = {}
    merge_history(rw_history, "rusted-warfare", "rusted-warfare-history", history, "rustedwarfare", "all", history_ids.get("rustedwarfare", []))
    output.append(dataset("rusted-warfare-history", "rusted-warfare", "铁锈战争版本记录", "unknown", "多平台", iso(history.get("generated")), history_ids.get("rustedwarfare", []), finalize(rw_history)))
    return output


def build() -> dict:
    registry = SourceRegistry()
    datasets = build_stardew(registry) + build_non_minecraft(registry)
    times = [dataset["last_verified_at"] for dataset in datasets for _ in [0]] + [entry["last_verified_at"] for dataset in datasets for entry in dataset["entries"]]
    generated_at = max(times or [NOW_FALLBACK])
    catalog = {
        "schema_version": "1.0.0",
        "catalog_id": "non-minecraft-game-version-library",
        "generated_at": generated_at,
        "last_verified_at": min(times or [generated_at]),
        "license": license_block(),
        "provenance": {
            "pipeline": {"name": "non-minecraft-game-version-library-builder", "version": "1.0.0"},
            "sources": sorted(registry.items.values(), key=lambda value: value["source_id"]),
            "notes": "Minecraft is intentionally excluded from this public repository.",
        },
        "datasets": sorted(datasets, key=lambda value: value["dataset_id"]),
    }
    OUT.write_text(json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return catalog


if __name__ == "__main__":
    result = build()
    print(f"wrote {OUT}")
    print(f"datasets={len(result['datasets'])} entries={sum(len(x['entries']) for x in result['datasets'])} offers={sum(len(e.get('offers', [])) for x in result['datasets'] for e in x['entries'])} sources={len(result['provenance']['sources'])}")
