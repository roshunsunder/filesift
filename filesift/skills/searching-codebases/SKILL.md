---
name: searching-codebases
description: >-
  Searches and indexes codebases using natural language queries via hybrid
  keyword and semantic search. Use when the user wants to find files in a
  project, understand code structure, locate implementations, or discover
  related files. Triggers on queries like "find the authentication logic",
  "where is the database connection handled", or "search this codebase for
  error handling".
compatibility: Requires the filesift Python package (pip install filesift). Python 3.11+.
metadata:
  author: roshunsunder
  version: "0.2.0"
allowed-tools: Bash(filesift:*)
---

# Searching Codebases with FileSift

FileSift indexes codebases and enables natural language search via hybrid keyword (BM25) + semantic (FAISS embeddings) search, merged with Reciprocal Rank Fusion.

## Quick start

### 1. Check if an index exists

```bash
ls <project-root>/.filesift/
```

If `.filesift/` exists, skip to step 3.

### 2. Index the codebase

```bash
filesift index <project-root>
```

- Fast indexing (keyword/structural) completes in seconds
- Semantic indexing (embeddings) runs in the background and may take 1-3 minutes for large codebases
- You can search immediately with keyword-only results while semantic indexing completes

### 3. Search

```bash
filesift find "<natural language query>" --path <project-root>
```

Use conceptual descriptions, not code syntax:
- "user authentication and session management"
- "database connection pooling"
- "error handling and retry logic"
- "API rate limiting middleware"

Results are ranked by relevance score (0-1). Read the top results to understand the actual implementation.

### 4. Re-index after significant changes

```bash
filesift index <project-root> --reindex
```

Use `--reindex` to force a full rebuild. Without it, only changed files are re-indexed.

## Tips

- **Default path**: If the project root is the current working directory, `--path` can be omitted
- **More results**: Default is 5 results. Change with `filesift config set search.MAX_RESULTS 20`
- **Multiple projects**: Each project gets its own `.filesift/` directory; index each separately

## Advanced usage

See [references/ADVANCED.md](references/ADVANCED.md) for daemon management, configuration tuning, and troubleshooting.
