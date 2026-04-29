#!/usr/bin/env python3
"""搜索 arXiv，并将规范化后的论文元数据写入 JSON。"""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


API_URL = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def arxiv_date(value: str, end_of_day: bool = False) -> str:
    compact = value.replace("-", "")
    return compact + ("2359" if end_of_day else "0000")


def term_query(value: str) -> str:
    value = value.strip()
    if " " in value:
        return f'all:"{value}"'
    return f"all:{value}"


def build_search_query(query: str, keywords: list[str], category: str | None, date_from: str | None, date_to: str | None) -> str:
    query_terms = keywords or [query]
    parts = [term_query(term) for term in query_terms if term.strip()]
    if category:
        parts.insert(0, f"cat:{category}")
    if date_from or date_to:
        start = arxiv_date(date_from or "1991-01-01")
        end = arxiv_date(date_to or "2099-12-31", end_of_day=True)
        parts.append(f"submittedDate:[{start} TO {end}]")
    return " AND ".join(parts)


def fetch_arxiv(
    query: str,
    max_results: int,
    category: str | None,
    sort_by: str,
    sort_order: str,
    date_from: str | None,
    date_to: str | None,
    retries: int,
    timeout: float,
    keywords: list[str],
) -> str:
    params = {
        "search_query": build_search_query(query, keywords, category, date_from, date_to),
        "start": "0",
        "max_results": str(max_results),
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "arxiv-discovery/1.0"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < retries:
                wait = 5 * (attempt + 1)
                print(f"arXiv 请求过快，等待 {wait} 秒后重试。", file=sys.stderr)
                time.sleep(wait)
                continue
            detail = exc.read().decode("utf-8", errors="ignore")[:500]
            raise RuntimeError(f"arXiv API 请求失败：HTTP {exc.code}。{detail}") from exc
        except urllib.error.URLError as exc:
            if attempt < retries:
                wait = 5 * (attempt + 1)
                print(f"arXiv 网络请求失败，等待 {wait} 秒后重试。", file=sys.stderr)
                time.sleep(wait)
                continue
            raise RuntimeError(f"arXiv API 网络请求失败：{exc}") from exc
        except (socket.timeout, TimeoutError) as exc:
            if attempt < retries:
                wait = 5 * (attempt + 1)
                print(f"arXiv 响应超时，等待 {wait} 秒后重试。", file=sys.stderr)
                time.sleep(wait)
                continue
            raise RuntimeError(f"arXiv API 响应超时：{exc}") from exc
    raise RuntimeError("arXiv API 请求失败。")


def parse_entry(entry: ET.Element) -> dict[str, Any]:
    abstract_url = clean_text(entry.findtext(f"{ATOM}id"))
    arxiv_id = abstract_url.rstrip("/").split("/")[-1]
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    for link in entry.findall(f"{ATOM}link"):
        if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
            pdf_url = link.attrib.get("href", pdf_url)

    categories = [item.attrib.get("term", "") for item in entry.findall(f"{ATOM}category")]
    primary = entry.find(f"{ARXIV}primary_category")
    primary_category = primary.attrib.get("term", "") if primary is not None else ""

    return {
        "arxiv_id": arxiv_id,
        "title": clean_text(entry.findtext(f"{ATOM}title")),
        "summary": clean_text(entry.findtext(f"{ATOM}summary")),
        "authors": [clean_text(author.findtext(f"{ATOM}name")) for author in entry.findall(f"{ATOM}author")],
        "published": clean_text(entry.findtext(f"{ATOM}published")),
        "updated": clean_text(entry.findtext(f"{ATOM}updated")),
        "abstract_url": abstract_url,
        "pdf_url": pdf_url,
        "primary_category": primary_category,
        "categories": [category for category in categories if category],
    }


def parse_feed(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    return [parse_entry(entry) for entry in root.findall(f"{ATOM}entry")]


def main() -> int:
    parser = argparse.ArgumentParser(description="按关键词搜索 arXiv，并写入 results.json。")
    parser.add_argument("query", help="搜索关键词或短语。")
    parser.add_argument("--keyword", action="append", default=[], help="可重复传入的拆分关键词；提供后会用 AND 组合搜索。")
    parser.add_argument("--max-results", type=int, default=6, help="请求结果数量，默认 6。")
    parser.add_argument("--category", help="可选 arXiv 分类，例如 cs.CL 或 stat.ML。")
    parser.add_argument("--date-from", help="可选起始提交日期，格式 YYYY-MM-DD。")
    parser.add_argument("--date-to", help="可选结束提交日期，格式 YYYY-MM-DD。")
    parser.add_argument(
        "--sort-by",
        choices=("relevance", "lastUpdatedDate", "submittedDate"),
        default="relevance",
    )
    parser.add_argument("--sort-order", choices=("ascending", "descending"), default="descending")
    parser.add_argument("--output", type=Path, default=Path("results.json"), help="输出 JSON 路径。")
    parser.add_argument("--sleep", type=float, default=1.0, help="API 请求后的等待秒数。")
    parser.add_argument("--retries", type=int, default=2, help="arXiv 请求失败后的重试次数，默认 2。")
    parser.add_argument("--timeout", type=float, default=60.0, help="arXiv 单次请求超时时间，默认 60 秒。")
    args = parser.parse_args()

    if args.max_results < 1:
        parser.error("--max-results 必须至少为 1")

    try:
        xml_text = fetch_arxiv(
            args.query,
            args.max_results,
            args.category,
            args.sort_by,
            args.sort_order,
            args.date_from,
            args.date_to,
            args.retries,
            args.timeout,
            args.keyword,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    time.sleep(max(args.sleep, 0))
    papers = parse_feed(xml_text)
    payload = {
        "query": args.query,
        "category": args.category,
        "sort_by": args.sort_by,
        "sort_order": args.sort_order,
        "requested_results": args.max_results,
        "date_from": args.date_from,
        "date_to": args.date_to,
        "keywords": args.keyword or [args.query],
        "returned_results": len(papers),
        "papers": papers,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {len(papers)} 条结果：{args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        raise SystemExit(130)
