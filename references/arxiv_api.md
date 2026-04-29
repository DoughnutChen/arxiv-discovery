# arXiv API Reference

Use the official arXiv Atom API for search:

```text
GET https://export.arxiv.org/api/query
```

Common query parameters:
- `search_query`: query expression, such as `all:"retrieval augmented generation"` or `cat:cs.CL AND all:hallucination`.
- `start`: zero-based offset. The skill scripts use `0`.
- `max_results`: number of entries to return. Default in this skill is `5`.
- `sortBy`: `relevance`, `lastUpdatedDate`, or `submittedDate`.
- `sortOrder`: `ascending` or `descending`.

PDF links usually follow this pattern:

```text
https://arxiv.org/pdf/<arxiv_id>.pdf
```

Search examples:

```text
all:"retrieval augmented generation"
cat:cs.CL AND all:"hallucination detection"
cat:stat.ML AND all:causal
```

Operational notes:
- arXiv does not require an API key for this workflow.
- Keep request pacing conservative. The included scripts sleep between API/download operations.
- Do not add third-party scholarly APIs unless the user explicitly asks for that expansion.
- Prefer title, abstract, category, and extracted正文 when judging keyword relevance.
