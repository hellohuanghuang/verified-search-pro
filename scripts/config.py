#!/usr/bin/env python3
"""
Verified Search Pro · 配置加载器
职责：分层加载配置（默认 < 项目 < 用户 < 环境变量），保持 local-first。
纯 Python 标准库，零外部依赖。
"""

import json
import os


DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "default.json",
)


_APP_NAME = "verified-search-pro"


def _xdg_config_home() -> str:
    return os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")


def _user_config_path() -> str:
    return os.path.join(_xdg_config_home(), _APP_NAME, "config.json")


def _project_config_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config.json",
    )


def _load_json_if_exists(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并两个字典；override 优先。"""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(config: dict) -> dict:
    """从环境变量读取覆盖值。前缀 VSP_，用双下划线表示嵌套。"""
    env_prefix = "VSP_"
    for key, value in os.environ.items():
        if not key.startswith(env_prefix):
            continue
        rest = key[len(env_prefix):].lower()
        parts = rest.split("__")

        target = config
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                target[part] = {}
            target = target[part]

        leaf = parts[-1]
        # 尝试解析为 JSON 值，失败则保留字符串
        try:
            target[leaf] = json.loads(value)
        except json.JSONDecodeError:
            target[leaf] = value
    return config


def load_config(
    default_path: str = None,
    project_path: str = None,
    user_path: str = None,
    apply_env: bool = True,
) -> dict:
    """
    加载分层配置。
    优先级：环境变量 > 用户配置 > 项目配置 > 默认配置。
    """
    default = _load_json_if_exists(default_path or DEFAULT_CONFIG_PATH)
    project = _load_json_if_exists(project_path or _project_config_path())
    user = _load_json_if_exists(user_path or _user_config_path())

    config = _deep_merge(default, project)
    config = _deep_merge(config, user)
    if apply_env:
        config = _apply_env_overrides(config)

    return config


def get_config_sources(
    default_path: str = None,
    project_path: str = None,
    user_path: str = None,
    apply_env: bool = True,
) -> list:
    """返回实际生效的配置来源列表，用于 --doctor 展示。"""
    sources = [("default", default_path or DEFAULT_CONFIG_PATH)]
    project = project_path or _project_config_path()
    if os.path.exists(project):
        sources.append(("project", project))
    user = user_path or _user_config_path()
    if os.path.exists(user):
        sources.append(("user", user))
    if apply_env and any(k.startswith("VSP_") for k in os.environ):
        sources.append(("environment", "VSP_*"))
    return sources


def get_web_engines(config: dict) -> dict:
    """返回启用的 Web 引擎配置字典。"""
    return config.get("web_engines", {})


def get_user_agent(config: dict) -> str:
    return config.get("user_agent", "")


def get_tavily_endpoint(config: dict) -> str:
    return config.get("tavily_endpoint", "https://api.tavily.com/search")


if __name__ == "__main__":
    cfg = load_config()
    print(json.dumps(cfg, indent=2, ensure_ascii=False))
