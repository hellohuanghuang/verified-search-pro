import json
import os
import sys
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import tavily_adapter  # noqa: E402


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class TavilyAdapterTests(unittest.TestCase):
    def test_missing_api_key_is_unavailable(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(tavily_adapter.is_available())
            self.assertEqual(tavily_adapter.search("query"), [])

    def test_direct_rest_api_maps_results(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse({
                "results": [
                    {
                        "url": "https://example.com/a",
                        "title": "Example title",
                        "content": "Example content",
                        "score": 0.8,
                        "published_date": "2026-06-01",
                    }
                ]
            })

        with mock.patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                results = tavily_adapter.search("example", max_results=1, search_depth="basic")

        self.assertEqual(captured["timeout"], 30)
        self.assertEqual(captured["request"].get_header("Authorization"), "Bearer test-key")
        self.assertEqual(results[0]["engine"], "tavily")
        self.assertEqual(results[0]["published_at"], "2026-06-01")


if __name__ == "__main__":
    unittest.main()
