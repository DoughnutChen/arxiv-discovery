#!/usr/bin/env python3
"""下载 arXiv 搜索结果 JSON 中列出的论文 PDF。"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")


def download(url: str, destination: Path, overwrite: bool) -> str:
    if destination.exists() and not overwrite:
        return "exists"
    request = urllib.request.Request(url, headers={"User-Agent": "arxiv-discovery/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    if not data.startswith(b"%PDF"):
        raise ValueError("下载内容不像 PDF 文件")
    destination.write_bytes(data)
    return "downloaded"


def main() -> int:
    parser = argparse.ArgumentParser(description="根据 arXiv 搜索结果 JSON 下载 PDF。")
    parser.add_argument("results_json", type=Path, help="search_arxiv.py 生成的 JSON。")
    parser.add_argument("--output-dir", type=Path, default=Path("pdfs"), help="PDF 保存目录。")
    parser.add_argument("--overwrite", action="store_true", help="即使 PDF 已存在也重新下载。")
    parser.add_argument("--sleep", type=float, default=3.0, help="下载间隔秒数，默认 3。")
    args = parser.parse_args()

    payload: dict[str, Any] = json.loads(args.results_json.read_text(encoding="utf-8"))
    papers = payload.get("papers", [])
    args.output_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for index, paper in enumerate(papers, start=1):
        arxiv_id = paper.get("arxiv_id", f"paper-{index}")
        filename = f"{safe_name(arxiv_id)}.pdf"
        destination = args.output_dir / filename
        status = "failed"
        error = ""
        try:
            status = download(paper["pdf_url"], destination, args.overwrite)
        except Exception as exc:  # noqa: BLE001 - 批处理命令需要保留每篇论文的处理状态。
            error = str(exc)
        manifest.append(
            {
                "arxiv_id": arxiv_id,
                "title": paper.get("title", ""),
                "pdf_url": paper.get("pdf_url", ""),
                "pdf_path": str(destination) if destination.exists() else "",
                "status": status,
                "error": error,
            }
        )
        print(f"[{index}/{len(papers)}] {arxiv_id}: {status}{f' ({error})' if error else ''}")
        if index < len(papers):
            time.sleep(max(args.sleep, 0))

    manifest_path = args.output_dir / "download_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入下载清单：{manifest_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        raise SystemExit(130)
