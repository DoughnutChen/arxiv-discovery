const state = {
  results: null,
  reportText: "",
  parsedReport: { overall: "", papers: [] },
  mergedPapers: [],
};

const nodes = {
  resultsFile: document.querySelector("#resultsFile"),
  reportFile: document.querySelector("#reportFile"),
  keywordInput: document.querySelector("#keywordInput"),
  paperCount: document.querySelector("#paperCount"),
  sortValue: document.querySelector("#sortValue"),
  queryValue: document.querySelector("#queryValue"),
  heroText: document.querySelector("#heroText"),
  overallSummary: document.querySelector("#overallSummary"),
  paperGrid: document.querySelector("#paperGrid"),
  archiveBody: document.querySelector("#archiveBody"),
  paperTemplate: document.querySelector("#paperTemplate"),
};

if (nodes.resultsFile) {
  nodes.resultsFile.addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    state.results = JSON.parse(text);
    render();
  });
}

if (nodes.reportFile) {
  nodes.reportFile.addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    state.reportText = await file.text();
    state.parsedReport = parseReport(state.reportText);
    render();
  });
}

nodes.keywordInput.addEventListener("input", () => {
  applySearch(nodes.keywordInput.value.trim());
});

const embedded = window.ARXIV_DISCOVERY_DATA;
if (embedded?.results) {
  document.body.classList.add("is-exported");
  state.results = embedded.results;
  state.reportText = embedded.reportText || "";
  state.parsedReport = parseReport(state.reportText);
  render();
}

function parseReport(markdown) {
  const overallMatch = markdown.match(/##\s*整体摘要\s*([\s\S]*?)(?=\n##\s+\d+\.|\n##\s+阅读顺序|\n##\s+[^\n]+|$)/);
  const papers = [];
  const paperPattern = /##\s+(\d+)\.\s+(.+?)\n([\s\S]*?)(?=\n##\s+\d+\.|\n##\s+阅读顺序|$)/g;
  let match;
  while ((match = paperPattern.exec(markdown)) !== null) {
    const body = match[3];
    papers.push({
      index: Number(match[1]),
      title: match[2].trim(),
      arxivId: pick(body, /arXiv ID[：:]\s*`?([^`\n]+)`?/),
      authors: pick(body, /作者[：:]\s*([^\n]+)/),
      date: pick(body, /发布\/更新[：:]\s*([^\n]+)/),
      summaryParts: researchSummaryParts(body),
      summary: researchSummary(body),
      field: section(body, "具体领域"),
      reason: section(body, "推荐原因"),
    });
  }
  return {
    overall: cleanup(overallMatch?.[1] || ""),
    papers,
  };
}

function pick(text, pattern) {
  return cleanup(text.match(pattern)?.[1] || "");
}

function section(text, title) {
  const pattern = new RegExp(`###\\s*${title}\\s*([\\s\\S]*?)(?=\\n###\\s+|$)`);
  return cleanup(text.match(pattern)?.[1] || "");
}

function boldSection(text, title) {
  const pattern = new RegExp(`\\*\\*${title}\\*\\*\\s*([\\s\\S]*?)(?=\\n\\*\\*[^*]+\\*\\*|\\n###\\s+|$)`);
  return cleanup(text.match(pattern)?.[1] || "");
}

function researchSummaryParts(text) {
  const summaryBlock = section(text, "摘要");
  return {
    question: boldSection(summaryBlock, "研究问题") || section(text, "研究问题"),
    method: boldSection(summaryBlock, "研究方法") || section(text, "研究方法"),
    findings: boldSection(summaryBlock, "研究结论") || section(text, "研究结论"),
  };
}

function researchSummary(text) {
  const summaryParts = researchSummaryParts(text);
  const parts = [
    ["研究问题", summaryParts.question],
    ["研究方法", summaryParts.method],
    ["研究结论", summaryParts.findings],
  ].filter(([, value]) => value);
  return parts.map(([title, value]) => `${title}：${value}`).join("\n\n");
}

function cleanup(text) {
  return text
    .replace(/```[\s\S]*?```/g, "")
    .replace(/\[[^\]]+\]\([^)]+\)/g, (value) => value.replace(/\(([^)]+)\)/, ""))
    .replace(/\s+\n/g, "\n")
    .trim();
}

