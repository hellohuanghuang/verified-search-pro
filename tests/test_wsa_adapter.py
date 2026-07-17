import io
import json
import os
import sys
import unittest
import urllib.error
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import wsa_adapter  # noqa: E402


FAKE_ENV = {
    "TENCENTCLOUD_SECRET_ID": "test-secret-id",
    "TENCENTCLOUD_SECRET_KEY": "test-secret-key",
}


def make_pages(*pages):
    """构造 WSA 响应：Pages 为 JSON 字符串数组。"""
    return {"Response": {"Pages": [json.dumps(p, ensure_ascii=False) for p in pages]}}


SAMPLE_PAGE = {
    "title": "2026年新能源汽车补贴政策解读",
    "url": "https://example.com/policy",
    "passage": "2026年新能源汽车补贴政策延续购置税减免……",
    "date": "2026-01-12 16:04:16",
    "site": "example.com",
    "score": 0.92,
}


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
    body = json.dumps({"Response": {"Error": {"Code": error_code, "Message": message}}}).encode("utf-8")
    return urllib.error.HTTPError("https://wsa.tencentcloudapi.com/", code, "Error", {}, io.BytesIO(body))


class WsaAdapterAvailabilityTests(unittest.TestCase):
    def test_missing_credentials_is_unavailable(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(wsa_adapter.is_available())
            payload = wsa_adapter.search_with_status("query")
            self.assertEqual(payload["results"], [])
            self.assertEqual(payload["status"]["status"], "skipped")
            self.assertEqual(payload["status"]["reason"], "api_key_missing")
            self.assertEqual(payload["status"]["requires"], wsa_adapter.REQUIRED_ENV)

    def test_partial_credentials_is_unavailable(self):
        with mock.patch.dict(os.environ, {"TENCENTCLOUD_SECRET_ID": "only-id"}, clear=True):
            self.assertFalse(wsa_adapter.is_available())
            self.assertEqual(wsa_adapter.search("query"), [])

    def test_get_status_requires_both_env_vars(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            status = wsa_adapter.get_status()
            self.assertFalse(status["available"])
            self.assertIn("TENCENTCLOUD_SECRET_ID", status["requires"])
            self.assertIn("TENCENTCLOUD_SECRET_KEY", status["requires"])


class WsaAdapterMappingTests(unittest.TestCase):
    def test_pages_json_strings_mapped_to_vsp_format(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse(make_pages(SAMPLE_PAGE))

        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                results = wsa_adapter.search("补贴", max_results=5, timeout=12)

        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertEqual(row["engine"], "tencent_wsa")
        self.assertEqual(row["url"], SAMPLE_PAGE["url"])
        self.assertEqual(row["title"], SAMPLE_PAGE["title"])
        self.assertEqual(row["content"], SAMPLE_PAGE["passage"])
        self.assertEqual(row["published_at"], "2026-01-12")  # 已规范化为 ISO 日期
        self.assertEqual(row["source"], "example.com")
        self.assertEqual(row["score"], 0.92)
        self.assertEqual(captured["timeout"], 12)

    def test_request_headers_and_default_payload(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            return FakeResponse(make_pages(SAMPLE_PAGE))

        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                wsa_adapter.search("补贴")

        req = captured["request"]
        self.assertEqual(req.get_header("X-tc-action"), "SearchPro")
        self.assertEqual(req.get_header("X-tc-version"), "2025-05-08")
        self.assertTrue(req.get_header("Authorization").startswith("TC3-HMAC-SHA256 Credential=test-secret-id/"))
        self.assertTrue(req.full_url.startswith("https://wsa.tencentcloudapi.com"))
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload, {"Query": "补贴"})  # 默认不发送 Mode/Site/时间参数

    def test_site_and_time_range_params_passed_through(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            return FakeResponse(make_pages(SAMPLE_PAGE))

        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                wsa_adapter.search_with_status(
                    "补贴", site="gov.cn", from_time=1704067200, to_time=1735689600, mode=2
                )

        payload = json.loads(captured["request"].data.decode("utf-8"))
        self.assertEqual(payload["Site"], "gov.cn")
        self.assertEqual(payload["FromTime"], 1704067200)
        self.assertEqual(payload["ToTime"], 1735689600)
        self.assertEqual(payload["Mode"], 2)

    def test_malformed_pages_and_missing_fields_skipped(self):
        payload = {
            "Response": {
                "Pages": [
                    "not-json-at-all",
                    json.dumps({"title": "无 URL 条目"}),
                    json.dumps(SAMPLE_PAGE),
                ],
                "Version": "standard",
                "Msg": "ok",
            }
        }
        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", return_value=FakeResponse(payload)):
                result = wsa_adapter.search_with_status("补贴")
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["status"]["status"], "ok")
        self.assertEqual(result["status"]["account_version"], "standard")

    def test_max_results_truncates_locally(self):
        payload = make_pages(*[dict(SAMPLE_PAGE, url=f"https://example.com/{i}") for i in range(5)])
        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", return_value=FakeResponse(payload)):
                result = wsa_adapter.search_with_status("补贴", max_results=2)
        self.assertEqual(len(result["results"]), 2)


class WsaAdapterErrorTests(unittest.TestCase):
    def _run_with_error(self, side_effect):
        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", side_effect=side_effect):
                return wsa_adapter.search_with_status("补贴")

    def test_http_error_resource_not_found_maps_to_skipped(self):
        result = self._run_with_error(make_http_error(404, "ResourceNotFound", "service not activated"))
        self.assertEqual(result["results"], [])
        self.assertEqual(result["status"]["status"], "skipped")
        self.assertEqual(result["status"]["reason"], "service_not_activated")
        self.assertEqual(result["status"]["error_code"], "ResourceNotFound")

    def _run_with_payload(self, payload):
        with mock.patch.dict(os.environ, FAKE_ENV, clear=True):
            with mock.patch("urllib.request.urlopen", return_value=FakeResponse(payload)):
                return wsa_adapter.search_with_status("补贴")

    def test_business_error_unauthorized_maps_to_failed(self):
        payload = {"Response": {"Error": {"Code": "UnauthorizedOperation", "Message": "cam auth failed"}}}
        result = self._run_with_payload(payload)
        self.assertEqual(result["results"], [])
        self.assertEqual(result["status"]["status"], "failed")
        self.assertEqual(result["status"]["reason"], "unauthorized")

    def test_http_error_unauthorized_maps_to_failed(self):
        result = self._run_with_error(make_http_error(403, "UnauthorizedOperation", "cam auth failed"))
        self.assertEqual(result["status"]["status"], "failed")
        self.assertEqual(result["status"]["reason"], "unauthorized")

    def test_request_limit_exceeded_maps_to_blocked(self):
        result = self._run_with_error(make_http_error(429, "RequestLimitExceeded", "too many requests"))
        self.assertEqual(result["status"]["status"], "blocked")
        self.assertEqual(result["status"]["reason"], "rate_limit_exceeded")

    def test_network_error_maps_to_failed(self):
        result = self._run_with_error(urllib.error.URLError("connection refused"))
        self.assertEqual(result["results"], [])
        self.assertEqual(result["status"]["status"], "failed")
        self.assertEqual(result["status"]["reason"], "network_error")


class WsaAdapterSignatureTests(unittest.TestCase):
    def test_signature_is_deterministic_for_fixed_timestamp(self):
        payload = json.dumps({"Query": "补贴"}, ensure_ascii=False).encode("utf-8")
        auth1 = wsa_adapter.build_authorization("sid", "skey", payload, 1768000000)
        auth2 = wsa_adapter.build_authorization("sid", "skey", payload, 1768000000)
        self.assertEqual(auth1, auth2)
        import time as _time
        expected_date = _time.strftime("%Y-%m-%d", _time.gmtime(1768000000))
        self.assertTrue(auth1.startswith(f"TC3-HMAC-SHA256 Credential=sid/{expected_date}/wsa/tc3_request, "))
        self.assertIn("SignedHeaders=content-type;host, Signature=", auth1)
        # 签名部分为 64 位十六进制
        signature = auth1.rsplit("Signature=", 1)[1]
        self.assertEqual(len(signature), 64)
        int(signature, 16)

    def test_signature_changes_with_timestamp_and_key(self):
        payload = b'{"Query":"x"}'
        base = wsa_adapter.build_authorization("sid", "skey", payload, 1768000000)
        other_ts = wsa_adapter.build_authorization("sid", "skey", payload, 1768000060)
        other_key = wsa_adapter.build_authorization("sid", "other-key", payload, 1768000000)
        self.assertNotEqual(base, other_ts)
        self.assertNotEqual(base, other_key)


class WsaAdapterDateNormalizationTests(unittest.TestCase):
    def test_wsa_datetime_normalized_to_iso_date(self):
        page = dict(SAMPLE_PAGE, date="2026-01-12 16:04:16")
        self.assertEqual(wsa_adapter._map_page(page)["published_at"], "2026-01-12")

    def test_iso_date_passthrough(self):
        page = dict(SAMPLE_PAGE, date="2026-01-12")
        self.assertEqual(wsa_adapter._map_page(page)["published_at"], "2026-01-12")

    def test_unparseable_and_empty_date_become_empty(self):
        for bad in ("not-a-date", "2026年1月12日", "", None):
            page = dict(SAMPLE_PAGE, date=bad)
            self.assertEqual(wsa_adapter._map_page(page)["published_at"], "")


if __name__ == "__main__":
    unittest.main()
