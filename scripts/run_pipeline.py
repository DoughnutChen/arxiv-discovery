#!/usr/bin/env python3
"""运行 arXiv 搜索、PDF 下载、正文提取和中文摘要生成完整流程。"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from provider_settings import provider_names, resolve_provider_config

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
    label = provider
    api_key = getpass.getpass(f"请输入 {label} API key（输入不会显示）：").strip()
    if not api_key:
        raise ValueError(f"{key_name} 不能为空。")
    return api_key


def parse_request(request: str, output_path: Path) -> dict[str, object]:
    command = [sys.executable, str(SCRIPT_DIR / "parse_request.py"), request, "--output", str(output_path)]
    run(command)
    return json.loads(output_path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="搜索 arXiv、下载 PDF、提取正文并生成中文论文速读报告。")
    parser.add_argument("query", nargs="?", help="搜索关键词或短语；如果省略，将在终端中询问。")
    parser.add_argument("--max-results", type=int, help="处理论文数量；未指定时从自然语言需求中解析，默认 6。")
    parser.add_argument("--category", help="可选 arXiv 分类，例如 cs.CL 或 stat.ML。")
    parser.add_argument("--date-from", help="可选起始提交日期，格式 YYYY-MM-DD；优先级高于自然语言解析结果。")
    parser.add_argument("--date-to", help="可选结束提交日期，格式 YYYY-MM-DD；优先级高于自然语言解析结果。")
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
    parser.add_argument("--provider", choices=provider_names(), help="摘要生成服务；未指定时读取本地配置，默认 kimi。")
    parser.add_argument("--model", help="生成摘要使用的模型；优先级高于本地配置。")
    parser.add_argument("--base-url", help="API base URL；优先级高于本地配置。")
    parser.add_argument("--api-key-env", help="API key 环境变量名；优先级高于本地配置。")
    parser.add_argument("--skip-download", action="store_true", help="只搜索 arXiv，不下载 PDF。")
    parser.add_argument("--skip-extract", action="store_true", help="搜索和下载 PDF，但不提取正文。")
    parser.add_argument("--skip-summary", action="store_true", help="不生成中文摘要报告。")
    parser.add_argument("--skip-html", action="store_true", help="不导出最终 HTML 页面。")
    parser.add_argument("--save-prompt", action="store_true", help="保存发送给模型的提示词，便于开发调试。")
    args = parser.parse_args()

    if args.max_results is not None and args.max_results < 1:
        parser.error("--max-results 必须至少为 1")

    try:
        request_text = args.query.strip() if args.query else ask_query()
    except ValueError as exc:
        parser.error(str(exc))

    provisional_slug = slugify(request_text)
    output_dir = args.output_dir or Path("runs") / provisional_slug
    output_dir.mkdir(parents=True, exist_ok=True)
    request_json = output_dir / "request.json"
    results_json = output_dir / "results.json"
    pdf_dir = output_dir / "pdfs"
    text_dir = output_dir / "text"
    report_md = output_dir / "report.md"
    html_path = output_dir / "index.html"
    prompt_md = output_dir / "summary_prompt.md"
    report_generated = False
    html_generated = False

    parsed = parse_request(request_text, request_json)
    query = str(parsed.get("search_query") or request_text)
    keywords = [str(item) for item in parsed.get("keywords", []) if str(item).strip()]
    max_results = args.max_results or int(parsed.get("max_results") or 6)
    date_from = args.date_from or parsed.get("date_from")
    date_to = args.date_to or parsed.get("date_to")
    print(f"解析后的搜索关键词：{query}")
    if keywords:
        print(f"拆分关键词：{', '.join(keywords)}")
    print(f"解析后的论文篇数：{max_results}")
    if date_from or date_to:
        print(f"解析后的时间范围：{date_from or '不限'} 到 {date_to or '不限'}")

    search_command = [
        sys.executable,
        str(SCRIPT_DIR / "search_arxiv.py"),
        query,
        "--max-results",
        str(max_results),
        "--sort-by",
        args.sort_by,
        "--sort-order",
        args.sort_order,
        "--output",
        str(results_json),
    ]
    if args.category:
        search_command.extend(["--category", args.category])
    for keyword in keywords:
        search_command.extend(["--keyword", keyword])
    if date_from:
        search_command.extend(["--date-from", str(date_from)])
    if date_to:
        search_command.extend(["--date-to", str(date_to)])
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
        provider_settings = resolve_provider_config(args.provider, args.model, args.base_url, args.api_key_env)
        key_name = provider_settings["api_key_env"]
        api_key = os.environ.get(key_name)
        if not api_key:
            try:
                api_key = ask_api_key(provider_settings["provider"], key_name)
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
                provider_settings["provider"],
                "--model",
                provider_settings["model"],
                "--base-url",
                provider_settings["base_url"],
                "--api-key-env",
                provider_settings["api_key_env"],
            ]
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

    if not args.skip_html:
        export_command = [
            sys.executable,
            str(SCRIPT_DIR / "export_html.py"),
            str(results_json),
            "--output",
            str(html_path),
        ]
        if report_md.exists():
            export_command.extend(["--report", str(report_md)])
        run(export_command)
        html_generated = html_path.exists()
    else:
        print("已按参数跳过 HTML 页面导出。")

    print("完整流程完成。")
    print(f"搜索结果：{results_json}")
    print(f"PDF 目录：{pdf_dir}")
    print(f"正文目录：{text_dir}")
    if report_generated:
        print(f"摘要报告：{report_md}")
    else:
        print("摘要报告：未生成")
    if html_generated:
        print(f"HTML 页面：{html_path}")
    else:
        print("HTML 页面：未生成")
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