function render() {
  const results = state.results || {};
  const metadataPapers = Array.isArray(results.papers) ? results.papers : [];
  state.mergedPapers = metadataPapers.map((paper, index) => mergePaper(paper, index));

  nodes.paperCount.textContent = String(metadataPapers.length || state.parsedReport.papers.length || 0);
  nodes.sortValue.textContent = results.sort_by ? `${results.sort_by}/${results.sort_order || "descending"}` : "未导入";
  nodes.queryValue.textContent = results.query || "等待导入";
  nodes.overallSummary.textContent =
    state.parsedReport.overall ||
    (metadataPapers.length ? "已导入 arXiv 元数据。继续导入 report.md 后，将显示整体摘要和单篇推荐原因。" : "请先导入完整流程生成的 results.json 和 report.md。");

  renderPapers(state.mergedPapers.length ? state.mergedPapers : state.parsedReport.papers);
  renderArchive(state.mergedPapers);
  applySearch(nodes.keywordInput.value.trim());
}

function mergePaper(paper, index) {
  const reportPaper = state.parsedReport.papers.find((item) => samePaper(item, paper, index));
  const authors = Array.isArray(paper.authors) ? paper.authors.join("；") : paper.authors || reportPaper?.authors || "";
  return {
    index: index + 1,
    title: paper.title || reportPaper?.title || `Paper ${index + 1}`,
    arxivId: paper.arxiv_id || reportPaper?.arxivId || "",
    authors,
    date: dateOnly(paper.published || paper.updated || reportPaper?.date || ""),
    abstractUrl: paper.abstract_url || "",
    pdfUrl: paper.pdf_url || "",
    categories: paper.categories || [],
    arxivSummary: paper.summary || "",
    summaryParts: reportPaper?.summaryParts || null,
    field: reportPaper?.field || "",
    summary: reportPaper?.summary || "尚未导入 report.md，暂无中文摘要。",
    reason: reportPaper?.reason || "尚未导入 report.md，暂无推荐原因。",
  };
}

function samePaper(reportPaper, paper, index) {
  if (reportPaper.arxivId && paper.arxiv_id) return reportPaper.arxivId === paper.arxiv_id;
  if (reportPaper.title && paper.title) return normalize(reportPaper.title) === normalize(paper.title);
  return reportPaper.index === index + 1;
}

function normalize(value) {
  return String(value).replace(/\s+/g, " ").trim().toLowerCase();
}

function dateOnly(value) {
  return String(value).slice(0, 10) || "未知";
}

function renderPapers(papers) {
  nodes.paperGrid.innerHTML = "";
  nodes.paperGrid.classList.toggle("empty", papers.length === 0);
  if (!papers.length) {
    nodes.paperGrid.textContent = "尚未导入论文数据。";
    return;
  }

  papers.forEach((paper, index) => {
    const fragment = nodes.paperTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".paper-card");
    card.dataset.search = [paper.title, paper.authors, paper.summary, paper.reason, paper.arxivSummary].join(" ").toLowerCase();
    fragment.querySelector(".paper-index").textContent = `Paper ${String(index + 1).padStart(2, "0")}`;
    fragment.querySelector("h3").textContent = paper.title;
    fragment.querySelector(".meta-list").innerHTML = metadataMarkup(paper);
    fragment.querySelector(".link-row").innerHTML = linksMarkup(paper);
    fragment.querySelector(".paper-summary").innerHTML = summaryMarkup(paper);
    fragment.querySelector(".paper-field").innerHTML = sectionMarkup("具体领域", paper.field || "暂无具体领域。");
    fragment.querySelector(".paper-reason").innerHTML = sectionMarkup("推荐原因", paper.reason || "暂无推荐原因。");
    fragment.querySelector(".radar-slot").innerHTML = radarSvg(scorePaper(paper));
    nodes.paperGrid.appendChild(fragment);
  });
}

function summaryMarkup(paper) {
  const parts = paper.summaryParts || {};
  if (parts.question || parts.method || parts.findings) {
    return [
      `<h4>摘要</h4>`,
      summaryItemMarkup("研究问题", parts.question),
      summaryItemMarkup("研究方法", parts.method),
      summaryItemMarkup("研究结论", parts.findings),
    ].join("");
  }
  return sectionMarkup("摘要", paper.summary || "暂无摘要。");
}

function summaryItemMarkup(title, value) {
  if (!value) return "";
  return `<div class="summary-item"><strong>${escapeHtml(title)}</strong><p>${formatMultiline(value)}</p></div>`;
}

function sectionMarkup(title, value) {
  return `<h4>${escapeHtml(title)}</h4><p>${formatMultiline(value)}</p>`;
}

function formatMultiline(value) {
  return escapeHtml(value)
    .split(/\n+/)
    .filter(Boolean)
    .map((line) => line.trim())
    .join("<br />");
}

