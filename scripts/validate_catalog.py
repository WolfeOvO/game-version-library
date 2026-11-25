#!/usr/bin/env python3
"""Validate the normalized catalog and its cross-object provenance rules."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schema" / "game-version-library.schema.json"
CATALOG = ROOT / "data" / "catalog.json"

SECRET_QUERY_NAMES = {"pwd", "password", "token", "access_token", "api_key", "apikey", "secret", "cookie", "signature", "sig", "auth", "e"}
SECRET_VALUE_MARKERS = ("token=", "access_token=", "authorization=", "bearer ", "cookie=")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", type=Path, default=SCHEMA)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    args = parser.parse_args()
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    errors: list[str] = []

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors.extend(f"schema: {list(error.absolute_path)}: {error.message}" for error in validator.iter_errors(catalog))

    registered_sources = {source["source_id"] for source in catalog.get("provenance", {}).get("sources", [])}
    dataset_ids: set[str] = set()
    try:
        catalog_time = parse_time(catalog["generated_at"])
    except (KeyError, ValueError) as exc:
        fail(errors, f"catalog generated_at invalid: {exc}")
        catalog_time = datetime.max.astimezone()

    seen_entry_ids: set[str] = set()
    seen_offer_ids: set[str] = set()
    for dataset in catalog.get("datasets", []):
        dataset_id = dataset.get("dataset_id")
        if dataset_id in dataset_ids:
            fail(errors, f"duplicate dataset_id: {dataset_id}")
        dataset_ids.add(dataset_id)
        dataset_sources = set(dataset.get("provenance", {}).get("source_ids", []))
        if not dataset_sources <= registered_sources:
            fail(errors, f"{dataset_id}: unknown dataset source ids: {sorted(dataset_sources - registered_sources)}")
        for entry in dataset.get("entries", []):
            entry_id = entry.get("entry_id")
            if entry_id in seen_entry_ids:
                fail(errors, f"duplicate entry_id: {entry_id}")
            seen_entry_ids.add(entry_id)
            try:
                verified = parse_time(entry["last_verified_at"])
                if verified > catalog_time:
                    fail(errors, f"{entry_id}: last_verified_at is after catalog generated_at")
            except (KeyError, ValueError):
                pass
            for provenance in entry.get("provenance", []):
                source_id = provenance.get("source_id")
                if source_id not in registered_sources:
                    fail(errors, f"{entry_id}: unknown provenance source_id: {source_id}")
            for offer in entry.get("offers", []):
                offer_id = offer.get("offer_id")
                if offer_id in seen_offer_ids:
                    fail(errors, f"duplicate offer_id: {offer_id}")
                seen_offer_ids.add(offer_id)
                source_id = offer.get("source_id")
                if source_id not in registered_sources:
                    fail(errors, f"{offer_id}: unknown offer source_id: {source_id}")
                url = offer.get("url", "")
                query_names = {name.lower() for name in parse_qs(urlparse(url).query)}
                if query_names & SECRET_QUERY_NAMES:
                    fail(errors, f"{offer_id}: credential-like query parameter: {sorted(query_names & SECRET_QUERY_NAMES)}")
                lowered = url.lower()
                if any(marker in lowered for marker in SECRET_VALUE_MARKERS):
                    fail(errors, f"{offer_id}: credential-like URL marker")
                try:
                    offer_verified = parse_time(offer["last_verified_at"])
                    if offer_verified > catalog_time:
                        fail(errors, f"{offer_id}: last_verified_at is after catalog generated_at")
                except (KeyError, ValueError):
                    pass

    if errors:
        print("catalog validation: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"catalog validation: PASS datasets={len(catalog['datasets'])} entries={len(seen_entry_ids)} offers={len(seen_offer_ids)} sources={len(registered_sources)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
