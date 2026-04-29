---
name: arxiv-discovery
description: 按关键词搜索 arXiv、批量下载论文 PDF、解析论文正文，并为研究生和博士文献调研生成结构化中文摘要。适用于论文速读、arXiv 文献发现、关键词文献综述、批量 PDF 总结、研究选题调研，以及按查询相关性筛选论文等任务。
---

# ArXiv Discovery

## 目标

使用本 skill 帮助研究生和博士研究者从一个关键词快速得到一组适合文献调研的论文：搜索 arXiv、下载 PDF、提取论文正文，并调用 OpenAI 或 Kimi API 输出结构化中文摘要报告。

默认行为：
- 默认处理 6 篇论文，除非用户明确指定其他数量。
- 如果可用结果不足，则处理 3 篇或全部可用论文。
- 论文题目保留英文原文。
- 每篇论文摘要使用中文撰写，长度控制在 200-300 个中文字符。
- 每篇论文必须按“摘要”和“推荐原因”两部分输出；“摘要”内的“研究问题”“研究方法”“研究结论”需加粗并各自另起一行，研究结论的每个编号点也需单独成行。
- 全部单篇摘要之外，额外生成一段约 100 个中文字符的整体摘要，概括本批论文的共同主题、主要方法或研究价值。
- 如果运行流水线时没有提供需求，脚本必须在终端主动询问用户的论文查找要求。
- 用户需求可以是中文或英文，流水线会解析搜索关键词、论文篇数和时间范围。
- 自动生成摘要支持一次性配置：优先运行 `scripts/configure_provider.py` 写入本地 provider 配置和可选 `.env`；如果仍未找到 API key，`run_pipeline.py` 会交互询问，输入不会回显。不要把 API key 写进代码、命令行参数或日志。

## 输入

当用户提供以下信息时，应尽量识别并使用：
- `query`：自然语言论文查找要求，例如 `帮我找近三年 8 篇 LLM 和 RAG 相关论文` 或 `find 8 recent papers about retrieval augmented generation in the last 3 years`；如果命令行未提供，流水线会主动询问。
- `max_results`：可选，处理论文数量；如果未指定，优先从用户需求中解析，默认值为 `6`。
- `category`：可选，arXiv 分类，例如 `cs.CL`、`cs.LG`、`stat.ML`。
- `sort_by`：可选，排序方式，可取 `relevance`、`submittedDate` 或 `lastUpdatedDate`；默认值为 `relevance`。
- `sort_order`：可选，排序顺序，可取 `descending` 或 `ascending`；默认值为 `descending`。
- `date_range`：可选，自然语言时间范围；如果无法直接通过 arXiv API 表达，则在最终筛选时应用。
- `date_from` / `date_to`：可选，显式 arXiv 提交日期范围，格式 `YYYY-MM-DD`；优先级高于自然语言解析结果。
- `output_dir`：可选，用于保存 PDF、正文文本和 JSON 元数据的目录。
- `provider`：可选，摘要生成服务，可取 `kimi` 或 `openai`；未指定时读取本地配置，默认值为 `kimi`。
- `model`：可选，生成摘要使用的模型；优先级高于本地配置。
- `base_url`：可选，API base URL；优先级高于本地配置。
- `api_key_env`：可选，API key 环境变量名；优先级高于本地配置。

## 输出

输出一份 Markdown 格式的文献调研报告，包含：
- 搜索关键词和筛选条件。
- 论文选择方法和实际处理数量。
- 对比表格：题目、arXiv ID、年份或日期、作者、相关性、阅读优先级。
- 一段约 100 个中文字符的整体摘要，总结返回论文的共同主题和整体价值。
- 每篇论文一个条目，题目保留英文，并严格包含“摘要”和“推荐原因”两个小节。
- 简短的推荐阅读顺序，说明哪些论文应该优先阅读以及原因。

