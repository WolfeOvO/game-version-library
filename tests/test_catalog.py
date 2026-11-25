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
        self.assertEqual({"minecraft", "stardew-valley", "terraria", "rusted-warfare"}, games)

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


if __name__ == "__main__":
    unittest.main()
