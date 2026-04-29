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

from provider_settings import provider_names, resolve_provider_config

MAX_TEXT_CHARS_PER_PAPER = 12000
DEFAULT_BATCH_SIZE = 2
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


def compact_paper(paper: dict[str, Any], text_dir: Path | None, report_index: int | None = None) -> dict[str, Any]:
    text = find_text_for_paper(text_dir, str(paper.get("arxiv_id", "")))
    compacted = {
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
    if report_index is not None:
        compacted["report_index"] = report_index
    return compacted


def read_style_reference(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def build_prompt(
    payload: dict[str, Any],
    text_dir: Path | None,
    style_reference: str,
    batch_start: int = 0,
    total_papers: int | None = None,
) -> str:
    papers = [
        compact_paper(paper, text_dir, batch_start + index + 1)
        for index, paper in enumerate(payload.get("papers", []))
    ]
    total = total_papers or len(papers)
    batch_end = batch_start + len(papers)
    compact_payload = {
        "query": payload.get("query", ""),
        "category": payload.get("category"),
        "sort_by": payload.get("sort_by"),
        "sort_order": payload.get("sort_order"),
        "returned_results": payload.get("returned_results"),
        "batch_start_index": batch_start + 1,
        "batch_end_index": batch_end,
        "total_papers": total,
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
4. 这是分批摘要任务中的第 {batch_start + 1}-{batch_end} 篇，共 {total} 篇；只输出本批输入中的论文，不要输出其他批次。
5. 每篇论文的 `### 摘要` 中，`**研究问题**`、`**研究方法**`、`**研究结论**` 必须分别单独成行；研究结论的每个编号结论也必须单独成行。
6. 必须为输入中的每一篇论文都输出一个编号条目，不要省略、合并或中途停止。

搜索与论文数据如下：

```json
{json.dumps(compact_payload, ensure_ascii=False, indent=2)}
```
""".strip()


def iter_batches(items: list[Any], batch_size: int) -> list[tuple[int, list[Any]]]:
    return [(start, items[start : start + batch_size]) for start in range(0, len(items), batch_size)]


def call_openai(prompt: str, model: str, api_key: str, base_url: str) -> str:
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
    url = base_url.rstrip("/") + "/responses"
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


def call_openai_compatible(prompt: str, model: str, api_key: str, base_url: str) -> str:
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
        raise RuntimeError(f"OpenAI-compatible API 请求失败：HTTP {exc.code} {detail}") from exc

    choices = result.get("choices", [])
    if not choices:
        raise RuntimeError("OpenAI-compatible API 未返回可用 choices。")
    output_text = str(choices[0].get("message", {}).get("content", "")).strip()
    if not output_text:
        raise RuntimeError("OpenAI-compatible API 未返回可用文本。")
    return output_text


def call_provider(prompt: str, provider_settings: dict[str, str], api_key: str) -> str:
    if provider_settings["type"] == "openai-compatible":
        return call_openai_compatible(prompt, provider_settings["model"], api_key, provider_settings["base_url"])
    return call_openai(prompt, provider_settings["model"], api_key, provider_settings["base_url"])


def extract_overall_summary(report: str) -> str:
    match = re.search(r"^##\s+整体摘要\s*$", report, flags=re.MULTILINE)
    if not match:
        return ""
    next_heading = re.search(r"^##\s+", report[match.end() :], flags=re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(report)
    return report[match.end() : end].strip()


def extract_paper_sections(report: str) -> list[str]:
    headings = list(re.finditer(r"^##\s+\d+\.\s+.+$", report, flags=re.MULTILINE))
    sections: list[str] = []
    for heading in headings:
        next_heading = re.search(r"^##\s+", report[heading.end() :], flags=re.MULTILINE)
        section_end = heading.end() + next_heading.start() if next_heading else len(report)
        sections.append(report[heading.start() : section_end].strip())
    return sections


def renumber_paper_section(section: str, number: int) -> str:
    return re.sub(r"^##\s+\d+\.", f"## {number}.", section, count=1, flags=re.MULTILINE)


def normalize_overall_summary(text: str) -> str:
    normalized = re.sub(r"^#+\s*整体摘要\s*", "", text.strip(), flags=re.MULTILINE).strip()
    normalized = re.sub(r"\n{2,}", "\n", normalized)
    if not normalized:
        raise RuntimeError("整体摘要生成失败：模型未返回可用文本。")
    return normalized


def build_overall_summary_prompt(payload: dict[str, Any], paper_sections: list[str]) -> str:
    compact_payload = {
        "query": payload.get("query", ""),
        "paper_count": len(payload.get("papers", [])),
        "papers": [
            {
                "index": index + 1,
                "title": paper.get("title", ""),
                "arxiv_id": paper.get("arxiv_id", ""),
                "primary_category": paper.get("primary_category", ""),
            }
            for index, paper in enumerate(payload.get("papers", []))
        ],
    }
    return f"""
你是面向研究生和博士文献调研的论文速读助手。请根据已经生成的单篇论文摘要，写一段统一的中文整体摘要。

要求：
1. 只输出正文，不要输出 Markdown 标题、列表或“第 1-2 篇”这类分批表述。
2. 输出一段 200-300 字中文，概括全部论文共同关注的问题、主要方法取向、差异和对检索主题的研究价值。
3. 不要编造单篇摘要中没有的信息。
4. 语言应像文献调研报告的整体导读，而不是把各批次摘要简单拼接。

检索信息如下：

```json
{json.dumps(compact_payload, ensure_ascii=False, indent=2)}
```

单篇论文摘要如下：

```markdown
{chr(10).join(paper_sections)}
```
""".strip()


def categories_text(payload: dict[str, Any]) -> str:
    category = payload.get("category")
    if category:
        return str(category)
    categories: list[str] = []
    for paper in payload.get("papers", []):
        primary = str(paper.get("primary_category") or "").strip()
        if primary and primary not in categories:
            categories.append(primary)
    return " / ".join(categories[:4]) if categories else "未指定"


def build_final_report(
    payload: dict[str, Any],
    batch_reports: list[tuple[int, str]],
    batch_size: int,
    overall_summary: str,
) -> str:
    papers = payload.get("papers", [])
    query = payload.get("query", "")
    header = [
        f"# arXiv Discovery：{query}",
        "",
        f"- 搜索关键词：`{query}`",
        f"- arXiv 分类：`{categories_text(payload)}`",
        f"- 排序方式：`{payload.get('sort_by', '')}/{payload.get('sort_order', '')}`",
        f"- 处理论文数：`{len(papers)}`",
        f"- 备注：`摘要按每批 {batch_size} 篇分批生成，并合并为本报告。`",
        "",
        "## 整体摘要",
        "",
        overall_summary,
    ]

    sections: list[str] = []
    for _start, report in batch_reports:
        sections.extend(extract_paper_sections(report))

    merged_sections = [renumber_paper_section(section, index + 1) for index, section in enumerate(sections)]
    return "\n\n".join(part for part in ["\n".join(header).strip(), *merged_sections] if part).strip() + "\n"


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
    parser.add_argument("--provider", choices=provider_names(), help="摘要生成服务；未指定时读取本地配置，默认 kimi。")
    parser.add_argument("--model", help="生成摘要使用的模型；优先级高于本地配置。")
    parser.add_argument("--base-url", help="API base URL；优先级高于本地配置。")
    parser.add_argument("--api-key-env", help="API key 环境变量名；优先级高于本地配置。")
    parser.add_argument("--prompt-output", type=Path, help="可选：保存发送给模型的提示词，便于开发调试。")
    parser.add_argument("--style-reference", type=Path, default=DEFAULT_STYLE_REFERENCE, help="摘要格式和风格要求 Markdown 文件。")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="每次提交给模型总结的论文篇数，默认 2。")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size 必须至少为 1")

    provider_settings = resolve_provider_config(args.provider, args.model, args.base_url, args.api_key_env)
    key_name = provider_settings["api_key_env"]
    api_key = os.environ.get(key_name)
    if not api_key:
        print(f"未检测到 {key_name}，无法自动生成摘要。请通过环境变量、.env 或 run_pipeline.py 交互输入提供 API key。", file=sys.stderr)
        return 2

    payload = read_json(args.results_json)
    style_reference = read_style_reference(args.style_reference)
    papers = list(payload.get("papers", []))
    batches = iter_batches(papers, args.batch_size)
    batch_prompts: list[tuple[int, str]] = []
    for start, batch_papers in batches:
        batch_payload = {**payload, "papers": batch_papers, "returned_results": len(batch_papers)}
        prompt = build_prompt(batch_payload, args.text_dir, style_reference, start, len(papers))
        batch_prompts.append((start, prompt))
    if args.prompt_output:
        args.prompt_output.parent.mkdir(parents=True, exist_ok=True)
        saved_prompts: list[str] = []
        for start, prompt in batch_prompts:
            end = min(start + args.batch_size, len(papers))
            saved_prompts.append(f"<!-- batch {start + 1}-{end} -->\n\n{prompt}")
        args.prompt_output.write_text("\n\n---\n\n".join(saved_prompts), encoding="utf-8")

    batch_reports: list[tuple[int, str]] = []
    for start, prompt in batch_prompts:
        end = min(start + args.batch_size, len(papers))
        print(f"正在生成第 {start + 1}-{end} 篇论文摘要...")
        report = call_provider(prompt, provider_settings, api_key)
        batch_payload = {**payload, "papers": papers[start:end]}
        validate_report_complete(report, batch_payload)
        batch_reports.append((start, report))

    paper_sections: list[str] = []
    for _start, batch_report in batch_reports:
        paper_sections.extend(extract_paper_sections(batch_report))
    overall_prompt = build_overall_summary_prompt(payload, paper_sections)
    if args.prompt_output:
        saved_prompts.append(f"<!-- overall summary -->\n\n{overall_prompt}")
        args.prompt_output.write_text("\n\n---\n\n".join(saved_prompts), encoding="utf-8")

    print("正在生成全部论文的整体摘要...")
    overall_summary = normalize_overall_summary(call_provider(overall_prompt, provider_settings, api_key))

    report = build_final_report(payload, batch_reports, args.batch_size, overall_summary)
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
