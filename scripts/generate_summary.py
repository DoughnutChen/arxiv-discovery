#!/usr/bin/env python3
"""调用 OpenAI 或 Kimi API，根据 arXiv 元数据和论文正文生成中文速读报告。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
KIMI_BASE_URL = "https://api.moonshot.cn/v1"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_KIMI_MODEL = "moonshot-v1-32k"
MAX_TEXT_CHARS_PER_PAPER = 12000
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_STYLE_REFERENCE = SCRIPT_DIR.parent / "references" / "summary_schema.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_text_for_paper(text_dir: Path | None, arxiv_id: str) -> str:
    if text_dir is None or not text_dir.exists():
        return ""
    direct = text_dir / f"{arxiv_id}.txt"
    if direct.exists():
        return direct.read_text(encoding="utf-8", errors="ignore")
    normalized = arxiv_id.replace("/", "_")
    fallback = text_dir / f"{normalized}.txt"
    if fallback.exists():
        return fallback.read_text(encoding="utf-8", errors="ignore")
    return ""


def compact_paper(paper: dict[str, Any], text_dir: Path | None) -> dict[str, Any]:
    text = find_text_for_paper(text_dir, str(paper.get("arxiv_id", "")))
    return {
        "arxiv_id": paper.get("arxiv_id", ""),
        "title": paper.get("title", ""),
        "authors": paper.get("authors", []),
        "published": paper.get("published", ""),
        "updated": paper.get("updated", ""),
        "abstract_url": paper.get("abstract_url", ""),
        "pdf_url": paper.get("pdf_url", ""),
        "primary_category": paper.get("primary_category", ""),
        "categories": paper.get("categories", []),
        "arxiv_summary": paper.get("summary", ""),
        "extracted_text_excerpt": text[:MAX_TEXT_CHARS_PER_PAPER],
        "text_available": bool(text.strip()),
    }


def read_style_reference(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def build_prompt(payload: dict[str, Any], text_dir: Path | None, style_reference: str) -> str:
    papers = [compact_paper(paper, text_dir) for paper in payload.get("papers", [])]
    compact_payload = {
        "query": payload.get("query", ""),
        "category": payload.get("category"),
        "sort_by": payload.get("sort_by"),
        "sort_order": payload.get("sort_order"),
        "returned_results": payload.get("returned_results"),
        "papers": papers,
    }
    return f"""
你是面向研究生和博士文献调研的论文速读助手。请根据下面的 arXiv 搜索结果、摘要和论文正文节选，生成 Markdown 格式中文速读报告。

必须严格遵守下面参考文件中的格式、长度和语言风格要求：

```markdown
{style_reference}
```

额外要求：
1. 不要编造输入中没有的实验结果、理论贡献或结论。
2. 如果正文不可用，应说明摘要主要基于 arXiv 摘要。
3. 必须使用中文输出，论文题目保留英文原文。
4. 必须为输入中的每一篇论文都输出一个编号条目，不要省略、合并或中途停止。
5. 每篇论文的 `### 摘要` 中，`**研究问题**`、`**研究方法**`、`**研究结论**` 必须分别单独成行；研究结论的每个编号结论也必须单独成行。

搜索与论文数据如下：

```json
{json.dumps(compact_payload, ensure_ascii=False, indent=2)}
```
""".strip()


def call_openai(prompt: str, model: str, api_key: str) -> str:
    body = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt,
                    }
                ],
            }
        ],
    }
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenAI API 请求失败：HTTP {exc.code} {detail}") from exc

    texts: list[str] = []
    for item in result.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                texts.append(content.get("text", ""))
    output_text = "\n".join(part for part in texts if part).strip()
    if not output_text:
        raise RuntimeError("OpenAI API 未返回可用文本。")
    return output_text


def call_kimi(prompt: str, model: str, api_key: str, base_url: str) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Kimi API 请求失败：HTTP {exc.code} {detail}") from exc

    choices = result.get("choices", [])
    if not choices:
        raise RuntimeError("Kimi API 未返回可用 choices。")
    output_text = str(choices[0].get("message", {}).get("content", "")).strip()
    if not output_text:
        raise RuntimeError("Kimi API 未返回可用文本。")
    return output_text


def default_model(provider: str) -> str:
    if provider == "kimi":
        return DEFAULT_KIMI_MODEL
    return DEFAULT_OPENAI_MODEL


def validate_report_complete(report: str, payload: dict[str, Any]) -> None:
    expected = len(payload.get("papers", []))
    headings = list(re.finditer(r"^##\s+(\d+)\.", report, flags=re.MULTILINE))
    found = len(headings)
    if expected and found != expected:
        raise RuntimeError(f"摘要报告不完整：预期 {expected} 篇论文，实际生成 {found} 篇。请重新生成或减少正文节选长度后重试。")
    required_markers = ("### 摘要", "**研究问题**", "**研究方法**", "**研究结论**", "### 具体领域", "### 推荐原因")
    for index, heading in enumerate(headings):
        section_end = headings[index + 1].start() if index + 1 < len(headings) else len(report)
        section = report[heading.start():section_end]
        missing = [marker for marker in required_markers if marker not in section]
        if missing:
            paper_number = heading.group(1)
            missing_text = "、".join(missing)
            raise RuntimeError(f"摘要报告第 {paper_number} 篇不完整，缺少：{missing_text}。请重新生成或减少正文节选长度后重试。")


def main() -> int:
    parser = argparse.ArgumentParser(description="根据 arXiv 搜索结果和正文生成中文论文速读报告。")
    parser.add_argument("results_json", type=Path, help="search_arxiv.py 生成的 results.json。")
    parser.add_argument("--text-dir", type=Path, help="extract_pdf_text.py 生成的正文目录。")
    parser.add_argument("--output", type=Path, default=Path("report.md"), help="输出 Markdown 报告路径。")
    parser.add_argument("--provider", choices=("openai", "kimi"), default="kimi", help="摘要生成服务，默认 kimi。")
    parser.add_argument("--model", help="生成摘要使用的模型；未指定时按 provider 使用默认模型。")
    parser.add_argument("--base-url", help=f"Kimi API base URL，默认 {KIMI_BASE_URL}。")
    parser.add_argument("--prompt-output", type=Path, help="可选：保存发送给模型的提示词，便于开发调试。")
    parser.add_argument("--style-reference", type=Path, default=DEFAULT_STYLE_REFERENCE, help="摘要格式和风格要求 Markdown 文件。")
    args = parser.parse_args()

    model = args.model or default_model(args.provider)
    key_name = "KIMI_API_KEY" if args.provider == "kimi" else "OPENAI_API_KEY"
    api_key = os.environ.get(key_name)
    if not api_key:
        print(f"未检测到 {key_name}，无法自动生成摘要。请通过环境变量提供 API key，或使用 run_pipeline.py 交互输入。", file=sys.stderr)
        return 2

    payload = read_json(args.results_json)
    style_reference = read_style_reference(args.style_reference)
    prompt = build_prompt(payload, args.text_dir, style_reference)
    if args.prompt_output:
        args.prompt_output.parent.mkdir(parents=True, exist_ok=True)
        args.prompt_output.write_text(prompt, encoding="utf-8")

    if args.provider == "kimi":
        report = call_kimi(prompt, model, api_key, args.base_url or KIMI_BASE_URL)
    else:
        report = call_openai(prompt, model, api_key)
    validate_report_complete(report, payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"已生成摘要报告：{args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        raise SystemExit(130)