每篇论文至少包含：
- 英文论文题目。
- arXiv ID，以及摘要页和 PDF 链接。
- “摘要”：200-300 个中文字符，写清楚研究问题、方法、主要结论，以及与搜索关键词的相关性；“研究问题”“研究方法”“研究结论”需作为加粗小标题单独成行，研究结论每个点单独成行。
- “推荐原因”：1-2 句中文，说明这篇论文为什么值得研究生或博士在当前主题下阅读。

最终报告的具体结构参考 `references/summary_schema.md`。

## 工作流程

1. 只有当用户关键词含义过于模糊、会明显影响搜索方向时，才先追问必要信息。
2. 标准流程优先使用 `scripts/run_pipeline.py`，完成需求解析、搜索、下载、正文提取、摘要生成和 HTML 导出。
3. `run_pipeline.py` 会先调用 `scripts/parse_request.py`，把中英文自然语言需求解析成关键词、篇数和时间范围，并写入 `request.json`。多个关键词会在 arXiv 查询中用 AND 组合搜索。
4. `run_pipeline.py` 会调用 `scripts/generate_summary.py`，读取 `results.json` 和 `text/` 目录，生成 `report.md`。摘要格式和风格要求必须来自 `references/summary_schema.md`。
5. 摘要生成配置优先级为命令行参数、本地 `.env` / 环境变量、本地 `.local/provider.json`、内置默认值；如果仍未设置当前 provider 对应的 API key，`run_pipeline.py` 应交互询问 API key。
6. `run_pipeline.py` 最后调用 `scripts/export_html.py`，生成可直接打开的 `index.html`。
7. 摘要报告必须先写整体摘要，再写每篇论文的“摘要”和“推荐原因”。
8. 明确说明被跳过的 PDF、解析失败的论文，以及与关键词相关性较弱的结果。

## 运行流水线

首次使用建议先做一次本地配置：

```bash
python3 scripts/configure_provider.py
```

该命令会写入 `.local/provider.json`；如果选择保存 API key，会写入已被 `.gitignore` 忽略的 `.env`。仓库只保留 `.env.example` 模板，不保存真实密钥。

在本 skill 目录中运行：

```bash
python3 scripts/run_pipeline.py "帮我找近三年 6 篇 retrieval augmented generation 相关论文" --category cs.CL --output-dir ./runs/rag
```

如果省略关键词，脚本会主动询问：

```bash
python3 scripts/run_pipeline.py --category cs.CL --output-dir ./runs/rag
```

也可以通过 `.env` 或环境变量直接配置。Kimi 示例：

```bash
export KIMI_API_KEY="你的 Kimi API key"
```

OpenAI 需要显式指定 `--provider openai`。示例：

```bash
export OPENAI_API_KEY="你的 OpenAI API key"
python3 scripts/run_pipeline.py "retrieval augmented generation" --max-results 6 --category cs.CL --provider openai --output-dir ./runs/rag
```

如果没有设置 `.env` 或环境变量，`run_pipeline.py` 会在需要生成摘要时询问 API key，输入内容不会显示，也不会保存到文件。

完整流水线会生成：
- `request.json`：从用户自然语言需求中解析出的关键词、篇数和时间范围。
- `results.json`：arXiv 搜索结果和论文元数据。
- `pdfs/`：下载的论文 PDF。
- `text/`：提取出的论文正文。
- `report.md`：最终中文论文速读报告。
- `index.html`：最终 HTML 论文雷达页面，打开即可查看结果。

## HTML 论文雷达页面

本 skill 附带一个静态 HTML 页面：

```text
page/index.html
```

该页面可直接用浏览器打开，不需要构建工具或本地服务。流水线会在每个运行目录下生成内嵌当前结果的 `index.html`，这是最终结果页，打开后不需要再手动导入 JSON 或 Markdown。`page/index.html` 仅作为开发预览模板保留。页面包含：
- Hero 概览区：关键词、论文数量和排序方式。
- 整体摘要区：展示 `report.md` 中的“整体摘要”。
- 论文卡片区：展示英文题目、作者、日期、arXiv 链接、PDF 链接、中文摘要和推荐原因。
- SVG 雷达图：根据本地元数据和摘要长度生成相关性、摘要完整度、元数据完整度、时效性和推荐理由完整度评分。
- 归档表：按导入顺序展示论文列表。
- 顶部导航和关键词搜索。

