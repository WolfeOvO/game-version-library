#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""非 Minecraft 游戏的版本记录：从各游戏官方 Wiki / 更新日志抓取并归一化。

数据源（2026-10-30 确认）：

| 游戏 | 官方来源 | 页面 |
| --- | --- | --- |
| 泰拉瑞亚 | Terraria Wiki（terraria.wiki.gg，官方 Wiki） | 中文子站「电脑版版本历史」「移动版版本历史」「主机版版本历史」 |
| 星露谷物语 | Stardew Valley Wiki（官方 Wiki） | 中文站「版本历史」「移动版历史」「主机版历史」 |
| 铁锈战争 | Corroding Games 官方 changelog + Steam 官方公告 | corrodinggames.com/rusted_warfare_changelog、appid 647960 |

星露谷官方 Wiki 在 Cloudflare 后面，python-requests 拿不到（403 Just a moment）。
原始 wikitext 因此走浏览器缓存：`cache/game_wiki/stardew_{zh,en}_{0,1,2}.wiki`。
需要刷新时用浏览器（同一 wiki 域）调 `/mediawiki/api.php?action=parse&prop=wikitext`
把结果存成这三个文件，再跑本脚本 —— 解析与联网解耦，构建期不依赖外网。

用法：
    python3 scripts/wiki_game_history.py            # 抓取（能抓的）+ 解析 → data/game_history.json
    python3 scripts/wiki_game_history.py --offline  # 只用缓存，不联网
    python3 scripts/wiki_game_history.py --check    # 只打印统计，不写文件
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "source-snapshots" / "non-minecraft"
CACHE = BASE / "data" / "source-cache" / "game_wiki"
OUT = DATA / "game_history.json"

UA = "game-version-library-history/1.0 (+https://github.com/WolfeOvO/game-version-library)"
HEADERS = {"User-Agent": UA}

TR_WIKI = "https://terraria.wiki.gg/zh"
SW_WIKI = "https://zh.stardewvalleywiki.com"
RW_CHANGELOG = "https://corrodinggames.com/rusted_warfare_changelog"
RW_APPID = 647960

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

# ------------------------------------------------------------------ 通用工具


def log(msg: str) -> None:
    print(msg, flush=True)


