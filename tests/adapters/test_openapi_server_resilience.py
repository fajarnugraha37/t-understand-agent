from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tu_runtime.adapters.base import AdapterContext, item
from tu_runtime.adapters.openapi import OpenApiAsyncApiAdapter
from tu_runtime.adapters.registry import AdapterRegistry

ROOT = Path(__file__).resolve().parents[2]


def context(path: str, data: bytes) -> AdapterContext:
    return AdapterContext(
        extraction_id="EXT-OPENAPI-REGRESSION",
        snapshot_id="SNAP-OPENAPI-REGRESSION",
        repository_id="repository",
        path=path,
        file_sha256=hashlib.sha256(data).hexdigest(),
    )


class OpenApiServerResilienceTests(unittest.TestCase):
    def test_openapi_three_server_objects_are_normalized(self):
        document = {
            "openapi": "3.0.3",
            "info": {"title": "Qando API", "version": "1.0.0"},
            "servers": [
                {"url": "https://api.example.test/v1", "description": "production"},
                {"url": "https://sandbox.example.test/v1"},
            ],
            "paths": {},
        }
        data = json.dumps(document).encode()
        result = OpenApiAsyncApiAdapter().extract(
            context("openapi.json", data), data, data.decode()
        )
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(
            [value["name"] for value in result["dependencies"]],
            ["https://api.example.test/v1", "https://sandbox.example.test/v1"],
        )
        self.assertEqual(result["dependencies"][0]["detail"], "production")

    def test_asyncapi_named_server_map_is_normalized(self):
        document = {
            "asyncapi": "2.6.0",
            "info": {"title": "Events", "version": "1.0.0"},
            "servers": {
                "production": {
                    "url": "broker.example.test:9092",
                    "protocol": "kafka",
                }
            },
            "channels": {},
        }
        data = json.dumps(document).encode()
        result = OpenApiAsyncApiAdapter().extract(
            context("asyncapi.json", data), data, data.decode()
        )
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["dependencies"][0]["name"], "production")
        self.assertIn("broker.example.test:9092", result["dependencies"][0]["detail"])
        self.assertIn("kafka", result["dependencies"][0]["detail"])

    def test_item_defensively_normalizes_non_string_values(self):
        value = item(
            "server",
            {"url": "https://example.test"},
            1,
            {"protocol": "https"},
        )
        self.assertIsInstance(value["name"], str)
        self.assertIsInstance(value["detail"], str)
        self.assertIn("https://example.test", value["name"])

    def test_registry_converts_unexpected_adapter_exception_to_partial_result(self):
        registry = AdapterRegistry(ROOT)
        document = {
            "openapi": "3.0.3",
            "info": {"title": "Broken adapter fixture", "version": "1.0.0"},
            "paths": {},
        }
        data = json.dumps(document).encode()
        selected = registry.adapters["openapi-asyncapi"]
        with patch.object(selected, "extract", side_effect=KeyError("slice")):
            result = registry.extract(
                context("openapi.json", data), data, data.decode()
            )
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["adapter_id"], "openapi-asyncapi")
        self.assertTrue(
            any(
                "unexpected extraction failure" in value.lower()
                for value in result["limitations"]
            )
        )


if __name__ == "__main__":
    unittest.main()
