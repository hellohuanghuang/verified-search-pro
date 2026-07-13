#!/usr/bin/env python3
"""
Verified Search Pro · 域名评级注册表
职责：统一管理域名可信度评分和分级，消除 result_fusion/trust_model 中的重复字典。
纯 Python 标准库，零外部依赖。
"""

import os
from urllib.parse import urlparse

import config as _config


# 域名字典 key -> grade 映射
_GRADE_ORDER = ["authoritative", "media", "ugc", "high_risk"]
_GRADE_LETTER = {
    "authoritative": "A",
    "media": "B",
    "ugc": "C",
    "high_risk": "D",
}


class DomainRegistry:
    def __init__(self, config: dict = None):
        self._config = config or _config.load_config(apply_env=False)
        self._table = self._build_table()

    def _build_table(self) -> dict:
        raw = self._config.get("domain_ranking", {})
        table = {}
        for grade, domains in raw.items():
            if not isinstance(domains, dict):
                continue
            for domain, score in domains.items():
                table[domain.lower()] = {
                    "score": float(score),
                    "grade": _GRADE_LETTER.get(grade, "unknown"),
                    "category": grade,
                }
        return table

    def _extract_domain(self, url: str) -> str:
        if not url:
            return ""
        if url.startswith("/"):
            return ""
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
        except Exception:
            return ""
        if host.startswith("www."):
            host = host[4:]
        return host

    def lookup(self, url: str) -> dict:
        """返回该 URL 的域名评级信息；找不到则返回 unknown。"""
        host = self._extract_domain(url)
        if not host:
            return {"score": 0.0, "grade": "unknown", "category": "unknown", "matched_domain": ""}

        # 优先精确匹配
        if host in self._table:
            entry = dict(self._table[host])
            entry["matched_domain"] = host
            return entry

        # 子域名匹配：从右向左匹配最长后缀
        parts = host.split(".")
        for i in range(len(parts)):
            candidate = ".".join(parts[i:])
            if candidate in self._table:
                entry = dict(self._table[candidate])
                entry["matched_domain"] = candidate
                return entry

        return {"score": 0.0, "grade": "unknown", "category": "unknown", "matched_domain": ""}

    def get_score(self, url: str) -> float:
        return self.lookup(url)["score"]

    def get_grade(self, url: str) -> str:
        return self.lookup(url)["grade"]

    def list_known_domains(self) -> list:
        return sorted(self._table.keys())

    def reload(self, config: dict = None):
        self._config = config if config is not None else _config.load_config(apply_env=False)
        self._table = self._build_table()


# 全局单例，保持向后兼容
_REGISTRY = None


def _registry() -> DomainRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = DomainRegistry()
    return _REGISTRY


def get_domain_score(url: str) -> float:
    return _registry().get_score(url)


def get_source_grade(url: str) -> str:
    return _registry().get_grade(url)


def list_known_domains() -> list:
    return _registry().list_known_domains()


def reload_registry(config: dict = None):
    _registry().reload(config)


def load_user_domains(path: str) -> dict:
    """加载用户自定义域名表，返回可用于 config 的 domain_ranking 结构。"""
    import json
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 domain_registry.py <url>")
        sys.exit(1)
    print(_registry().lookup(sys.argv[1]))