页面不发起外部网络请求，不处理 API key，也不包含遥测逻辑。对于流水线导出的 `runs/<query>/index.html`，数据已内嵌在 HTML 中；用户只需要打开最终 HTML 文件即可查看结果。

也可以分步骤运行：

```bash
python3 scripts/search_arxiv.py "diffusion models" --max-results 6 --sort-by submittedDate --output ./runs/diffusion/results.json
python3 scripts/download_pdfs.py ./runs/diffusion/results.json --output-dir ./runs/diffusion/pdfs
python3 scripts/extract_pdf_text.py ./runs/diffusion/pdfs --output-dir ./runs/diffusion/text
python3 scripts/generate_summary.py ./runs/diffusion/results.json --text-dir ./runs/diffusion/text --output ./runs/diffusion/report.md
python3 scripts/generate_summary.py ./runs/diffusion/results.json --text-dir ./runs/diffusion/text --output ./runs/diffusion/report.md
python3 scripts/export_html.py ./runs/diffusion/results.json --report ./runs/diffusion/report.md --output ./runs/diffusion/index.html
```

脚本只使用 arXiv 官方公开接口进行网络访问：
- `https://export.arxiv.org/api/query`
- `https://arxiv.org/pdf/<arxiv_id>.pdf`

PDF 正文解析会按顺序尝试本地已安装的解析库：先尝试 `PyMuPDF`（`fitz`），再尝试 `pypdf`。如果两者都不存在，应提示用户安装其中一个库，或请用户提供已提取的正文文本。摘要生成支持 OpenAI Responses API 和 OpenAI-compatible chat completions 接口，API key 可来自 `.env`、环境变量或 `run_pipeline.py` 的交互输入。arXiv 搜索会对 429、网络错误和响应超时做有限重试，并输出中文错误信息。

## 触发词

以下请求应触发本 skill：
- `论文速读：帮我搜 arXiv 上 RAG 的最新论文并总结 6 篇`
- `用 arxiv-discovery 搜 efficient LLM inference`
- `按关键词帮我做博士文献调研`
- `批量下载并总结 arXiv paper`
- `找 3 篇和 diffusion policy 相关的论文，中文总结`

## 使用示例

用户请求：

```text
用 arxiv-discovery 搜索 multi-agent reinforcement learning，默认 6 篇，输出中文摘要。
```

应执行：

```bash
python3 scripts/run_pipeline.py "multi-agent reinforcement learning" --max-results 6 --output-dir ./runs/marl
```

流水线完成后，读取 `./runs/marl/report.md`，其中应包含整体摘要，并为每篇论文输出英文题目、中文“摘要”和“推荐原因”。

用户请求：

```text
帮我找 cs.CL 里和 hallucination detection 相关的 3 篇论文，按相关性排序。
```

应执行：

```bash
python3 scripts/run_pipeline.py "hallucination detection" --max-results 3 --category cs.CL --sort-by relevance --output-dir ./runs/hallucination-detection
```

## 失败处理

- 如果 arXiv 返回结果过少，应说明实际返回数量，并继续处理可用论文。
- 如果 PDF 下载失败，应保留论文元数据，并在报告中标记下载失败。
- 如果正文提取失败，应只基于题目和摘要总结，并明确标记该限制。
- 如果未设置当前 provider 对应的 API key，应交互询问用户输入；如果用户留空，应说明当前只生成了搜索、PDF 和正文提取产物。
- 如果关键词过宽，应优先选择题目或摘要中直接出现关键词的论文。
- 不要编造论文中没有体现的研究结论、实验结果或贡献。

## 参考资料

- 修改搜索行为或查询语法前，阅读 `references/arxiv_api.md`。
- 生成最终文献调研报告前，阅读 `references/summary_schema.md`。
- 展示最终报告时，优先打开流水线生成的 `runs/<query>/index.html`；开发预览时可以打开 `page/index.html` 并手动导入 `results.json` 和 `report.md`。
