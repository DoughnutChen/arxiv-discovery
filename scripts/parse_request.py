#!/usr/bin/env python3
"""从中英文自然语言需求中解析 arXiv 搜索参数。"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any


DEFAULT_MAX_RESULTS = 6

TERM_MAP = {
    "大语言模型": "large language model",
    "大型语言模型": "large language model",
    "语言模型": "language model",
    "人工智能": "artificial intelligence",
    "机器学习": "machine learning",
    "深度学习": "deep learning",
    "神经网络": "neural network",
    "检索增强生成": "retrieval augmented generation",
    "多模态": "multimodal",
    "强化学习": "reinforcement learning",
    "计算机视觉": "computer vision",
    "自然语言处理": "natural language processing",
    "知识图谱": "knowledge graph",
}

CHINESE_DIGITS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def parse_count(text: str) -> int:
    patterns = [
        r"(\d+)\s*(?:篇|篇论文|papers?|articles?)",
        r"(?:top|前|找|搜索|总结)\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return max(1, int(match.group(1)))
    match = re.search(r"([一二两三四五六七八九十])\s*(?:篇|篇论文)", text)
    if match:
        return CHINESE_DIGITS.get(match.group(1), DEFAULT_MAX_RESULTS)
    return DEFAULT_MAX_RESULTS


def parse_date_range(text: str, today: date) -> tuple[str | None, str | None, str]:
    lowered = text.lower()
    match = re.search(r"(?:近|过去|最近)\s*(\d+|[一二两三四五六七八九十])\s*年", text)
    if match:
        years = number_value(match.group(1))
        return iso(today - timedelta(days=365 * years)), iso(today), f"近 {years} 年"
    match = re.search(r"last\s+(\d+)\s+years?", lowered)
    if match:
        years = int(match.group(1))
        return iso(today - timedelta(days=365 * years)), iso(today), f"last {years} years"
    match = re.search(r"(?:近|过去|最近)\s*(\d+|[一二两三四五六七八九十])\s*个月", text)
    if match:
        months = number_value(match.group(1))
        return iso(today - timedelta(days=30 * months)), iso(today), f"近 {months} 个月"
    match = re.search(r"last\s+(\d+)\s+months?", lowered)
    if match:
        months = int(match.group(1))
        return iso(today - timedelta(days=30 * months)), iso(today), f"last {months} months"
    match = re.search(r"(?:近|过去|最近)\s*(\d+|[一二两三四五六七八九十])\s*天", text)
    if match:
        days = number_value(match.group(1))
        return iso(today - timedelta(days=days)), iso(today), f"近 {days} 天"
    match = re.search(r"last\s+(\d+)\s+days?", lowered)
    if match:
        days = int(match.group(1))
        return iso(today - timedelta(days=days)), iso(today), f"last {days} days"
    match = re.search(r"(?:since|after|自|从)\s*(\d{4}-\d{1,2}-\d{1,2})", lowered)
    if match:
        return normalize_date(match.group(1)), iso(today), f"since {match.group(1)}"
    match = re.search(r"(\d{4}-\d{1,2}-\d{1,2})\s*(?:到|至|~|-|to)\s*(\d{4}-\d{1,2}-\d{1,2})", lowered)
    if match:
        return normalize_date(match.group(1)), normalize_date(match.group(2)), "explicit range"
    return None, None, ""


def number_value(value: str) -> int:
    if value.isdigit():
        return int(value)
    return CHINESE_DIGITS.get(value, DEFAULT_MAX_RESULTS)


def iso(value: date) -> str:
    return value.isoformat()


def normalize_date(value: str) -> str:
    parts = [int(part) for part in value.split("-")]
    return date(parts[0], parts[1], parts[2]).isoformat()


def extract_keywords(text: str) -> list[str]:
    mapped = [english for chinese, english in TERM_MAP.items() if chinese in text]
    explicit_topics = []
    topic_match_en = re.search(r"(?:about|on|related to)\s+(.+?)(?:\s+(?:in|from|since|during|over|for|last)\b|$)", text, re.IGNORECASE)
    if topic_match_en:
        explicit_topics.append(topic_match_en.group(1).strip(" ：:，,。."))
    english_terms = re.findall(r"[A-Za-z][A-Za-z0-9+-]*(?:\s+[A-Za-z][A-Za-z0-9+-]*){0,4}", text)
    cleaned = []
    stop = {
        "find",
        "search",
        "papers",
        "paper",
        "articles",
        "article",
        "latest",
        "recent",
        "last",
        "years",
        "year",
        "months",
        "month",
        "days",
        "day",
        "about",
        "in",
        "the",
        "related",
        "with",
        "on",
        "top",
        "summarize",
        "arxiv",
    }
    for term in english_terms:
        words = [word for word in term.strip().split() if word.lower() not in stop]
        if words:
            cleaned.append(" ".join(words))
    topic_match = re.search(r"(?:关于|有关|主题是|方向是)(.+?)(?:的论文|论文|$)", text)
    if topic_match:
        topic = topic_match.group(1).strip(" ：:，,。.")
        for chinese, english in TERM_MAP.items():
            topic = topic.replace(chinese, english)
        if topic:
            cleaned.append(topic)
    result = []
    for item in [*mapped, *explicit_topics, *cleaned]:
        normalized = re.sub(r"\s+", " ", item).strip(" ：:，,。.")
        if normalized and normalized.lower() not in {value.lower() for value in result}:
            result.append(normalized)
    return result


def strip_control_phrases(text: str) -> str:
    value = text
    value = re.sub(r"(\d+|[一二两三四五六七八九十])\s*(篇|篇论文|papers?|articles?)", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"(近|过去|最近)\s*(\d+|[一二两三四五六七八九十])\s*(年|个月|天)", " ", value)
    value = re.sub(r"last\s+\d+\s+(years?|months?|days?)", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"(请|帮我|给我|搜索|查找|找|总结|论文|文献|arxiv|ArXiv)", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" ：:，,。.")


def parse_request(text: str, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    max_results = parse_count(text)
    date_from, date_to, date_note = parse_date_range(text, today)
    keywords = extract_keywords(text)
    fallback = strip_control_phrases(text)
    search_query = " ".join(keywords) if keywords else fallback
    if not search_query:
        search_query = text.strip()
    return {
        "raw_query": text,
        "search_query": search_query,
        "keywords": keywords or [search_query],
        "max_results": max_results,
        "date_from": date_from,
        "date_to": date_to,
        "date_note": date_note,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="解析中英文论文检索需求。")
    parser.add_argument("request", help="用户的自然语言论文检索需求。")
    parser.add_argument("--output", type=Path, help="可选：写入解析结果 JSON。")
    args = parser.parse_args()

    payload = parse_request(args.request)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
