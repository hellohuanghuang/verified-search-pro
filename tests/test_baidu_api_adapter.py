import datetime
import io
import json
import os
import sys
import unittest
import urllib.error
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import baidu_api_adapter  # noqa: E402


FAKE_ENV = {"BAIDU_API_KEY": "bce-v3/ALTAK-test-key"}

SAMPLE_REFERENCE = {
    "id": 1,
    "title": "2026年新能源汽车补贴政策解读",
    "url": "https://example.com/policy",
    "content": "2026年新能源汽车补贴政策延续购置税减免……",
    "snippet": "兜底摘要（官方 Skill 会删除该字段，VSP 兼容读取）",
    "date": "2026-01-12",
    "type": "web",
    "website": "example.com",
    "icon": "https://example.com/favicon.ico",
}


def make_response(*refs):
    return {"references": list(refs), "request_id": "req-test-123"}


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def make_http_error(code, error_code="", message=""):
    body = json.dumps({"code": error_code, "message": message}).encode("utf-8")
    return urllib.error.HTTPError(
        "https://qianfan.baidubce.com/v2/ai_search/web_search", code, "Error", {}, io.BytesIO(body)
    )


def run_search(fake_urlopen, *args, **kwargs):
    with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            return baidu_api_adapter.search_with_status(*args, **kwargs)


