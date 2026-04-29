---
name: arxiv-discovery
description: 按关键词搜索 arXiv、下载论文 PDF、提取正文，并生成中文结构化论文速读报告。适用于 arXiv 文献发现、关键词文献综述、论文批量总结、研究选题调研和论文速读页面导出。
---

# ArXiv Discovery

## 适用场景

当用户要查找、下载、总结或导出 arXiv 论文时使用本 skill。典型任务包括：

- 按关键词找论文并中文总结。
- 批量下载 arXiv PDF 并提取正文。
- 从自然语言需求解析关键词、篇数和时间范围。
- 生成 `report.md` 和可直接打开的 `index.html`。

## 触发词

出现以下意图或近似表达时，应优先使用本 skill：

- `arXiv 搜索`
- `帮我找论文`
- `论文速读`
- `文献综述`
- `批量总结 paper`
- `下载 arXiv PDF`
- `生成论文报告`
- `导出论文页面`

## 默认行为

- 默认返回并处理 6 篇论文，除非用户指定其他数量。
- 搜索源是 arXiv 官方 Atom API。
- 多关键词会用 AND 组合搜索。
- 摘要 provider 默认读取本地配置；未配置时默认 `kimi`。
- 摘要输出必须遵守 `references/summary_schema.md`。
- 真实 API key 只能来自环境变量、被忽略的 `.env`，或运行时交互输入；不要写入代码、日志、提示词或可提交文件。

## 标准流程

优先运行完整流程：

```bash
python3 scripts/run_pipeline.py "<论文检索需求>"
```

常用参数：

```bash
--max-results 6
--category cs.CL
--date-from YYYY-MM-DD
--date-to YYYY-MM-DD
--provider kimi|openai
--model <model>
--skip-summary
--skip-html
```

如果用户还没有配置摘要服务，先运行：

```bash
python3 scripts/configure_provider.py
```

配置优先级：

```text
命令行参数 > .env / 环境变量 > .local/provider.json > 内置默认值
```

## 分步命令

需要单独调试时再分步运行：

```bash
python3 scripts/search_arxiv.py "<query>" --max-results 6 --output ./runs/demo/results.json
python3 scripts/download_pdfs.py ./runs/demo/results.json --output-dir ./runs/demo/pdfs
python3 scripts/extract_pdf_text.py ./runs/demo/pdfs --output-dir ./runs/demo/text
python3 scripts/generate_summary.py ./runs/demo/results.json --text-dir ./runs/demo/text --output ./runs/demo/report.md
python3 scripts/export_html.py ./runs/demo/results.json --report ./runs/demo/report.md --output ./runs/demo/index.html
```

## 输出产物

完整流程默认生成到 `runs/<query-slug>/`：

- `request.json`：自然语言需求解析结果。
- `results.json`：arXiv 搜索元数据。
- `pdfs/`：下载的 PDF 和下载清单。
- `text/`：提取出的正文和提取清单。
- `report.md`：中文结构化论文速读报告。
- `index.html`：内嵌数据的单文件 HTML 页面。

## 失败处理

- arXiv 返回 0 篇时停止后续下载、解析和摘要生成。
- PDF 下载或正文提取失败时保留 manifest 中的错误状态，继续处理其他论文。
- 缺少 API key 时，`run_pipeline.py` 会交互询问；用户不提供则跳过摘要生成。
- `generate_summary.py` 会校验报告完整性；如果模型输出被截断或缺少必需小节，应失败而不是写入不完整报告。
- 如果 arXiv 网络持续失败，说明当前实现只有 arXiv 官方 API；备用搜索源需另行实现。

## 参考文件

- 搜索语法或 arXiv API 行为：读取 `references/arxiv_api.md`。
- 摘要格式、字段和质量要求：读取 `references/summary_schema.md`。
- 用户安装和发布说明：读取仓库根目录 `README.md`。
