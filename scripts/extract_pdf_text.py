#!/usr/bin/env python3
"""优先使用 PyMuPDF 或 pypdf 从 PDF 中提取正文。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Callable


def normalize_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"-\n(?=[a-z])", "", text)
    text = re.sub(r"(?<![.!?:;。！？：；])\n(?!\n)", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_with_pymupdf(path: Path) -> tuple[str, int]:
    import fitz  # type: ignore[import-not-found]

    parts = []
    with fitz.open(path) as document:
        for page in document:
            parts.append(page.get_text("text"))
        return normalize_text("\n\n".join(parts)), document.page_count


def extract_with_pypdf(path: Path) -> tuple[str, int]:
    from pypdf import PdfReader  # type: ignore[import-not-found]

    reader = PdfReader(str(path))
    parts = [page.extract_text() or "" for page in reader.pages]
    return normalize_text("\n\n".join(parts)), len(reader.pages)


def choose_extractor() -> tuple[str, Callable[[Path], tuple[str, int]]]:
    try:
        import fitz  # noqa: F401

        return "pymupdf", extract_with_pymupdf
    except Exception:
        pass

    try:
        import pypdf  # noqa: F401

        return "pypdf", extract_with_pypdf
    except Exception:
        pass

    raise RuntimeError("未找到 PDF 解析库。请安装 PyMuPDF：`python3 -m pip install PyMuPDF`，或安装 pypdf：`python3 -m pip install pypdf`。")


def iter_pdfs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(input_path.glob("*.pdf"))


def main() -> int:
    parser = argparse.ArgumentParser(description="从单个 PDF 或 PDF 目录中提取正文。")
    parser.add_argument("input", type=Path, help="PDF 文件，或包含 PDF 的目录。")
    parser.add_argument("--output-dir", type=Path, default=Path("text"), help="提取后的 .txt 文件目录。")
    args = parser.parse_args()

    extractor_name, extractor = choose_extractor()
    pdfs = iter_pdfs(args.input)
    if not pdfs:
        parser.error(f"未在 {args.input} 找到 PDF 文件")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for index, pdf in enumerate(pdfs, start=1):
        output = args.output_dir / f"{pdf.stem}.txt"
        status = "failed"
        error = ""
        pages = 0
        chars = 0
        try:
            text, pages = extractor(pdf)
            output.write_text(text, encoding="utf-8")
            chars = len(text)
            status = "extracted" if text else "empty"
        except Exception as exc:  # noqa: BLE001 - 批处理命令需要继续处理其他 PDF。
            error = str(exc)
        manifest.append(
            {
                "pdf_path": str(pdf),
                "text_path": str(output) if output.exists() else "",
                "status": status,
                "extractor": extractor_name,
                "pages": pages,
                "characters": chars,
                "error": error,
            }
        )
        print(f"[{index}/{len(pdfs)}] {pdf.name}: {status}, pages={pages}, chars={chars}{f' ({error})' if error else ''}")

    manifest_path = args.output_dir / "extract_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入提取清单：{manifest_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        raise SystemExit(130)
