# 非 Minecraft 游戏版本库

统一的星露谷物语、Terraria 与 Rusted Warfare 版本元数据目录。

Minecraft 已单独维护在私有的 `minecraft-site` 项目，本仓库**明确不包含 Minecraft 数据、代码、页面或构建产物**。

本仓库只发布：

- 版本号、平台、渠道、发布日期等元数据；
- 来源、许可证和抓取溯源信息；
- 原始来源页面或下载入口；
- 可公开验证的大小和校验值。

本仓库**不托管、不转存、不再分发游戏安装包**。下载入口仍归原始来源所有。

## 目录结构

```text
schema/game-version-library.schema.json  JSON Schema Draft 2020-12

data/catalog.json                        非 Minecraft 规范化目录
data/source-snapshots/non-minecraft/     脱敏后的审计快照
docs/                                    MkDocs 页面源码与 Ore 风格公开主题
overrides/main.html                      独立站点模板

scripts/build_catalog.py                  快照 → 规范化目录
scripts/collect_atomlib.py                Terraria/Rusted Warfare 来源采集器
scripts/collect_game_history.py           官方 Wiki/更新记录解析器
scripts/collect_stardew.py                星露谷来源采集器
scripts/sanitize_snapshots.py             删除提取码和临时签名
scripts/validate_catalog.py               Schema + 语义校验
scripts/render_markdown.py                规范目录 → Markdown 页面
mkdocs.yml                                 可复现站点配置
.github/workflows/validate.yml            GitHub Actions 校验
```

## 支持的游戏标识

```text
stardew-valley
terraria
rusted-warfare
```


## 快速开始

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 scripts/sanitize_snapshots.py
python3 scripts/build_catalog.py
python3 scripts/render_markdown.py
python3 scripts/validate_catalog.py
python3 -m unittest discover -s tests -v
.venv/bin/mkdocs build --strict
```

规范化目录写入 `data/catalog.json`。相同输入快照生成相同记录身份；`generated_at` 使用输入快照时间上界，`last_verified_at` 使用目录内最早验证时间。`mkdocs build --strict` 构建完整独立站点到 `site/`，包含 Ore 风格应用栏、导航抽屉、搜索、页面大纲、卡片/列表视图、明暗主题和响应式页面布局。部署到子路径时用 `SITE_URL` 设置规范 URL。

本地预览：

```bash
.venv/bin/mkdocs serve
```

## 数据模型

```text
catalog
└── datasets[]
    ├── game_id
    ├── platform_id
    ├── platform
    ├── license
    ├── provenance
    └── entries[]
        ├── version / version_raw / version_normalized
        ├── channel
        ├── availability
        ├── provenance[]
        └── offers[]
            ├── source_id
            ├── kind / scope
            ├── url
            ├── verification_status
            └── last_verified_at
```

`version_raw` 保留来源原文，`version_normalized` 用于跨来源匹配；两者不能互相覆盖。粗粒度目录使用 `entry_type=collection` 与 `coverage`，不能冒充精确版本安装包。

## 溯源和许可证

每条记录都应能够回到一个注册来源。`provenance` 保存来源 ID、读取时间和采集方式，`license` 区分项目代码、目录数据以及上游内容。

默认数据再分发策略为 `link-only`：公开元数据和入口，但不暗示原始游戏文件可以由本项目再分发。令牌、Cookie、临时签名和账户凭据不得提交。网盘密码和临时签名参数在进入公共快照前已删除，目录只保留 `access.mode`。

## CI

Pull request 和 `main` 分支会执行：

1. JSON Schema 自身检查；
2. 规范目录格式校验；
3. 来源 ID、记录 ID、入口 ID 唯一性检查；
4. 日期一致性检查；
5. 凭据样式 URL 检查；
6. 三个非 Minecraft 游戏 ID 的覆盖检查。

## 许可

代码使用 MIT，见 [LICENSE](LICENSE)。目录数据只授予本项目实际拥有或明确获准的权利；第三方游戏、商标、来源页面和文件的权利归各自权利人所有。
