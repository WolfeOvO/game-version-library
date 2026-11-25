# Game Version Library

统一的 Minecraft、星露谷物语、Terraria 与 Rusted Warfare 版本元数据目录。

本仓库只发布：

- 版本号、平台、渠道、发布日期等元数据；
- 来源、许可证和抓取溯源信息；
- 原始来源页面或下载入口；
- 可公开验证的大小和校验值。

本仓库**不托管、不转存、不再分发游戏安装包**。下载入口仍归原始来源所有。

## 目录结构

```text
schema/game-version-library.schema.json  JSON Schema Draft 2020-12

data/catalog.json                        统一规范化目录

data/source-snapshots/                   生成目录使用的审计快照
scripts/build_catalog.py                  快照 → 规范化目录
scripts/validate_catalog.py               Schema + 语义校验
.github/workflows/validate.yml            GitHub Actions 校验
```

## 支持的游戏标识

```text
minecraft
stardew-valley
terraria
rusted-warfare
```

## 快速开始

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 scripts/build_catalog.py
python3 scripts/validate_catalog.py
```

规范化目录写入 `data/catalog.json`。构建过程是确定性的：相同输入快照应生成相同记录身份和内容。

## 数据模型

目录层级如下：

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

默认数据再分发策略为 `link-only`：公开元数据和入口，但不暗示原始游戏文件可以由本项目再分发。令牌、Cookie、临时签名和账户凭据不得提交；提取码只有在确认属于公开分享信息时才可作为公开提示。

## CI

Pull request 和 `main` 分支会执行：

1. JSON Schema 自身检查；
2. 规范目录格式校验；
3. 来源 ID、记录 ID、入口 ID 唯一性检查；
4. 日期一致性检查；
5. 凭据样式 URL 检查；
6. 四个游戏 ID 的覆盖检查。

## 许可

代码使用 MIT，见 [LICENSE](LICENSE)。目录数据只授予本项目实际拥有或明确获准的权利；第三方游戏、商标、来源页面和文件的权利归各自权利人所有。
