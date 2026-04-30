# ArXiv Discovery Skill

`arxiv-discovery` 是一个 Codex skill，用于按关键词搜索 arXiv、下载论文 PDF、提取正文，并生成中文论文速读报告和可直接打开的 HTML 页面。
飞书说明文档：https://jcn7zice1pwy.feishu.cn/wiki/DtPOweLgSiChQ3kp6iVcnpUKnYd

## 安装

将本仓库克隆到本地后，把 skill 目录复制到 Codex skills 目录：

```bash
git clone https://github.com/DoughnutChen/arxiv-discovery/tree/master
mkdir -p ~/.codex/skills
cp -R arxiv-discovery-skill/arxiv-discovery ~/.codex/skills/arxiv-discovery
```

如果你已经在本仓库根目录，也可以直接执行：

```bash
mkdir -p ~/.codex/skills
cp -R arxiv-discovery ~/.codex/skills/arxiv-discovery
```

进入 skill 目录：

```bash
cd ~/.codex/skills/arxiv-discovery
```

## 配置

首次使用建议运行一次配置命令：

```bash
python3 scripts/configure_provider.py
```

该命令会配置：

- 默认摘要 provider：`kimi` 或 `openai`
- 默认模型
- API base URL
- API key 对应的环境变量名
- 可选：把 API key 写入本地 `.env`

真实 API key 只应放在环境变量或本地 `.env` 中。`.env` 和 `.local/` 已被 `.gitignore` 忽略，不应提交到仓库。

也可以复制模板手动配置：

```bash
cp .env.example .env
```

然后编辑 `.env`，填入自己的 API key。

配置优先级为：

```text
命令行参数 > .env / 环境变量 > .local/provider.json > 内置默认值
```

## 运行示例

搜索并生成完整报告：

```bash
python3 scripts/run_pipeline.py "帮我找近三年 4 篇 Agent 相关论文"
```

指定论文数量：

```bash
python3 scripts/run_pipeline.py "large language model inference" --max-results 6
```


分步骤运行：

```bash
python3 scripts/search_arxiv.py "diffusion models" --max-results 6 --output ./runs/diffusion/results.json
python3 scripts/download_pdfs.py ./runs/diffusion/results.json --output-dir ./runs/diffusion/pdfs
python3 scripts/extract_pdf_text.py ./runs/diffusion/pdfs --output-dir ./runs/diffusion/text
python3 scripts/generate_summary.py ./runs/diffusion/results.json --text-dir ./runs/diffusion/text --output ./runs/diffusion/report.md --batch-size 2
python3 scripts/export_html.py ./runs/diffusion/results.json --report ./runs/diffusion/report.md --output ./runs/diffusion/index.html
```

## 输出文件

默认输出到 `runs/<query>/`：

- `request.json`：自然语言需求解析结果
- `results.json`：论文元数据
- `pdfs/`：下载的 PDF
- `text/`：提取出的正文
- `report.md`：中文论文速读报告
- `index.html`：可直接打开的 HTML 页面

## 注意事项

- 不要提交 `.env`、`.local/`、`runs/`、PDF 或生成的报告。
- 如果 arXiv 网络请求失败，可以稍后重试，或扩展搜索脚本接入 Semantic Scholar / OpenAlex 等备用源。
- 摘要生成默认每次提交 2 篇论文给模型；全部批次完成后，会把所有单篇摘要再次输入模型，生成统一的整体摘要并合并为一个 `report.md`。如果任一批次不完整，脚本会报错，避免留下截断报告。
