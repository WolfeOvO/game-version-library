#!/usr/bin/env python3
"""Build the public, schema-first catalog from audited source snapshots.

The input snapshots are kept separate from the public normalized catalog so the
normalization is reproducible and the public schema remains stable.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "source-snapshots"
OUT = ROOT / "data" / "catalog.json"

GAME_IDS = {"minecraft", "stardew-valley", "terraria", "rusted-warfare"}
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
    if not value:
        return None
    text = str(value).strip()
    return text[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", text) else None


def slug(value: str, prefix: str = "item") -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    if text:
        return text[:100]
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def stable_id(*parts: object, prefix: str = "item") -> str:
    joined = "-".join(str(part) for part in parts if part is not None and str(part) != "")
    return slug(joined, prefix=prefix)


def digest_id(*parts: object, prefix: str = "item") -> str:
    joined = "\x1f".join(str(part) for part in parts)
    return f"{slug(prefix, prefix)}-{hashlib.sha256(joined.encode('utf-8')).hexdigest()[:20]}"


def source_kind(source_id: str) -> str:
    if source_id in {"mojang", "mojang-manifest"}:
        return "manifest"
    if source_id in {"bmclapi", "fastmirror"}:
        return "repository"
    if source_id in {"mcdl", "mcdwei", "mcapks", "mcappx", "spectro"}:
        return "api"
    return "import"


def source_url_from_offer(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}/"
    return "https://example.invalid/"


class SourceRegistry:
    def __init__(self) -> None:
        self.items: dict[str, dict] = {}

    def add(
        self,
        source_id: str,
        name: str,
        url: str,
        kind: str,
        retrieved_at: str,
        terms_url: str | None = None,
        notes: str = "",
    ) -> str:
        key = stable_id(source_id, prefix="source")
        item = self.items.get(key)
        if item is None:
            item = {
                "source_id": key,
                "name": name or key,
                "url": url or "https://example.invalid/",
                "kind": kind,
                "retrieved_at": iso(retrieved_at),
            }
            self.items[key] = item
        else:
            item["retrieved_at"] = max(item["retrieved_at"], iso(retrieved_at))
            if item["url"] == "https://example.invalid/" and url:
                item["url"] = url
        if terms_url:
            item["terms_url"] = terms_url
        if notes:
            item["notes"] = notes
        return key

    def ensure_offer_source(self, source_id: str, offer_url: str, retrieved_at: str) -> str:
        key = stable_id(source_id, prefix="source")
        if key not in self.items:
            self.add(key, source_id, source_url_from_offer(offer_url), source_kind(source_id), retrieved_at)
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


def checksum_items(item: dict) -> list[dict]:
    algorithm = str(item.get("checksum_type") or "").lower()
    value = str(item.get("checksum") or "")
    if algorithm in {"md5", "sha1", "sha256", "sha512", "blake3"} and re.fullmatch(r"[0-9a-fA-F]{32,128}", value):
        return [{"algorithm": algorithm, "value": value}]
    return []


def map_offer(raw: dict, source_id: str, verified_at: str, index: int, context: str = "") -> dict:
    kind = str(raw.get("kind") or "metadata")
    kind_map = {"file": "direct", "link": "direct", "netdisk": "share"}
    kind = kind_map.get(kind, kind if kind in {"official", "direct", "mirror", "share", "page", "directory", "api", "metadata"} else "metadata")
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
    }
    if raw.get("provider"):
        offer["provider"] = str(raw["provider"])
    if raw.get("arch"):
        offer["architecture"] = str(raw["arch"])
    if raw.get("note"):
        offer["label"] = str(raw["note"])
    if isinstance(raw.get("size"), int) and raw["size"] >= 0:
        offer["size_bytes"] = raw["size"]
    checksums = checksum_items(raw)
    if checksums:
        offer["checksums"] = checksums
    access_mode = str(raw.get("access_mode") or "")
    if access_mode not in {"public", "password", "account", "signed", "unknown"}:
        access_mode = "password" if raw.get("password") else "public"
    offer["access"] = {"mode": access_mode}
    return offer


def entry(game_id: str, dataset_id: str, version: str, verified_at: str, source_ids: list[str], raw: dict | None = None) -> dict:
    raw = raw or {}
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
        "provenance": [
            {"source_id": source_id, "retrieved_at": verified_at, "method": "import"}
            for source_id in sorted(set(source_ids))
        ],
    }
    major = raw.get("major")
    if major:
        item["major"] = str(major)
    release_date = date_only(raw.get("release_date") or raw.get("released") or raw.get("date"))
    if release_date:
        item["release_date"] = release_date
    if raw.get("notes"):
        notes = raw["notes"] if isinstance(raw["notes"], str) else " ".join(str(x) for x in raw["notes"])
        if notes:
            item["notes"] = notes
    return item


def add_offer_to_entry(item: dict, offer: dict) -> None:
    item.setdefault("offers", []).append(offer)
    item["availability"] = "downloadable"


def finalize_entries(items: dict[str, dict]) -> list[dict]:
    for item in items.values():
        offers = item.get("offers") or []
        if offers:
            unique = {offer["offer_id"]: offer for offer in offers}
            item["offers"] = [unique[key] for key in sorted(unique)]
            item["availability"] = "downloadable"
        item["provenance"] = sorted(item["provenance"], key=lambda x: (x["source_id"], x["method"]))
    return sorted(items.values(), key=lambda x: (x.get("version_normalized", ""), x["entry_id"]), reverse=True)


def new_dataset(dataset_id: str, game_id: str, platform_id: str, name: str, platform: dict, verified_at: str, source_ids: list[str]) -> dict:
    return {
        "dataset_id": dataset_id,
        "game_id": game_id,
        "platform_id": platform_id,
        "name": name,
        "platform": platform,
        "last_verified_at": verified_at,
        "license": license_block(),
        "provenance": {"source_ids": sorted(set(source_ids)), "method": "import", "retrieved_at": verified_at},
        "entries": [],
    }


def add_history_sources(registry: SourceRegistry, history: dict, generated_at: str) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for game_id, game in (history.get("games") or {}).items():
        ids = []
        for source in game.get("sources") or []:
            source_id = registry.add(
                f"history-{game_id}-{source.get('label', '')}",
                source.get("label") or f"{game_id} history",
                source.get("url") or "https://example.invalid/",
                "official" if "官方" in str(source.get("label")) or "Wiki" in str(source.get("label")) else "web",
                generated_at,
            )
            ids.append(source_id)
        mapping[game_id] = ids or [registry.add(f"history-{game_id}", f"{game_id} history", "https://example.invalid/", "import", generated_at)]
    return mapping


def build_minecraft(registry: SourceRegistry) -> list[dict]:
    catalog = read_json(SNAP / "minecraft" / "catalog.json")
    generated_at = iso(catalog.get("generated"))
    for raw in catalog.get("sources") or []:
        registry.add(raw.get("key", "source"), raw.get("name", raw.get("key", "source")), raw.get("homepage", "https://example.invalid/"), source_kind(raw.get("key", "source")), raw.get("last_sync") or generated_at)
    datasets = []
    platform_meta = {
        "java": ("minecraft-java", "Minecraft Java 版", "Minecraft Java 版", "desktop", "Java"),
        "android": ("minecraft-bedrock-android", "Minecraft 基岩版 Android", "Minecraft 基岩版", "mobile", "Android"),
        "ios": ("minecraft-bedrock-ios", "Minecraft 基岩版 iOS", "Minecraft 基岩版", "mobile", "iOS"),
        "windows": ("minecraft-bedrock-windows", "Minecraft 基岩版 Windows", "Minecraft 基岩版", "desktop", "Windows"),
    }
    for device, (dataset_id, name, display, family, os_name) in platform_meta.items():
        doc = read_json(SNAP / "minecraft" / f"{device}.json")
        verified_at = iso(doc.get("generated") or generated_at)
        source_ids = []
        items: dict[str, dict] = {}
        for raw_version in doc.get("versions") or []:
            raw_sources = [registry.ensure_offer_source(x, "https://example.invalid/", verified_at) for x in raw_version.get("sources") or []]
            source_ids.extend(raw_sources)
            version = str(raw_version.get("v") or "unknown")
            item = entry("minecraft", dataset_id, version, verified_at, raw_sources or [registry.add("unknown-minecraft", "Unknown Minecraft source", "https://example.invalid/", "import", verified_at)], {**raw_version, "version_raw": (raw_version.get("meta") or {}).get("raw", version)})
            for index, raw_offer in enumerate(raw_version.get("offers") or []):
                offer_source = registry.ensure_offer_source(raw_offer.get("source", "unknown-minecraft"), raw_offer.get("url", "https://example.invalid/"), verified_at)
                add_offer_to_entry(item, map_offer(raw_offer, offer_source, verified_at, index, f"{dataset_id}:{version}"))
            items[item["entry_id"]] = item
        platform = {"display_name": display + " · " + os_name if device != "java" else display, "family": family, "os": os_name}
        if device == "java":
            platform["architectures"] = ["any"]
        dataset = new_dataset(dataset_id, "minecraft", dataset_id, name, platform, verified_at, source_ids or [registry.add("unknown-minecraft", "Unknown Minecraft source", "https://example.invalid/", "import", verified_at)])
        dataset["entries"] = finalize_entries(items)
        datasets.append(dataset)
    return datasets


def add_history_entries(dataset: dict, game_id: str, platform_key: str, history: dict, history_sources: dict[str, list[str]], source_ids: list[str], history_game_id: str | None = None) -> None:
    history_game_id = history_game_id or game_id
    game = (history.get("games") or {}).get(history_game_id) or {}
    platform = next((p for p in game.get("platforms") or [] if p.get("key") == platform_key), None)
    if not platform:
        return
    verified_at = iso(history.get("generated"))
    items = {item["version"]: item for item in dataset.get("entries") or []}
    source_ids = source_ids or history_sources.get(history_game_id, [])
    for raw in platform.get("versions") or []:
        version = str(raw.get("v") or "unknown")
        item = items.get(version)
        if item is None:
            item = entry(game_id, dataset["dataset_id"], version, verified_at, source_ids, {"version_raw": version, **raw})
            items[version] = item
        else:
            item["last_verified_at"] = max(item["last_verified_at"], verified_at)
            item["provenance"].extend({"source_id": source_id, "retrieved_at": verified_at, "method": "import"} for source_id in source_ids)
        if raw.get("date") and "release_date" not in item:
            item["release_date"] = date_only(raw.get("date"))
        if raw.get("channel") in {"release", "beta", "preview", "snapshot", "alpha", "nightly", "old"}:
            item["channel"] = raw["channel"]
    dataset["entries"] = finalize_entries(items)
    dataset["last_verified_at"] = max(dataset["last_verified_at"], verified_at)


def build_non_minecraft(registry: SourceRegistry) -> list[dict]:
    atom = read_json(SNAP / "non-minecraft" / "atomlib.json")
    history = read_json(SNAP / "non-minecraft" / "game_history.json")
    atom_verified = iso(atom.get("generated"))
    history_sources = add_history_sources(registry, history, iso(history.get("generated")))
    nullatom = registry.add("nullatom", "NullAtom 原子资源", (atom.get("source") or {}).get("site", "https://example.invalid/"), "api", atom_verified)
    datasets: list[dict] = []
    platform_defaults = {
        "terraria": {"client-android": ("terraria-mobile", "泰拉瑞亚 Android", "mobile", "Android"), "client-windows": ("terraria-desktop", "泰拉瑞亚桌面版", "desktop", "Windows"), "server-pc": ("terraria-server-pc", "泰拉瑞亚原版 PC 服务端", "server", "Windows/Linux"), "server-pe": ("terraria-server-mobile", "泰拉瑞亚手机版服务端", "server", "Android"), "server-tmodloader": ("terraria-server-tmodloader", "泰拉瑞亚 tModLoader 服务端", "server", "desktop"), "server-tshock": ("terraria-server-tshock", "泰拉瑞亚 TShock 服务端", "server", "desktop"), "server-atomcraft": ("terraria-server-atomcraft", "泰拉瑞亚 AtomCraft 服务端", "server", "desktop")},
        "rustedwarfare": {"android": ("rusted-warfare-android", "铁锈战争 Android", "mobile", "Android"), "server-rw-hps": ("rusted-warfare-server", "铁锈战争 RW-HPS 服务端", "server", "Java")},
    }
    for game_key in ("terraria", "rustedwarfare"):
        game_id = "rusted-warfare" if game_key == "rustedwarfare" else game_key
        lib = (atom.get("libraries") or {}).get(game_key) or {}
        for group in lib.get("groups") or []:
            key = group.get("key") or slug(group.get("label", "group"))
            defaults = platform_defaults[game_key]
            dataset_id, name, family, os_name = defaults.get(key, (f"{game_id}-{slug(key)}", f"{game_id} {group.get('label', key)}", "unknown", "unknown"))
            items: dict[str, dict] = {}
            for index, raw_file in enumerate(group.get("files") or []):
                version = str(raw_file.get("version") or "unknown")
                item = items.get(version)
                if item is None:
                    item = entry(game_id, dataset_id, version, atom_verified, [nullatom], {"version_raw": version, "channel": "unknown"})
                    items[version] = item
                raw_offer = {**raw_file, "kind": "page", "scope": "file", "source": "nullatom", "provider": "NullAtom 原站页", "note": raw_file.get("note") or raw_file.get("name")}
                add_offer_to_entry(item, map_offer(raw_offer, nullatom, atom_verified, index, f"{dataset_id}:{version}"))
            platform = {"display_name": name, "family": family, "os": os_name}
            dataset = new_dataset(dataset_id, game_id, dataset_id, name, platform, atom_verified, [nullatom])
            dataset["entries"] = finalize_entries(items)
            if game_key == "terraria" and key in {"client-android", "client-windows"}:
                history_key = "mobile" if key == "client-android" else "desktop"
                add_history_entries(dataset, game_id, history_key, history, history_sources, history_sources.get(game_key, []), history_game_id=game_key)
            elif game_key == "rustedwarfare":
                add_history_entries(dataset, game_id, "all", history, history_sources, history_sources.get(game_key, []), history_game_id=game_key)
            datasets.append(dataset)
    return datasets


def build_stardew(registry: SourceRegistry) -> list[dict]:
    doc = read_json(SNAP / "minecraft" / "stardew.json")
    verified_at = iso(doc.get("generated"))
    items: dict[str, dict] = {}
    source_ids: list[str] = []
    for raw_version in doc.get("versions") or []:
        raw_sources = [registry.ensure_offer_source(x, "https://example.invalid/", verified_at) for x in raw_version.get("sources") or []]
        source_ids.extend(raw_sources)
        version = str(raw_version.get("v") or "unknown")
        item = entry("stardew-valley", "stardew-valley-android", version, verified_at, raw_sources, {**raw_version, "version_raw": (raw_version.get("meta") or {}).get("raw", version)})
        for index, raw_offer in enumerate(raw_version.get("offers") or []):
            offer_source = registry.ensure_offer_source(raw_offer.get("source", "stardew"), raw_offer.get("url", "https://example.invalid/"), verified_at)
            add_offer_to_entry(item, map_offer(raw_offer, offer_source, verified_at, index, f"stardew-valley-android:{version}"))
        items[item["entry_id"]] = item
    dataset = new_dataset("stardew-valley-android", "stardew-valley", "stardew-valley-android", "星露谷物语 Android", {"display_name": "星露谷物语 Android", "family": "mobile", "os": "Android"}, verified_at, source_ids or [registry.add("stardew", "星露谷版本库", "https://example.invalid/", "import", verified_at)])
    dataset["entries"] = finalize_entries(items)
    return [dataset]


def build() -> dict:
    registry = SourceRegistry()
    datasets = build_minecraft(registry) + build_stardew(registry) + build_non_minecraft(registry)
    all_times = [dataset["last_verified_at"] for dataset in datasets]
    all_times.extend(entry["last_verified_at"] for dataset in datasets for entry in dataset["entries"])
    generated_at = max(all_times or [NOW_FALLBACK])
    catalog = {
        "schema_version": "1.0.0",
        "catalog_id": "game-version-library",
        "generated_at": generated_at,
        "last_verified_at": generated_at,
        "license": license_block(),
        "provenance": {
            "pipeline": {"name": "game-version-library-catalog-builder", "version": "1.0.0"},
            "sources": sorted(registry.items.values(), key=lambda x: x["source_id"]),
            "notes": "Generated from audited source snapshots; raw package files are not included.",
        },
        "datasets": sorted(datasets, key=lambda x: x["dataset_id"]),
    }
    OUT.write_text(json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return catalog


if __name__ == "__main__":
    catalog = build()
    entries = sum(len(dataset["entries"]) for dataset in catalog["datasets"])
    offers = sum(len(entry.get("offers") or []) for dataset in catalog["datasets"] for entry in dataset["entries"])
    print(f"wrote {OUT}")
    print(f"datasets={len(catalog['datasets'])} entries={entries} offers={offers} sources={len(catalog['provenance']['sources'])}")