class BaiduApiAvailabilityTests(unittest.TestCase):
    def test_missing_key_is_unavailable(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(baidu_api_adapter.is_available())
            payload = baidu_api_adapter.search_with_status("query")
            self.assertEqual(payload["results"], [])
            self.assertEqual(payload["status"]["status"], "skipped")
            self.assertEqual(payload["status"]["reason"], "api_key_missing")
            self.assertEqual(payload["status"]["requires"], baidu_api_adapter.REQUIRED_ENV)
            self.assertEqual(baidu_api_adapter.search("query"), [])

    def test_get_status_requires_baidu_api_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            status = baidu_api_adapter.get_status()
            self.assertFalse(status["available"])
            self.assertIn("BAIDU_API_KEY", status["requires"])
            self.assertIn("qianfan.baidubce.com", status["endpoint"])


class BaiduApiMappingTests(unittest.TestCase):
    def test_references_mapped_to_vsp_format(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse(make_response(SAMPLE_REFERENCE))

        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                results = baidu_api_adapter.search("补贴", max_results=5, timeout=12)

        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertEqual(row["engine"], "baidu_api")
        self.assertEqual(row["url"], SAMPLE_REFERENCE["url"])
        self.assertEqual(row["title"], SAMPLE_REFERENCE["title"])
        self.assertEqual(row["content"], SAMPLE_REFERENCE["content"])  # content 优先
        self.assertEqual(row["published_at"], "2026-01-12")
        self.assertEqual(row["source"], "example.com")
        self.assertEqual(captured["timeout"], 12)

    def test_snippet_used_as_fallback_when_content_empty(self):
        ref = dict(SAMPLE_REFERENCE, content="")
        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", return_value=FakeResponse(make_response(ref))):
                results = baidu_api_adapter.search("补贴")
        self.assertEqual(results[0]["content"], SAMPLE_REFERENCE["snippet"])

    def test_request_headers_and_endpoint(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            return FakeResponse(make_response(SAMPLE_REFERENCE))

        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                baidu_api_adapter.search("补贴")

        req = captured["request"]
        self.assertEqual(req.get_header("Authorization"), "Bearer bce-v3/ALTAK-test-key")
        self.assertEqual(req.get_header("Content-type"), "application/json")
        self.assertEqual(req.get_header("X-appbuilder-from"), "verified-search-pro")
        self.assertEqual(req.full_url, "https://qianfan.baidubce.com/v2/ai_search/web_search")

    def test_request_body_structure(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            return FakeResponse(make_response(SAMPLE_REFERENCE))

        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                baidu_api_adapter.search("补贴政策", max_results=10)

        payload = json.loads(captured["request"].data.decode("utf-8"))
        self.assertEqual(payload["messages"], [{"content": "补贴政策", "role": "user"}])
        self.assertEqual(payload["search_source"], "baidu_search_v2")
        # 官方契约：resource_type_filter 为数组
        self.assertEqual(payload["resource_type_filter"], [{"type": "web", "top_k": 10}])
        # 官方契约：search_filter 始终存在，无时效过滤时为 {}
        self.assertEqual(payload["search_filter"], {})

    def test_top_k_passed_and_clamped(self):
        bodies = []

        def fake_urlopen(request, timeout):
            bodies.append(json.loads(request.data.decode("utf-8")))
            return FakeResponse(make_response(SAMPLE_REFERENCE))

        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                baidu_api_adapter.search("q", max_results=20)
                baidu_api_adapter.search("q", max_results=100)  # 超上限 → 50
                baidu_api_adapter.search("q", max_results=0)    # 非正 → 默认 10

        top_ks = [b["resource_type_filter"][0]["top_k"] for b in bodies]
        self.assertEqual(top_ks, [20, 50, 10])

    def test_freshness_shortcut_builds_range_filter(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            return FakeResponse(make_response(SAMPLE_REFERENCE))

        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                baidu_api_adapter.search("补贴", freshness="pw")

        payload = json.loads(captured["request"].data.decode("utf-8"))
        page_time = payload["search_filter"]["range"]["page_time"]
        today = datetime.datetime.now()
        self.assertEqual(page_time["gte"], (today - datetime.timedelta(days=6)).strftime("%Y-%m-%d"))
        self.assertEqual(page_time["lt"], (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d"))

    def test_freshness_custom_range_passthrough(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            return FakeResponse(make_response(SAMPLE_REFERENCE))

        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                baidu_api_adapter.search("补贴", freshness="2026-01-01to2026-01-31")

        payload = json.loads(captured["request"].data.decode("utf-8"))
        self.assertEqual(
            payload["search_filter"],
            {"range": {"page_time": {"gte": "2026-01-01", "lt": "2026-01-31"}}},
        )

    def test_invalid_freshness_degrades_to_empty_filter(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            return FakeResponse(make_response(SAMPLE_REFERENCE))

        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                baidu_api_adapter.search("补贴", freshness="bogus")

        payload = json.loads(captured["request"].data.decode("utf-8"))
        self.assertEqual(payload["search_filter"], {})

    def test_malformed_references_skipped(self):
        payload = {
            "references": [
                "not-a-dict",
                {"title": "无 URL 条目"},
                {"url": "https://example.com/no-title"},
                SAMPLE_REFERENCE,
            ],
            "request_id": "req-test-123",
        }
        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", return_value=FakeResponse(payload)):
                result = baidu_api_adapter.search_with_status("补贴")
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["status"]["status"], "ok")
        self.assertEqual(result["status"]["request_id"], "req-test-123")

    def test_max_results_truncates_locally(self):
        refs = [dict(SAMPLE_REFERENCE, url=f"https://example.com/{i}") for i in range(5)]
        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", return_value=FakeResponse(make_response(*refs))):
                result = baidu_api_adapter.search_with_status("补贴", max_results=2)
        self.assertEqual(len(result["results"]), 2)

    def test_empty_references_maps_to_empty_status(self):
        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", return_value=FakeResponse({"references": []})):
                result = baidu_api_adapter.search_with_status("补贴")
        self.assertEqual(result["results"], [])
        self.assertEqual(result["status"]["status"], "empty")
        self.assertEqual(result["status"]["reason"], "no_results_returned")


class BaiduApiErrorTests(unittest.TestCase):
    def _run_with_error(self, side_effect):
        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", side_effect=side_effect):
                return baidu_api_adapter.search_with_status("补贴")

    def _run_with_payload(self, payload):
        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", return_value=FakeResponse(payload)):
                return baidu_api_adapter.search_with_status("补贴")

    def test_http_401_maps_to_unauthorized(self):
        result = self._run_with_error(make_http_error(401, "AuthenticationError", "invalid api key"))
        self.assertEqual(result["results"], [])
        self.assertEqual(result["status"]["status"], "failed")
        self.assertEqual(result["status"]["reason"], "unauthorized")
        self.assertEqual(result["status"]["error_code"], "AuthenticationError")

    def test_http_403_maps_to_unauthorized(self):
        result = self._run_with_error(make_http_error(403, "", "forbidden"))
        self.assertEqual(result["status"]["status"], "failed")
        self.assertEqual(result["status"]["reason"], "unauthorized")
        self.assertEqual(result["status"]["error_code"], "HTTP 403")

    def test_http_429_maps_to_rate_limit_blocked(self):
        result = self._run_with_error(make_http_error(429, "RateLimitExceeded", "too many requests"))
        self.assertEqual(result["status"]["status"], "blocked")
        self.assertEqual(result["status"]["reason"], "rate_limit_exceeded")

    def test_business_error_code_in_200_response(self):
        # 官方契约：响应顶层出现 code 字段即业务错误
        payload = {"code": "InvalidParameter", "message": "top_k must be positive"}
        result = self._run_with_payload(payload)
        self.assertEqual(result["results"], [])
        self.assertEqual(result["status"]["status"], "failed")
        self.assertEqual(result["status"]["reason"], "api_error")
        self.assertEqual(result["status"]["error_code"], "InvalidParameter")
        self.assertIn("top_k", result["status"]["message"])

    def test_business_error_auth_code_maps_to_unauthorized(self):
        payload = {"code": "AuthenticationError", "message": "token expired"}
        result = self._run_with_payload(payload)
        self.assertEqual(result["status"]["status"], "failed")
        self.assertEqual(result["status"]["reason"], "unauthorized")

    def test_business_error_quota_code_maps_to_blocked(self):
        payload = {"code": "QuotaExceeded", "message": "daily quota exhausted"}
        result = self._run_with_payload(payload)
        self.assertEqual(result["status"]["status"], "blocked")
        self.assertEqual(result["status"]["reason"], "rate_limit_exceeded")

    def test_network_error_maps_to_failed(self):
        result = self._run_with_error(urllib.error.URLError("connection refused"))
        self.assertEqual(result["results"], [])
        self.assertEqual(result["status"]["status"], "failed")
        self.assertEqual(result["status"]["reason"], "network_error")

    def test_search_contract_returns_empty_list_on_error(self):
        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", side_effect=make_http_error(500, "InternalError", "boom")):
                self.assertEqual(baidu_api_adapter.search("补贴"), [])


class BaiduApiSearchFilterTests(unittest.TestCase):
    """build_search_filter 单测：注入固定时间，断言确定性输出（与官方 Skill 天数口径一致）。"""

    NOW = datetime.datetime(2026, 2, 10, 12, 0, 0)

    def test_empty_freshness_returns_empty_dict(self):
        self.assertEqual(baidu_api_adapter.build_search_filter("", now=self.NOW), {})
        self.assertEqual(baidu_api_adapter.build_search_filter(None, now=self.NOW), {})

    def test_shortcut_days(self):
        expected_gte = {"pd": "2026-02-09", "pw": "2026-02-04", "pm": "2026-01-11", "py": "2025-02-11"}
        for key, gte in expected_gte.items():
            with self.subTest(freshness=key):
                self.assertEqual(
                    baidu_api_adapter.build_search_filter(key, now=self.NOW),
                    {"range": {"page_time": {"gte": gte, "lt": "2026-02-11"}}},
                )

    def test_custom_range(self):
        self.assertEqual(
            baidu_api_adapter.build_search_filter("2025-12-01to2026-01-31", now=self.NOW),
            {"range": {"page_time": {"gte": "2025-12-01", "lt": "2026-01-31"}}},
        )

    def test_invalid_values_degrade_to_empty(self):
        for bad in ("yesterday", "2026/01/01", "2026-01-01", "pdd"):
            with self.subTest(freshness=bad):
                self.assertEqual(baidu_api_adapter.build_search_filter(bad, now=self.NOW), {})


class BaiduApiDateNormalizationTests(unittest.TestCase):
    def test_iso_date_passthrough(self):
        self.assertEqual(baidu_api_adapter._map_reference(dict(SAMPLE_REFERENCE, date="2026-01-12"))["published_at"], "2026-01-12")

    def test_datetime_normalized_to_iso_date(self):
        self.assertEqual(baidu_api_adapter._map_reference(dict(SAMPLE_REFERENCE, date="2026-01-12 16:04:16"))["published_at"], "2026-01-12")

    def test_unparseable_and_empty_date_become_empty(self):
        for bad in ("not-a-date", "2026年1月12日", "", None):
            with self.subTest(date=bad):
                self.assertEqual(baidu_api_adapter._map_reference(dict(SAMPLE_REFERENCE, date=bad))["published_at"], "")


if __name__ == "__main__":
    unittest.main()