function metadataMarkup(paper) {
  return [
    ["arXiv", paper.arxivId || "未知"],
    ["日期", paper.date || "未知"],
    ["作者", paper.authors || "未知"],
    ["分类", Array.isArray(paper.categories) ? paper.categories.join(" / ") : "未知"],
  ]
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`)
    .join("");
}

function linksMarkup(paper) {
  if (paper.pdfUrl) {
    return `<a href="${escapeAttribute(paper.pdfUrl)}" target="_blank" rel="noreferrer">PDF下载</a>`;
  }
  return "<span>暂无 PDF</span>";
}

function scorePaper(paper) {
  const query = normalize(state.results?.query || "");
  const text = normalize([paper.title, paper.arxivSummary, paper.summary].join(" "));
  const tokens = query.split(/\s+/).filter(Boolean);
  const matched = tokens.filter((token) => text.includes(token)).length;
  const relevance = tokens.length ? Math.round((matched / tokens.length) * 100) : 70;
  const summaryDepth = Math.min(100, Math.round(((paper.summary || "").length / 260) * 100));
  const metadata = [paper.title, paper.authors, paper.date, paper.abstractUrl, paper.pdfUrl].filter(Boolean).length * 20;
  const freshness = freshnessScore(paper.date);
  const readability = Math.min(100, Math.round(((paper.reason || "").length / 60) * 100));
  return [
    ["相关性", clamp(relevance)],
    ["摘要", clamp(summaryDepth)],
    ["元数据", clamp(metadata)],
    ["时效", clamp(freshness)],
    ["推荐", clamp(readability)],
  ];
}

function freshnessScore(dateText) {
  const time = Date.parse(dateText);
  if (Number.isNaN(time)) return 55;
  const days = (Date.now() - time) / 86400000;
  if (days <= 30) return 100;
  if (days <= 365) return 85;
  if (days <= 1095) return 70;
  return 55;
}

function clamp(value) {
  return Math.max(0, Math.min(100, value));
}

function radarSvg(scores) {
  const size = 132;
  const center = size / 2;
  const radius = 44;
  const points = scores.map(([, score], index) => point(center, radius * (score / 100), index, scores.length));
  const grid = [0.33, 0.66, 1]
    .map((scale) => polygon(scores.map((_, index) => point(center, radius * scale, index, scores.length)), "none", "rgba(245,240,230,.18)"))
    .join("");
  const axes = scores
    .map(([label], index) => {
      const end = point(center, radius, index, scores.length);
      const labelPoint = point(center, radius + 14, index, scores.length);
      return `<line x1="${center}" y1="${center}" x2="${end.x}" y2="${end.y}" stroke="rgba(245,240,230,.14)" /><text x="${labelPoint.x}" y="${labelPoint.y}" text-anchor="middle">${label}</text>`;
    })
    .join("");
  return `<svg class="radar" viewBox="0 0 ${size} ${size}" role="img" aria-label="论文雷达评分">${grid}${axes}${polygon(points, "rgba(214,170,88,.35)", "#d6aa58")}</svg>`;
}

function point(center, radius, index, total) {
  const angle = -Math.PI / 2 + (Math.PI * 2 * index) / total;
  return {
    x: Number((center + Math.cos(angle) * radius).toFixed(2)),
    y: Number((center + Math.sin(angle) * radius).toFixed(2)),
  };
}

function polygon(points, fill, stroke) {
  const value = points.map((item) => `${item.x},${item.y}`).join(" ");
  return `<polygon points="${value}" fill="${fill}" stroke="${stroke}" stroke-width="1.4" />`;
}

function renderArchive(papers) {
  if (!papers.length) {
    nodes.archiveBody.innerHTML = `<tr><td colspan="5">尚未导入论文数据。</td></tr>`;
    return;
  }
  nodes.archiveBody.innerHTML = papers
    .map((paper, index) => {
      const score = average(scorePaper(paper).map((item) => item[1]));
      return `<tr><td>${index + 1}</td><td>${escapeHtml(paper.title)}</td><td>${escapeHtml(paper.arxivId)}</td><td>${escapeHtml(paper.date)}</td><td>${score} / 100</td></tr>`;
    })
    .join("");
}

function average(values) {
  return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length);
}

function applySearch(keyword) {
  const normalized = keyword.toLowerCase();
  document.querySelectorAll(".paper-card").forEach((card) => {
    const matched = !normalized || card.dataset.search.includes(normalized);
    card.classList.toggle("hidden", !matched);
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}
