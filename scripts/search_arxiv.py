#!/usr/bin/env python3
"""搜索 arXiv，并将规范化后的论文元数据写入 JSON。"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
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


def build_search_query(query: str, category: str | None) -> str:
    terms = f'all:"{query}"' if " " in query.strip() else f"all:{query.strip()}"
    if category:
        return f"cat:{category} AND {terms}"
    return terms


def fetch_arxiv(
    query: str,
    max_results: int,
    category: str | None,
    sort_by: str,
    sort_order: str,
) -> str:
    params = {
        "search_query": build_search_query(query, category),
        "start": "0",
        "max_results": str(max_results),
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "arxiv-discovery/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


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
    parser.add_argument("--max-results", type=int, default=5, help="请求结果数量，默认 5。")
    parser.add_argument("--category", help="可选 arXiv 分类，例如 cs.CL 或 stat.ML。")
    parser.add_argument(
        "--sort-by",
        choices=("relevance", "lastUpdatedDate", "submittedDate"),
        default="relevance",
    )
    parser.add_argument("--sort-order", choices=("ascending", "descending"), default="descending")
    parser.add_argument("--output", type=Path, default=Path("results.json"), help="输出 JSON 路径。")
    parser.add_argument("--sleep", type=float, default=1.0, help="API 请求后的等待秒数。")
    args = parser.parse_args()

    if args.max_results < 1:
        parser.error("--max-results 必须至少为 1")

    xml_text = fetch_arxiv(args.query, args.max_results, args.category, args.sort_by, args.sort_order)
    time.sleep(max(args.sleep, 0))
    papers = parse_feed(xml_text)
    payload = {
        "query": args.query,
        "category": args.category,
        "sort_by": args.sort_by,
        "sort_order": args.sort_order,
        "requested_results": args.max_results,
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