def plain(text: str) -> str:
    """去掉 MediaWiki / HTML 标记，留下可读文本。"""
    s = text or ""
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    for _ in range(4):  # {{tr|X}}、{{version|1.6.15|PC 版 1.6.15}} 这类模板逐层剥
        s = re.sub(r"\{\{tr\|([^{}|]*)(?:\|[^{}]*)?\}\}", r"\1", s)
        s = re.sub(r"\{\{version\|([^{}|]*)(?:\|[^{}]*)?\}\}", r"\1", s)
        s = re.sub(r"\{\{(?:anchor|note|sic)\|([^{}|]*)[^{}]*\}\}", r"\1", s)
        s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^\]|]*)\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", s)
    s = re.sub(r"\[https?://\S+\]", "", s)
    s = re.sub(r"<br\s*/?>", " · ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("'''", "").replace("''", "")
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" ··；;,，、")


def iso_date(text: str) -> str:
    """把中/英文日期写法统一成 YYYY-MM-DD，认不出来就返回空串。"""
    s = plain(text)
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", s)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?\s+(\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        d, mo, y = int(m.group(1)), MONTHS[m.group(2).lower()], int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", s)
    if m and m.group(1).lower() in MONTHS:
        mo, d, y = MONTHS[m.group(1).lower()], int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.search(r"^(\d{4})$", s)
    if m:
        return f"{m.group(1)}-01-01"
    return ""


def vkey(v: str) -> tuple:
    """版本号排序键：4.5.8 → (4,5,8)，非数字段按 0 处理。"""
    parts = []
    for p in re.split(r"[.\-_ ]", str(v)):
        m = re.match(r"^(\d+)", p)
        parts.append(int(m.group(1)) if m else 0)
    return tuple(parts)


def major(v: str) -> str:
    parts = str(v).split(".")
    return ".".join(parts[:2]) if len(parts) > 1 else str(v)


def fetch(url: str, params=None, timeout=90) -> str:
    r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text


def wiki_wikitext(base: str, page: str) -> str:
    txt = fetch(base + "/api.php", {"action": "parse", "page": page,
                                    "prop": "wikitext", "format": "json",
                                    "formatversion": "2"})
    j = json.loads(txt)
    if "parse" not in j:
        raise RuntimeError(f"{base} {page}: {json.dumps(j, ensure_ascii=False)[:300]}")
    return j["parse"]["wikitext"]


# ------------------------------------------------------------------ 泰拉瑞亚


def terraria_desktop(wikitext: str) -> list[dict]:
    """桌面版是普通表格：版本 / 发布日期 / 名称 / 亮点和备注。"""
    out = []
    for m in re.finditer(
            r"\|\s*\{\{anchor\|([^}]+)\}\}\s*'''\[\[([^\]|]+)(?:\|[^\]]*)?\]\]'''\s*\n"
            r"\|\s*([^\n]*)\n"
            r"\|\s*([^\n]*)\n"
            r"\|\s*([^\n]*)", wikitext):
        anchor, link, date_raw, name, notes = m.groups()
        ver = plain(anchor) or plain(link)
        out.append({
            "v": ver,
            "date": iso_date(date_raw),
            "name": plain(name),
            "notes": [plain(notes)] if plain(notes) else [],
            "wiki": f"{TR_WIKI}/wiki/{urllib.parse.quote(link)}",
            "channel": "release",
        })
    return out


def _row_params(block: str) -> dict:
    """解析 {{/row ...}} 的参数（同名参数后面的覆盖前面的）。"""
    params = {}
    for m in re.finditer(r"^\|\s*([^=\n]+?)\s*=\s*(.*)$", block, re.M):
        params[m.group(1).strip()] = m.group(2).strip()
    return params


def _clean_changes(raw: str, limit: int = 3) -> list[str]:
    s = re.sub(r"\{\{collapse top[^}]*\}\}", "", raw or "")
    s = s.replace("{{collapse bottom}}", "")
    s = re.sub(r"\{\{forums thread\|[^}]*\}\}", "", s)
    items = []
    for line in s.split("\n"):
        line = line.strip()
        if line.startswith("*"):
            text = plain(line.lstrip("*").strip())
            if text and len(text) > 3:
                items.append(text)
        if len(items) >= limit:
            break
    return items


STORE_LABEL = {"ios": "iOS", "amazon": "Amazon", "winphone": "Windows Phone",
               "stadia": "Stadia", "googleplay": "Google Play"}


def terraria_mobile(wikitext: str) -> list[dict]:
    """移动版是 {{/row}} 模板，同一发布分 Google Play / Amazon / iOS 三个版本号。

    只收**有 Google Play 版本号**的行（本站下载页只有 Android APK）：
    平台写 `stadia` 或只有 `v-winphone` / `v-amazon` 的行会跳过 —— 否则同一个
    1.4.3.2.3 会既当 Stadia 又当 Android 出现两次（2026-10-30 踩过）。
    """
    out = []
    for m in re.finditer(r"\{\{/\s*row(.*?)\n\}\}", wikitext, re.S):
        block = m.group(1)
        p = _row_params(block)
        vmap = {k[2:]: re.sub(r"\s*\(Build[^)]*\)\s*$", "", plain(v), flags=re.I).strip()
                for k, v in p.items() if k.startswith("v-")}
        vmap = {k: v for k, v in vmap.items() if v}
        vmain = re.sub(r"\s*\(Build[^)]*\)\s*$", "", plain(p.get("v", "")), flags=re.I).strip()
        plat = plain(p.get("platform", "")).replace(" ", "")
        # 键名有单平台、也有合并写法（ios-googleplay、googleplay-amazon、
        # ios-googleplay-amazon），统一按「键里是否含 googleplay 段」判断
        google = next((val for key, val in vmap.items()
                       if "googleplay" in key.split("-") and val), "")
        if not google and "googleplay" in plat.split("/"):
            google = vmain
        if not google:
            continue
        date = ""
        for key in ("date", "date-googleplay", "date-ios-googleplay", "date-android"):
            if p.get(key):
                date = iso_date(p[key])
                if date:
                    break
        if not date:
            for k, v in p.items():
                if k.startswith("date") and "googleplay" in k.split("-"):
                    date = iso_date(v)
                    if date:
                        break
        if not date:
            for k, v in p.items():
                if k.startswith("date"):
                    date = iso_date(v)
                    if date:
                        break
        others = {}
        for key, val in vmap.items():
            if "googleplay" in key.split("-") or val == google:
                continue
            for part in key.split("-"):
                if part in STORE_LABEL:
                    others[STORE_LABEL[part]] = val
        out.append({
            "v": google,
            "date": date,
            "name": plain(p.get("name", "")),
            "notes": _clean_changes(p.get("changes", "")),
            "wiki": f"{TR_WIKI}/wiki/%E7%A7%BB%E5%8A%A8%E7%89%88%E7%89%88%E6%9C%AC%E8%AE%B0%E5%BD%95",
            "channel": "release",
            "also": others,
        })
    return out


def build_terraria(offline: bool) -> dict:
    pages = [("desktop", "电脑版版本历史", terraria_desktop),
             ("mobile", "移动版版本历史", terraria_mobile)]
    platforms = []
    for i, (key, page, parser) in enumerate(pages):
        fn = CACHE / f"terraria_zh_{i}.wiki"
        if not fn.exists() or not offline:
            CACHE.mkdir(parents=True, exist_ok=True)
            try:
                fn.write_text(wiki_wikitext("https://terraria.wiki.gg/zh", page), encoding="utf-8")
                log(f"  terraria: 抓取 {page} -> {fn.name} ({fn.stat().st_size} B)")
            except Exception as exc:                      # 网络失败就退回旧缓存
                if not fn.exists():
                    raise
                log(f"  terraria: 抓取 {page} 失败（{exc}），用缓存 {fn.name}")
        versions = parser(fn.read_text(encoding="utf-8"))
        # 来源页面本身就是「新 → 旧」，不再重排：按版本号排会把 1.051 / 1.4.5.8.1
        # 这类老号或带构建号的版本排错位。
        label = ("桌面版（Windows / macOS / Linux）" if key == "desktop"
                 else "移动版（Android · Google Play）")
        platforms.append({
            "key": key,
            "label": label,
            "wiki": f"{TR_WIKI}/wiki/{urllib.parse.quote(page)}",
            "versions": versions,
        })
    return {
        "title": "泰拉瑞亚",
        "lead": ("泰拉瑞亚由 Re-Logic 开发。桌面版与移动版的版本线不同：桌面版由 Re-Logic 自己维护，"
                 "移动版 1.3 起由 DR Studios 移植，因此同一个大版本在两边的构建号与发布日期都不一样。"),
        "sources": [
            {"label": "Terraria Wiki（官方）", "url": TR_WIKI + "/"},
            {"label": "Steam 商店页", "url": "https://store.steampowered.com/app/105600/"},
        ],
        "note": ("Google Play 与 Amazon 商店的移动版更新路径不同（版本号、日期都不一样），"
                 "这里收录 Google Play 版本号，Amazon / iOS 版本号放在条目说明里。"
                 "主机版（Xbox / PlayStation / Switch）更新记录见 Wiki「主机版版本历史」。"),
        "platforms": platforms,
    }


# ------------------------------------------------------------------ 星露谷物语

SW_SECTION = re.compile(r"^==\s*(?!\[\[)([^=\n]+?)\s*==\s*$", re.M)


def _sw_sections(wikitext: str, level: int = 2) -> list[tuple[str, str]]:
    """按指定层级标题切段，返回 [(标题, 正文)]。

    标题里可能有 `=`（如 `==<span id="Android">…==`），所以不能用 `[^=]` 卡；
    改为「正好 level 个等号开头、同样 level 个等号结尾」，`===1.6.9===` 不会被 level=2 误吃。
    """
    pattern = re.compile(r"^(={2,6})(.+?)\1\s*$", re.M)
    found = [m for m in pattern.finditer(wikitext) if len(m.group(1)) == level]
    out = []
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(wikitext)
        out.append((m.group(2), wikitext[m.end():end]))
    return out


SW_DATE_RE = re.compile(r"(?:发布于|发布於|發佈於|released(?:\s+on)?|out\s+on)\s*(?:\[[^\]]*\])?\s*"
                        r"([0-9]{4}\s*年\s*[0-9]{1,2}\s*月\s*[0-9]{1,2}\s*日"
                        r"|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\.?,?\s+[0-9]{4}"
                        r"|[A-Za-z]{3,9}\.?\s+[0-9]{1,2},?\s+[0-9]{4})", re.I)


def _sw_body_notes(body: str, limit: int = 3) -> tuple[list[str], list[str]]:
    """`; 小节名` + `:* 条目` 结构 → (小节名列表, 前几条要点)。"""
    heads, items = [], []
    cur = ""
    for raw in body.split("\n"):
        line = raw.strip()
        if not line or line.startswith("{{") or line.startswith("<"):
            continue
        if line.startswith(";"):
            cur = plain(line.lstrip(";:").strip())
            if cur and len(cur) < 40:
                heads.append(cur)
        elif line.startswith(":") and line.lstrip(":").startswith("*"):
            text = plain(line.lstrip(":*").strip())
            if text and len(items) < limit:
                items.append((f"{cur}：" if cur else "") + text)
    return heads, items


def stardew_pc(zh: str, en: str) -> list[dict]:
    def collect(text):
        out = {}
        for name, body in _sw_sections(text, 2):
            ver = plain(name)
            if not re.match(r"^\d", ver):
                continue
            m = SW_DATE_RE.search(plain(body)[:600])
            date = iso_date(m.group(1)) if m else ""
            # 英文页把日期写成 "was released on 20 December 2024"
            if not date:
                m2 = re.search(r"released(?:\s+on)?\s+(\d{1,2}\s+\w+\s+\d{4})", plain(body)[:600], re.I)
                date = iso_date(m2.group(1)) if m2 else ""
            heads, items = _sw_body_notes(body)
            out[ver] = {"name": "、".join(heads[:3]), "notes": items, "date": date}
        return out

    a, b = collect(zh), collect(en)
    versions = []
    # 两个语言版本按「中文页顺序 + 英文页新增」合并；不再按版本号排序
    # （1.051 / 1.051b 这种老号按数字排会跑到 1.6.15 前面）。
    order = list(a) + [v for v in b if v not in a]
    for ver in order:
        zh_v, en_v = a.get(ver, {}), b.get(ver, {})
        notes = zh_v.get("notes") or en_v.get("notes") or []
        name = zh_v.get("name") or en_v.get("name") or ""
        date = zh_v.get("date") or en_v.get("date") or ""
        versions.append({
            "v": ver,
            "date": date,
            "name": name,
            "notes": notes,
            "wiki": f"{SW_WIKI}/%E7%89%88%E6%9C%AC%E5%8E%86%E5%8F%B2#{urllib.parse.quote(ver)}",
            "channel": "release",
        })
    return versions


def stardew_mobile(zh: str, en: str) -> list[dict]:
    """移动版：h2 = 平台（Android / iOS），h3 = 版本。"""
    def collect(text):
        out = {}
        for plat, body in _sw_sections(text, 2):
            plat_name = plain(plat)
            if "Android" not in plat_name and "安卓" not in plat_name:
                continue
            for ver_raw, vbody in _sw_sections(body, 3):
                ver = plain(ver_raw)
                if not re.match(r"^\d", ver):
                    continue
                text_body = plain(vbody)[:500]
                m = SW_DATE_RE.search(text_body)
                date = iso_date(m.group(1)) if m else ""
                if not date:
                    m2 = re.search(r"released\s+on\s+(\d{1,2}\s+\w+\s+\d{4})", text_body, re.I)
                    date = iso_date(m2.group(1)) if m2 else ""
                heads, items = _sw_body_notes(vbody)
                out[ver] = {"date": date, "name": "、".join(heads[:3]), "notes": items}
        return out

    a, b = collect(zh), collect(en)
    versions = []
    order = list(a) + [v for v in b if v not in a]
    for ver in order:
        zh_v, en_v = a.get(ver, {}), b.get(ver, {})
        versions.append({
            "v": ver,
            "date": zh_v.get("date") or en_v.get("date") or "",
            "name": zh_v.get("name") or en_v.get("name") or "",
            "notes": zh_v.get("notes") or en_v.get("notes") or [],
            "wiki": f"{SW_WIKI}/%E7%A7%BB%E5%8A%A8%E7%89%88%E5%8E%86%E5%8F%B2#{urllib.parse.quote(ver)}",
            "channel": "release",
        })
    return versions


def build_stardew() -> dict:
    files = ["stardew_zh_0.wiki", "stardew_zh_1.wiki", "stardew_en_0.wiki", "stardew_en_1.wiki"]
    missing = [f for f in files if not (CACHE / f).exists()]
    if missing:
        raise RuntimeError("缺少星露谷 Wiki 原始缓存：" + ", ".join(missing)
                           + "（用浏览器抓 /mediawiki/api.php?action=parse&prop=wikitext 存盘）")
    zh_pc, zh_mb = (CACHE / files[0]).read_text(encoding="utf-8"), (CACHE / files[1]).read_text(encoding="utf-8")
    en_pc, en_mb = (CACHE / files[2]).read_text(encoding="utf-8"), (CACHE / files[3]).read_text(encoding="utf-8")
    platforms = [
        {"key": "android", "label": "Android（Google Play）",
         "wiki": f"{SW_WIKI}/%E7%A7%BB%E5%8A%A8%E7%89%88%E5%8E%86%E5%8F%B2",
         # Wiki 的 Android 小节只列到 1.6.9，但页面顶部写明「Android 最新版本相当于 PC 1.6.15」，
         # 两者口径不同，必须在页面上讲清楚，免得读者以为本站漏了 1.6.15。
         "note": ("官方 Wiki 的 Android 列表最后一条是 **1.6.9（2024-11-04）**，"
                  "但同一页面顶部写着「Android 最新版本相当于 PC 1.6.15」——"
                  "1.6.10 之后 Android 没有单独的更新条目，改动并入 PC 版本，"
                  "对照请看下面的 PC 段。本站下载页的 1.6.15.x 属于这类构建号。"),
         "versions": stardew_mobile(zh_mb, en_mb)},
        {"key": "pc", "label": "PC（Steam / GOG，版本基准）",
         "wiki": f"{SW_WIKI}/%E7%89%88%E6%9C%AC%E5%8E%86%E5%8F%B2",
         "versions": stardew_pc(zh_pc, en_pc)},
    ]
    return {
        "title": "星露谷物语",
        "lead": ("星露谷物语由 ConcernedApe 独立开发。PC 版是版本基准：主机版与移动版的每个版本都"
                 "标注「相当于 PC 的哪个版本」，因此这里把 PC 版一并列出，方便对照 Android 包缺少哪些改动。"),
        "sources": [
            {"label": "Stardew Valley Wiki（官方）", "url": SW_WIKI + "/"},
            {"label": "官方更新公告（stardewvalley.net）", "url": "https://www.stardewvalley.net/"},
        ],
        "note": ("移动版的 Android 与 iOS 更新节奏不完全一致，这里只收 Android；"
                 "主机版（PS4 / Xbox / Switch / Vita）记录见 Wiki「主机版历史」。"),
        "platforms": platforms,
    }


# ------------------------------------------------------------------ 铁锈战争


def _looks_like_date(text: str) -> bool:
    s = plain(text)
    return bool(re.fullmatch(r"(?:\d{1,2}(?:st|nd|rd|th)?\s+)?[A-Za-z]{3,9}\.?\s*\d{0,2},?\s*\d{4}", s)
                or re.fullmatch(r"\d{4}-\d{2}-\d{2}", s))


def _plain_lines(fragment: str) -> list[str]:
    text = re.sub(r"<br\s*/?>", "\n", fragment)
    text = re.sub(r"<[^>]+>", "\n", text)
    out = []
    for line in text.split("\n"):
        t = plain(line.lstrip("-·—  ").strip())
        if t and t.lower() != "see on steam":
            out.append(t)
    return out


def _rw_notes(body: str, date: str) -> tuple[list[str], str]:
    """从一段 changelog HTML 里抽 2–3 条要点，并补出没写在 <p class=date> 里的日期。

    官方页的排法是「<b>小标题</b> + -要点若干」，只有小标题没有内容时读起来没信息量，
    所以拼成「小标题：第一条要点」。早期条目把日期写成普通文本行（"23 sep 2017"），
    这里认出来当日发日期，不当要点。
    """
    body = re.sub(r"<img[^>]*>", " ", body)
    for line in _plain_lines(body):
        if not date and _looks_like_date(line):
            date = iso_date(line)
            break
    notes = []
    for m in re.finditer(r"<b>(.*?)</b>(.*?)(?=<b>|$)", body, re.S):
        head = plain(m.group(1)).strip().rstrip(":：")
        bullets = [plain(x) for x in re.findall(r"-{1,3}\s*([^\n<]+)", m.group(2))]
        bullets = [b for b in bullets if b and len(b) > 4 and not _looks_like_date(b)]
        if head and 2 < len(head) < 70:
            notes.append(f"{head}：{bullets[0][:110]}" if bullets else head)
        if len(notes) >= 3:
            break
    if not notes:
        for line in _plain_lines(body):
            if _looks_like_date(line) or len(line) < 5:
                continue
            notes.append(line[:150])
            if len(notes) >= 3:
                break
    return notes, date


def rw_changelog(html_text: str) -> list[dict]:
    out = []
    unlabeled = 0
    # 页面顶部有一段被注释掉的空条目（<h3>Rusted Warfare v</h3>），先去掉注释
    html_text = re.sub(r"<!--.*?-->", "", html_text, flags=re.S)
    blocks = re.split(r"<h3>", html_text)[1:]
    for block in blocks:
        title_html = block.split("</h3>", 1)[0]
        title = plain(title_html)
        m = re.match(r"Rusted Warfare\s+v([\w.]+)?\s*(.*)$", title, re.I)
        if not m:
            continue
        ver, rest = (m.group(1) or ""), plain(m.group(2)).strip("() ")
        if not re.match(r"^\d", ver):
            # 官方页有两条只写 "Rusted Warfare v"（版本号漏了），内容是真的更新记录，
            # 不编版本号，按出现顺序标成「未标注①②」，页面上照实说明。
            unlabeled += 1
            ver = f"未标注{'①②③④⑤'[min(unlabeled, 5) - 1]}"
        body = block.split("</h3>", 1)[1] if "</h3>" in block else ""
        d = re.search(r'<p class="date">(.*?)</p>', body, re.S)
        date = iso_date(d.group(1)) if d else ""
        body = re.sub(r'<p class="date">.*?</p>', "", body, flags=re.S)
        steam = re.search(r'href="(https://store\.steampowered\.com/newshub/[^"]+)"', body)
        notes, date = _rw_notes(body, date)
        out.append({
            "v": ver,
            "date": date,
            "name": rest,
            "notes": notes,
            "wiki": steam.group(1) if steam else RW_CHANGELOG,
            "channel": "beta" if re.search(r"(beta|test)", rest, re.I) else "release",
        })
    return out


def rw_steam() -> list[dict]:
    """官方站 changelog 停在 1.14；1.15 的更新说明只在 Steam 官方公告里。"""
    try:
        raw = fetch("https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/",
                    {"appid": RW_APPID, "count": 100, "format": "json"})
        news = json.loads(raw)["appnews"]["newsitems"]
    except Exception as exc:
        log(f"  rustedwarfare: Steam 公告抓取失败（{exc}），跳过 1.15")
        return []
    out = []
    for item in news:
        if item.get("feedname") != "steam_community_announcements":
            continue
        if (item.get("author") or "").lower() != "corrodinggames":
            continue
        title = item.get("title") or ""
        if "1.15" not in title:
            continue
        content = item.get("contents") or ""
        # BBCode 里的图片、链接、Steam CDN 占位符先清掉，否则会原样出现在页面上
        content = re.sub(r"\[img\].*?\[/img\]", " ", content, flags=re.S)
        content = re.sub(r"\[/?url[^\]]*\]", " ", content)
        content = content.replace("{STEAM_CLAN_IMAGE}", " ")
        ver = "1.15p8" if "beta" in title.lower() else "1.15"
        # 标题已在 name 里，先摘掉，免得导语又从标题念一遍
        content = re.sub(r"\[h1\].*?\[/h1\]", " ", content, flags=re.S)
        # 导语：第一个 [h2]/[b] 之前的那段白话
        intro = re.split(r"\[h2\]|\[b\]", content, maxsplit=1)[0]
        intro = plain(re.sub(r"\[/?\w+[^\]]*\]", " ", intro)).strip()
        notes = []
        # beta 公告开头是「怎么在 Steam 里切到 beta」的操作说明，不是更新内容，跳过
        if len(intro) > 40 and not intro.lower().startswith("to try it out"):
            notes.append(intro[:180])
        for hm in re.finditer(r"\[b\](.+?)\[/b\](.*?)(?=\[b\]|\[h2\]|$)", content, re.S):
            head = plain(hm.group(1)).strip().rstrip(":：")
            if len(head) < 3 or re.match(r"^(update highlights|major changes|rusted warfare)", head, re.I):
                continue
            # 小标题后面通常跟一条 [*] 要点或 ---连字符要点，取第一条当说明
            seg = hm.group(2)
            b = (re.search(r"\[\*\]\s*([^\[]+)", seg)
                 or re.search(r"-{2,}\s*([^\n\[]{6,})", seg))
            detail = re.sub(r"\s+", " ", plain(b.group(1)).strip(" -—·")) if b else ""
            # 只有「(by uber)」这种括注的说明没有信息量，宁可不写
            if len(detail) < 12 or re.fullmatch(r"\([^)]*\)", detail):
                detail = ""
            notes.append(head + (f"：{detail[:100]}" if len(detail) > 3 else ""))
            if len(notes) >= 3:
                break
        if not notes:
            # 纯 [list][*] 结构的公告（如 1.15 beta）没有 [b] 小标题，直接取前几条要点
            for b in re.findall(r"\[\*\]\s*(.+?)(?=\[\*\]|\[/list\]|$)", content, re.S):
                t = re.sub(r"\s+", " ", plain(re.sub(r"\[[^\]]+\]", " ", b))).strip()
                if len(t) > 10:
                    notes.append(t[:150])
                if len(notes) >= 3:
                    break
        date = datetime.fromtimestamp(item["date"], timezone.utc).strftime("%Y-%m-%d")
        out.append({
            "v": ver,
            "date": date,
            "name": plain(title),
            "notes": notes[:3],
            "wiki": item.get("url") or RW_CHANGELOG,
            "channel": "beta" if ver.endswith("p8") else "release",
        })
    return out


def build_rustedwarfare(offline: bool) -> dict:
    fn = CACHE / "rustedwarfare_changelog.html"
    if not fn.exists() or not offline:
        CACHE.mkdir(parents=True, exist_ok=True)
        try:
            fn.write_text(fetch(RW_CHANGELOG), encoding="utf-8")
            log(f"  rustedwarfare: 抓取官方 changelog ({fn.stat().st_size} B)")
        except Exception as exc:
            if not fn.exists():
                raise
            log(f"  rustedwarfare: 抓取失败（{exc}），用缓存")
    versions = rw_changelog(fn.read_text(encoding="utf-8"))
    if not offline:
        have = {v["v"] for v in versions}
        # 官网 changelog 停在 1.14，Steam 公告里的 1.15 按日期插到对应位置
        for extra in rw_steam():
            if extra["v"] in have:
                continue
            idx = next((i for i, v in enumerate(versions)
                        if v.get("date") and extra.get("date") and v["date"] < extra["date"]), 0)
            versions.insert(idx, extra)
            have.add(extra["v"])
    return {
        "title": "铁锈战争",
        "lead": ("铁锈战争（Rusted Warfare）由 Corroding Games 独立开发，Android / Windows / Linux / "
                 "macOS / iOS 共用同一条版本线（1.15 起支持 iOS 与跨平台联机）。"
                 "官方没有 Wiki，更新记录以开发者官网 changelog 与 Steam 官方公告为准。"),
        "sources": [
            {"label": "Corroding Games · 官方 changelog", "url": RW_CHANGELOG},
            {"label": "Steam 官方公告（appid 647960）",
             "url": "https://store.steampowered.com/news/app/647960"},
        ],
        "note": ("官方 changelog 只写到 1.14（2020-11-17），1.15 的更新说明只在 Steam 官方公告里，"
                 "1.15 beta 系列（p1–p8）与正式版的日期分开标注。"),
        "platforms": [{
            "key": "all",
            "label": "全平台（Android / Windows / Linux / macOS / iOS）",
            "wiki": RW_CHANGELOG,
            "versions": versions,
        }],
    }


# ------------------------------------------------------------------ 主流程


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="只用本地缓存，不联网")
    ap.add_argument("--check", action="store_true", help="只打印统计，不写文件")
    args = ap.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    games = {}
    log("[1/3] 泰拉瑞亚 · Terraria Wiki（官方）")
    games["terraria"] = build_terraria(args.offline)
    log("[2/3] 星露谷物语 · Stardew Valley Wiki（官方，浏览器缓存）")
    games["stardew"] = build_stardew()
    log("[3/3] 铁锈战争 · Corroding Games 官方 changelog + Steam 公告")
    games["rustedwarfare"] = build_rustedwarfare(args.offline)

    for key, g in games.items():
        counts = ", ".join(f"{p['key']} {len(p['versions'])}" for p in g["platforms"])
        latest = {}
        for p in g["platforms"]:
            vs = p["versions"]        # 已是「新 → 旧」
            latest[p["key"]] = (vs[0]["v"], vs[0]["date"]) if vs else ("—", "—")
        log(f"  {key}: {counts} | 最新 {latest}")

    missing_dates = {k: sum(1 for p in g["platforms"] for v in p["versions"] if not v["date"])
                     for k, g in games.items()}
    log(f"  缺发布日期：{missing_dates}")

    doc = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "scripts/wiki_game_history.py",
        "games": games,
    }
    if args.check:
        log("--check：未写文件")
        return 0
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"写出 {OUT}（{OUT.stat().st_size} 字节）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
