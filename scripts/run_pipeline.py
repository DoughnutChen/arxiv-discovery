#!/usr/bin/env python3
"""运行 arXiv 搜索、PDF 下载、正文提取和中文摘要生成流水线。"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "arxiv-query"


def run(command: list[str], allow_failure: bool = False, env: dict[str, str] | None = None) -> int:
    print("$ " + " ".join(command))
    completed = subprocess.run(command, check=not allow_failure, env=env)
    return completed.returncode


def ask_query() -> str:
    query = input("请描述论文查找要求：").strip()
    if not query:
        raise ValueError("输入不能为空。")
    return query


def ask_api_key(provider: str, key_name: str) -> str:
    label = "Kimi" if provider == "kimi" else "OpenAI"
    api_key = getpass.getpass(f"请输入 {label} API key（输入不会显示）：").strip()
    if not api_key:
        raise ValueError(f"{key_name} 不能为空。")
    return api_key


def main() -> int:
    parser = argparse.ArgumentParser(description="搜索 arXiv、下载 PDF、提取正文并生成中文论文速读报告。")
    parser.add_argument("query", nargs="?", help="搜索关键词或短语；如果省略，将在终端中询问。")
    parser.add_argument("--max-results", type=int, default=5, help="处理论文数量，默认 5。")
    parser.add_argument("--category", help="可选 arXiv 分类，例如 cs.CL 或 stat.ML。")
    parser.add_argument(
        "--sort-by",
        choices=("relevance", "lastUpdatedDate", "submittedDate"),
        default="relevance",
        help="排序字段，默认 relevance。",
    )
    parser.add_argument(
        "--sort-order",
        choices=("ascending", "descending"),
        default="descending",
        help="排序方向，默认 descending。",
    )
    parser.add_argument("--output-dir", type=Path, help="输出目录，默认 runs/<query-slug>。")
    parser.add_argument("--provider", choices=("openai", "kimi"), default="openai", help="摘要生成服务，默认 openai。")
    parser.add_argument("--model", help="生成摘要使用的模型；未指定时按 provider 使用默认模型。")
    parser.add_argument("--base-url", help="Kimi API base URL；通常不需要修改。")
    parser.add_argument("--skip-download", action="store_true", help="只搜索 arXiv，不下载 PDF。")
    parser.add_argument("--skip-extract", action="store_true", help="搜索和下载 PDF，但不提取正文。")
    parser.add_argument("--skip-summary", action="store_true", help="不生成中文摘要报告。")
    parser.add_argument("--save-prompt", action="store_true", help="保存发送给模型的提示词，便于开发调试。")
    args = parser.parse_args()

    if args.max_results < 1:
        parser.error("--max-results 必须至少为 1")

    try:
        query = args.query.strip() if args.query else ask_query()
    except ValueError as exc:
        parser.error(str(exc))

    output_dir = args.output_dir or Path("runs") / slugify(query)
    output_dir.mkdir(parents=True, exist_ok=True)
    results_json = output_dir / "results.json"
    pdf_dir = output_dir / "pdfs"
    text_dir = output_dir / "text"
    report_md = output_dir / "report.md"
    prompt_md = output_dir / "summary_prompt.md"
    report_generated = False

    search_command = [
        sys.executable,
        str(SCRIPT_DIR / "search_arxiv.py"),
        query,
        "--max-results",
        str(args.max_results),
        "--sort-by",
        args.sort_by,
        "--sort-order",
        args.sort_order,
        "--output",
        str(results_json),
    ]
    if args.category:
        search_command.extend(["--category", args.category])
    run(search_command)

    returned = 0
    try:
        returned = int(json.loads(results_json.read_text(encoding="utf-8")).get("returned_results", 0))
    except Exception:
        returned = 0
    if returned == 0:
        print("arXiv 没有返回结果，已停止后续下载、解析和摘要生成。")
        return 0

    if not args.skip_download:
        run([sys.executable, str(SCRIPT_DIR / "download_pdfs.py"), str(results_json), "--output-dir", str(pdf_dir)])

    text_available = False
    if not args.skip_download and not args.skip_extract:
        run([sys.executable, str(SCRIPT_DIR / "extract_pdf_text.py"), str(pdf_dir), "--output-dir", str(text_dir)])
        text_available = text_dir.exists()

    if args.skip_summary:
        print("已按参数跳过自动摘要生成。")
    else:
        key_name = "KIMI_API_KEY" if args.provider == "kimi" else "OPENAI_API_KEY"
        api_key = os.environ.get(key_name)
        if not api_key:
            try:
                api_key = ask_api_key(args.provider, key_name)
            except ValueError as exc:
                print(f"{exc} 已跳过自动摘要生成。")
                api_key = ""
        if api_key:
            summary_command = [
                sys.executable,
                str(SCRIPT_DIR / "generate_summary.py"),
                str(results_json),
                "--output",
                str(report_md),
                "--provider",
                args.provider,
            ]
            if args.model:
                summary_command.extend(["--model", args.model])
            if args.base_url:
                summary_command.extend(["--base-url", args.base_url])
            if text_available:
                summary_command.extend(["--text-dir", str(text_dir)])
            if args.save_prompt:
                summary_command.extend(["--prompt-output", str(prompt_md)])
            summary_env = os.environ.copy()
            summary_env[key_name] = api_key
            run(summary_command, env=summary_env)
            report_generated = report_md.exists()
        else:
            print("未获得可用 API key，已跳过自动摘要生成。")

    print("流水线完成。")
    print(f"搜索结果：{results_json}")
    print(f"PDF 目录：{pdf_dir}")
    print(f"正文目录：{text_dir}")
    if report_generated:
        print(f"摘要报告：{report_md}")
    else:
        print("摘要报告：未生成")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"命令执行失败，退出码：{exc.returncode}", file=sys.stderr)
        raise SystemExit(exc.returncode)
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        raise SystemExit(130)
