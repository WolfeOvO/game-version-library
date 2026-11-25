#!/usr/bin/env python3
"""Render the normalized non-Minecraft catalog as portable Markdown pages."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/catalog.json"
OUT = ROOT / "docs"
GAME_ORDER = ("stardew-valley", "terraria", "rusted-warfare")
LABELS = {"stardew-valley": "星露谷物语", "terraria": "泰拉瑞亚", "rusted-warfare": "铁锈战争"}


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


def render_table(entries: list[dict]) -> list[str]:
    rows = []
    for entry in entries:
        rows.append("| " + " | ".join([
            f"`{esc(entry['version'])}`",
            esc(entry.get("channel")),
            esc(entry.get("release_date") or "—"),
            esc(entry.get("availability")),
            offer_links(entry),
        ]) + " |")
    return ["| 版本 | 渠道 | 发布日期 | 可用性 | 来源 / 入口 |", "| --- | --- | --- | --- | --- |", *rows]


def render_dataset(dataset: dict) -> str:
    entries = dataset.get("entries") or []
    lines = [
        f"# {dataset['name']}",
        "",
        f"游戏标识：`{dataset['game_id']}` · 平台：`{dataset['platform_id']}`",
        "",
        f"共 {len(entries)} 条记录。",
        "",
    ]
    if dataset["game_id"] == "terraria":
        label = "客户端" if dataset["dataset_id"] in {"terraria-mobile", "terraria-desktop"} else "服务端与模组服务端"
        if entries:
            lines.extend([f"## {label}", "", *render_table(entries), ""])
    else:
        lines.extend(render_table(entries))
    return "\n".join(lines).rstrip() + "\n"


def dataset_route(dataset: dict) -> str:
    return f"{dataset['game_id']}/{slug(dataset['dataset_id'])}/"


def render_home(catalog: dict) -> str:
    datasets = catalog.get("datasets") or []
    cards = []
    for game_id in GAME_ORDER:
        items = [dataset for dataset in datasets if dataset["game_id"] == game_id]
        if not items:
            continue
        all_entries = [entry for dataset in items for entry in dataset.get("entries", [])]
        latest = all_entries[0].get("version") if all_entries else "暂无记录"
        links = []
        for dataset in items:
            route = dataset_route(dataset)
            links.append(
                '<li><a href="' + html.escape(route, quote=True) + '">' + html.escape(dataset["name"]) + '</a>'
                + f' · {len(dataset.get("entries") or [])} 条</li>'
            )
        route = dataset_route(items[0])
        cards.append(
            '<li class="ore-resource-card">'
            '<div class="ore-resource-head"><span class="ore-resource-icon" aria-hidden="true">'
            '<svg viewBox="0 0 24 24"><path fill="currentColor" d="M4 4h7v7H4zm9 0h7v7h-7zM4 13h7v7H4zm9 0h7v7h-7z"/></svg></span>'
            '<div class="ore-resource-identity"><div class="ore-resource-title"><a href="'
            + html.escape(route, quote=True) + '">' + html.escape(LABELS[game_id]) + '</a></div>'
            + '<span class="ore-resource-host">' + html.escape(game_id) + '</span></div></div>'
            + '<div class="ore-resource-description"><p>最新目录记录：<strong>' + html.escape(str(latest))
            + f'</strong> · {len(all_entries)} 条记录 · {len(items)} 个数据集</p></div>'
            + f'<div class="ore-resource-tags"><span class="ore-resource-tag">{len(items)} 个平台/类型</span><span class="ore-resource-tag">JSON 目录</span></div>'
            + '<div class="ore-resource-links"><ul>' + "".join(links) + '</ul></div></li>'
        )
    return "\n".join([
        "# 游戏版本库",
        "",
        "开源发行版仅包含星露谷物语、泰拉瑞亚与铁锈战争；Minecraft 数据和私有部署源码不在本仓库中。",
        "",
        '<div class="ore-catalog" data-ore-catalog data-catalog-view="cards">',
        '<div class="ore-catalog-toolbar" data-catalog-toolbar><span class="ore-catalog-label">目录显示</span>',
        '<div class="ore-catalog-switch" role="group" aria-label="目录显示方式">',
        '<button type="button" data-catalog-view="cards" aria-pressed="true">卡片</button>',
        '<button type="button" data-catalog-view="list" aria-pressed="false">列表</button></div></div>',
        '<ul class="ore-resource-grid">' + "".join(cards) + '</ul></div>',
        "",
        "## 数据口径",
        "",
        "版本原文、规范化版本、渠道和发布日期按来源保留。下载入口跳转到上游；访问状态不等于对文件内容的独立安全背书。",
        "",
        "数据 Schema、采集器和网站构建配置均见 [GitHub 开源仓库](https://github.com/WolfeOvO/game-version-library)。",
        "",
    ]).rstrip() + "\n"


def main() -> int:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    search_index = []
    datasets = sorted(catalog.get("datasets") or [], key=lambda item: (GAME_ORDER.index(item["game_id"]) if item["game_id"] in GAME_ORDER else len(GAME_ORDER), item["dataset_id"]))
    expected_paths = {Path(*dataset_route(dataset).rstrip("/").split("/")) / "index.md" for dataset in datasets}
    for game_id in GAME_ORDER:
        game_root = OUT / game_id
        if not game_root.exists():
            continue
        for old_page in game_root.rglob("*.md"):
            if old_page.relative_to(OUT) not in expected_paths:
                old_page.unlink()
        for directory in sorted((path for path in game_root.rglob("*") if path.is_dir()), reverse=True):
            if not any(directory.iterdir()):
                directory.rmdir()
    for dataset in datasets:
        route = dataset_route(dataset)
        markdown_path = OUT / dataset["game_id"] / f"{slug(dataset['dataset_id'])}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_dataset(dataset), encoding="utf-8")
        search_index.append({"title": dataset["name"], "location": route})
        for version in dataset.get("entries") or []:
            search_index.append({"title": f"{LABELS.get(dataset['game_id'], dataset['game_id'])} {version['version']}", "location": route})
    (OUT / "index.md").write_text(render_home(catalog), encoding="utf-8")
    search_index.append({"title": "非 Minecraft 游戏版本库", "location": ""})
    (OUT / "search").mkdir(parents=True, exist_ok=True)
    (OUT / "search/ore-index.json").write_text(json.dumps(search_index, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"rendered datasets={len(datasets)} search_records={len(search_index)} into {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
