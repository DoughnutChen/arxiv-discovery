#!/usr/bin/env python3
"""一次性配置摘要生成 provider。"""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from provider_config import DOTENV_PATH, LOCAL_CONFIG_PATH, default_for, provider_names, write_local_config


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}：").strip()
    return value or default


def yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    value = input(f"{prompt} [{suffix}]：").strip().lower()
    if not value:
        return default
    return value in {"y", "yes", "是", "确认"}


def append_dotenv(values: dict[str, str], path: Path = DOTENV_PATH) -> None:
    existing: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                existing[key.strip()] = value.strip()
    existing.update({key: value for key, value in values.items() if value})
    text = "\n".join(f"{key}={value}" for key, value in existing.items()) + "\n"
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="配置 arxiv-discovery 的摘要生成服务。")
    parser.add_argument("--provider", choices=provider_names(), help="默认摘要生成 provider。")
    parser.add_argument("--model", help="默认模型。")
    parser.add_argument("--base-url", help="OpenAI-compatible 或 Responses API base URL。")
    parser.add_argument("--api-key-env", help="API key 环境变量名。")
    parser.add_argument("--write-env", action="store_true", help="将 provider 配置写入 .env。")
    parser.add_argument("--no-write-env", action="store_true", help="不写入 .env。")
    parser.add_argument("--with-api-key", action="store_true", help="交互输入 API key 并写入 .env。")
    parser.add_argument("--no-api-key", action="store_true", help="不询问 API key。")
    args = parser.parse_args()

    provider = args.provider or ask("选择 provider，可选 kimi/openai", "kimi")
    if provider not in provider_names():
        parser.error(f"--provider 必须是：{', '.join(provider_names())}")
    defaults = default_for(provider)
    model = args.model or ask("默认模型", defaults["model"])
    base_url = args.base_url or ask("Base URL", defaults["base_url"])
    api_key_env = args.api_key_env or ask("API key 环境变量名", defaults["api_key_env"])

    config = {
        "provider": provider,
        "type": defaults["type"],
        "base_url": base_url,
        "api_key_env": api_key_env,
        "model": model,
    }
    write_local_config(config)

    should_write_env = args.write_env or (not args.no_write_env and yes_no("是否把 provider 配置写入本地 .env", True))
    env_values: dict[str, str] = {}
    if should_write_env:
        env_values.update(
            {
                "ARXIV_DISCOVERY_PROVIDER": provider,
                "ARXIV_DISCOVERY_MODEL": model,
                "ARXIV_DISCOVERY_BASE_URL": base_url,
                "ARXIV_DISCOVERY_API_KEY_ENV": api_key_env,
            }
        )
    should_ask_key = args.with_api_key or (not args.no_api_key and yes_no("是否现在输入 API key 并写入本地 .env", False))
    if should_ask_key:
        api_key = getpass.getpass(f"请输入 {api_key_env}（输入不会显示）：").strip()
        if api_key:
            env_values[api_key_env] = api_key
            should_write_env = True
    if should_write_env and env_values:
        append_dotenv(env_values)

    print(f"已写入 provider 配置：{LOCAL_CONFIG_PATH}")
    if should_write_env and env_values:
        print(f"已更新本地环境文件：{DOTENV_PATH}")
    print("后续运行 run_pipeline.py 或 generate_summary.py 时会自动读取该配置。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("已中断")
        raise SystemExit(130)
