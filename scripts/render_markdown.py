#!/usr/bin/env python3
"""Render the normalized catalog as portable Markdown pages."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/catalog.json"
OUT = ROOT / "rendered"

LABELS = {
    "stardew-valley": "星露谷物语",
    "terraria": "泰拉瑞亚",
    "rusted-warfare": "铁锈战争",
}


def esc(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-") or "dataset"


def offer_links(entry: dict) -> str:
    links = []
    for offer in entry.get("offers") or []:
        label = offer.get("provider") or offer.get("kind") or "来源"
        mode = (offer.get("access") or {}).get("mode")
        suffix = f"（{mode}）" if mode and mode != "public" else ""
        links.append(f"[{esc(label)}{suffix}]({offer['url']})")
    return "<br>".join(links) or "—"


def render_dataset(dataset: dict) -> str:
    title = dataset["name"]
    lines = [f"# {title}", "", f"游戏标识：`{dataset['game_id']}` · 平台：`{dataset['platform_id']}`", "", "| 版本 | 渠道 | 发布日期 | 可用性 | 来源 / 入口 |", "| --- | --- | --- | --- | --- |"]
    for entry in dataset.get("entries") or []:
        lines.append("| " + " | ".join([
            f"`{esc(entry['version'])}`",
            esc(entry.get("channel")),
            esc(entry.get("release_date") or "—"),
            esc(entry.get("availability")),
            offer_links(entry),
        ]) + " |")
    return "\n".join(lines) + "\n"


def main() -> int:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    index = ["# 非 Minecraft 游戏版本库", "", "本目录由 `scripts/build_catalog.py` 生成。", ""]
    for dataset in catalog["datasets"]:
        game = LABELS.get(dataset["game_id"], dataset["game_id"])
        path = OUT / dataset["game_id"] / f"{slug(dataset['dataset_id'])}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_dataset(dataset), encoding="utf-8")
        rel = path.relative_to(OUT).as_posix()
        index.append(f"- [{html.escape(dataset['name'])}]({rel}) · `{dataset['game_id']}` · {len(dataset['entries'])} 条")
    (OUT / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"rendered datasets={len(catalog['datasets'])} into {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
