#!/usr/bin/env python3
"""把 results.json 和 report.md 导出为可直接打开的单文件 HTML 页面。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PAGE_DIR = SCRIPT_DIR.parent / "page"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def build_html(results_json: Path, report_md: Path | None) -> str:
    index = read_text(PAGE_DIR / "index.html")
    styles = read_text(PAGE_DIR / "styles.css")
    app = read_text(PAGE_DIR / "app.js")
    results = json.loads(read_text(results_json))
    report_text = read_text(report_md) if report_md and report_md.exists() else ""
    data_script = (
        "<script>\n"
        "window.ARXIV_DISCOVERY_DATA = "
        + json.dumps({"results": results, "reportText": report_text}, ensure_ascii=False)
        + ";\n"
        "</script>"
    )
    html = index.replace('<link rel="stylesheet" href="./styles.css" />', f"<style>\n{styles}\n</style>")
    html = html.replace("<body>", '<body class="is-exported">')
    html = re.sub(r'\s*<div class="import-panel" aria-label="导入文件">[\s\S]*?</div>\s*', "\n", html, count=1)
    html = html.replace('<script src="./app.js"></script>', f"{data_script}\n<script>\n{app}\n</script>")
    return html


def main() -> int:
    parser = argparse.ArgumentParser(description="导出 arXiv Discovery 单文件 HTML 报告。")
    parser.add_argument("results_json", type=Path, help="完整流程生成的 results.json。")
    parser.add_argument("--report", type=Path, help="完整流程生成的 report.md。")
    parser.add_argument("--output", type=Path, default=Path("index.html"), help="输出 HTML 路径。")
    args = parser.parse_args()

    html = build_html(args.results_json, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"已生成 HTML 页面：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
