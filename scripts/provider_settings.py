"""摘要生成 provider 的本地配置读取工具。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
LOCAL_CONFIG_PATH = SKILL_DIR / ".local" / "provider.json"
DOTENV_PATH = SKILL_DIR / ".env"

DEFAULT_PROVIDERS: dict[str, dict[str, str]] = {
    "kimi": {
        "provider": "kimi",
        "type": "openai-compatible",
        "base_url": "https://api.moonshot.cn/v1",
        "api_key_env": "KIMI_API_KEY",
        "model": "moonshot-v1-32k",
    },
    "openai": {
        "provider": "openai",
        "type": "openai-responses",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-4.1-mini",
    },
}


def load_dotenv(path: Path = DOTENV_PATH) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def read_local_config(path: Path = LOCAL_CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_local_config(config: dict[str, Any], path: Path = LOCAL_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def provider_names() -> tuple[str, ...]:
    return tuple(DEFAULT_PROVIDERS)


def default_for(provider: str) -> dict[str, str]:
    if provider not in DEFAULT_PROVIDERS:
        raise ValueError(f"未知 provider：{provider}")
    return dict(DEFAULT_PROVIDERS[provider])


def resolve_provider_config(
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key_env: str | None = None,
) -> dict[str, str]:
    load_dotenv()
    local = read_local_config()
    selected_provider = (
        provider
        or os.environ.get("ARXIV_DISCOVERY_PROVIDER")
        or str(local.get("provider") or "")
        or "kimi"
    )
    config = default_for(selected_provider)
    if local.get("provider") == selected_provider:
        for key in ("type", "base_url", "api_key_env", "model"):
            if local.get(key):
                config[key] = str(local[key])

    env_overrides = {
        "model": os.environ.get("ARXIV_DISCOVERY_MODEL"),
        "base_url": os.environ.get("ARXIV_DISCOVERY_BASE_URL"),
        "api_key_env": os.environ.get("ARXIV_DISCOVERY_API_KEY_ENV"),
    }
    for key, value in env_overrides.items():
        if value:
            config[key] = value

    if model:
        config["model"] = model
    if base_url:
        config["base_url"] = base_url
    if api_key_env:
        config["api_key_env"] = api_key_env

    return config
