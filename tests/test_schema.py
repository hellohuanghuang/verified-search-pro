#!/usr/bin/env python3
"""Evidence-pack JSON Schema 基础校验测试。

本测试不依赖 jsonschema 库，使用标准库对 schema 和 sample output 做关键字段检查。
如果安装了 jsonschema 作为可选 dev dependency，可以进一步启用完整校验。
"""

import json
import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(ROOT, "schemas", "evidence-pack.schema.json")
FIXTURE_PATH = os.path.join(ROOT, "tests", "fixtures", "sample_search_results.json")

sys.path.insert(0, os.path.join(ROOT, "scripts"))

import result_fusion  # noqa: E402
import trust_model  # noqa: E402


class SchemaTests(unittest.TestCase):
    def test_schema_file_exists_and_has_required_fields(self):
        self.assertTrue(os.path.exists(SCHEMA_PATH))
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema = json.load(f)
        self.assertEqual(schema["type"], "object")
        for field in [
            "schema_version", "generated_at", "query", "research_mode", "search",
            "context_budget", "claims", "trusted_conclusions", "perspective_map",
            "common_misconceptions", "controversies_uncertainties", "temporal_evolution",
            "evidence", "limitations", "agent_handoff",
        ]:
            self.assertIn(field, schema["required"])

    def test_sample_output_matches_schema_required_fields(self):
        with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
            results = json.load(f)
        fused = result_fusion.fuse_results(results, "standard")
        package = trust_model.build_claim_package(
            "2026 年新能源汽车政策",
            fused,
            {"budget": "standard", "engines": ["baidu", "bing_cn", "sogou"], "total_raw": len(results)},
        )

        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema = json.load(f)

        self._check_object_against_schema(package, schema)

    def _check_object_against_schema(self, obj, schema, path="root"):
        if schema.get("type") == "object":
            self.assertIsInstance(obj, dict, f"{path} should be object")
            for req in schema.get("required", []):
                self.assertIn(req, obj, f"{path} missing required field: {req}")
            for prop, subschema in schema.get("properties", {}).items():
                if prop in obj:
                    self._check_object_against_schema(obj[prop], subschema, f"{path}.{prop}")
        elif schema.get("type") == "array":
            self.assertIsInstance(obj, list, f"{path} should be array")
            for i, item in enumerate(obj):
                self._check_object_against_schema(item, schema.get("items", {}), f"{path}[{i}]")
        elif schema.get("type") == "string":
            self.assertIsInstance(obj, str, f"{path} should be string")
        elif schema.get("type") == "integer":
            self.assertIsInstance(obj, int, f"{path} should be integer")
        elif schema.get("type") == "number":
            self.assertIsInstance(obj, (int, float), f"{path} should be number")
        elif schema.get("type") == "boolean":
            self.assertIsInstance(obj, bool, f"{path} should be boolean")
        elif isinstance(schema.get("type"), list):
            # 例如 ["string", "null"]
            types = schema["type"]
            if "null" in types and obj is None:
                return
            type_map = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "object": dict, "array": list}
            matched = any(isinstance(obj, type_map.get(t, type(None))) for t in types)
            self.assertTrue(matched, f"{path} should be one of {types}")


if __name__ == "__main__":
    unittest.main()
