import json
import subprocess
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


class CatalogContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((ROOT / "schema/game-version-library.schema.json").read_text(encoding="utf-8"))
        cls.catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(cls.schema, format_checker=FormatChecker())

    def test_schema_is_valid(self):
        Draft202012Validator.check_schema(self.schema)

    def test_catalog_matches_schema(self):
        self.assertEqual([], list(self.validator.iter_errors(self.catalog)))

    def test_all_requested_games_are_present(self):
        games = {dataset["game_id"] for dataset in self.catalog["datasets"]}
        self.assertEqual({"stardew-valley", "terraria", "rusted-warfare"}, games)

    def test_catalog_semantic_validator_passes(self):
        result = subprocess.run(
            [sys.executable, "scripts/validate_catalog.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_no_raw_password_field_is_published(self):
        def walk(value):
            if isinstance(value, dict):
                self.assertNotIn("password", value)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(self.catalog)

    def test_public_catalog_has_no_minecraft_dataset(self):
        self.assertNotIn("minecraft", {dataset["game_id"] for dataset in self.catalog["datasets"]})
        self.assertFalse((ROOT / "data/source-snapshots/minecraft").exists())
        site_config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8").lower()
        self.assertNotIn("minecraft", site_config)

    def test_official_history_snapshots_are_all_in_catalog(self):
        history = json.loads((ROOT / "data/source-snapshots/non-minecraft/game_history.json").read_text(encoding="utf-8"))
        datasets = {item["dataset_id"]: item for item in self.catalog["datasets"]}
        pairs = (
            ("terraria-desktop", "terraria", "desktop"),
            ("terraria-mobile", "terraria", "mobile"),
            ("stardew-valley-android", "stardew", "android"),
            ("stardew-valley-pc", "stardew", "pc"),
            ("rusted-warfare-history", "rustedwarfare", "all"),
        )
        for dataset_id, game_id, platform_id in pairs:
            expected = {str(item["v"]) for game_platform in history["games"][game_id]["platforms"] if game_platform["key"] == platform_id for item in game_platform["versions"]}
            actual = {entry["version"] for entry in datasets[dataset_id]["entries"]}
            self.assertTrue(expected <= actual, f"{dataset_id}: missing {sorted(expected - actual)}")

    def test_site_shell_sources_and_build_config_are_included(self):
        for path in (
            "mkdocs.yml",
            "overrides/main.html",
            "docs/stylesheets/ore.css",
            "docs/stylesheets/catalog.css",
            "docs/stylesheets/site.css",
            "docs/javascripts/app.js",
            "docs/javascripts/catalog.js",
            "docs/javascripts/tabs.js",
            "docs/javascripts/motion.js",
        ):
            self.assertTrue((ROOT / path).is_file(), path)

    def test_markdown_renderer_smoke(self):
        result = subprocess.run(
            [sys.executable, "scripts/render_markdown.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertTrue((ROOT / "docs/index.md").exists())


if __name__ == "__main__":
    unittest.main()
