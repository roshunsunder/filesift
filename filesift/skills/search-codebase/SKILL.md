---
name: search-codebase
description: >-
  Searches and indexes codebases using natural language queries via hybrid
  keyword and semantic search. Use when the user wants to find files in a
  project, understand code structure, locate implementations, or discover
  related files. Triggers on queries like "find the authentication logic",
  "where is the database connection handled", or "search this codebase for
  error handling".
compatibility: Requires the filesift Python package (pip install filesift). Python 3.12+.
metadata:
  author: roshunsunder
  version: "1.0.1"
allowed-tools: Bash(filesift:*)
---

# Searching Codebases with FileSift

FileSift indexes codebases and enables natural language search via hybrid keyword (BM25) + semantic (FAISS embeddings) search, merged with Reciprocal Rank Fusion.

## Step 0 — Verify FileSift is installed

**Do this before anything else, every time this skill is invoked for the first time in a session.**

```bash
filesift --version
```

If the command is found, proceed to [Quick start](#quick-start).

If it isn't found, install it. FileSift requires **Python 3.12+** and is published on PyPI. The right install command depends on how the user manages Python packages. Use whatever context you have — lock files, config files, prior conversation — to pick the correct one. If you're unsure, ask before running anything.

| Environment | Install command |
|---|---|
| pip (default) | `pip install filesift` |
| uv (tool) | `uv tool install filesift` |
| uv (project) | `uv add filesift` |
| pipx | `pipx install filesift` |
| poetry | `poetry add filesift` |
| pdm | `pdm add filesift` |
| conda / mamba | `pip install filesift` (inside the active conda env) |

**Hints for inferring the right tool:**
- `uv.lock` or `[tool.uv]` in `pyproject.toml` → user likely uses `uv`
- `poetry.lock` or `[tool.poetry]` in `pyproject.toml` → use `poetry add`
- `pdm.lock` → use `pdm add`
- A plain `requirements.txt` with no other tooling → use `pip install`
- If the user is in an active virtualenv (check `$VIRTUAL_ENV`), use `pip install` inside it

After installing, confirm with `filesift --version` before proceeding.

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

**Formulating effective queries**

The semantic index embeds raw source code. The embedding model (jina-embeddings-v2-base-code) was trained on 150M+ natural language / code pairs, so it bridges intent-based queries directly to code. Despite this, query quality directly determines result quality — the model encodes each query into a single dense vector, so a vague or overloaded query produces a vague result.

**Core rule:** Translate the user's request into a short (3–7 word) description of what the target code *does*, as a developer would phrase it in a docstring. Do not paste the user's question verbatim.

Guidelines:
- **Strip question framing** — Remove "how does", "where is", "I need to understand", "code that handles". These words don't appear in code.
- **Lead with an action verb** — "parse", "validate", "authenticate", "retry", "transform" match function names and docstrings.
- **One concept per query** — For multi-part user requests, run separate focused queries rather than one long combined query. A single long query dilutes the embedding signal.
- **Use developer vocabulary** — Think: what would a developer name this function, or write in its docstring?

| User request | Bad query | Good queries |
|---|---|---|
| "How does the app handle user login and JWT tokens?" | `"how app handles user login and JWT token management"` | `"user authentication"` + `"JWT token validation"` |
| "I want to understand how database errors are caught and retried" | `"catching retrying database errors logic"` | `"database error handling"` |
| "Where is the config loaded from at startup?" | `"config loading parsing startup initialization"` | `"configuration loading"` |
| "How does payment processing work, including webhooks?" | `"payment processing webhooks implementation"` | `"payment processing"` + `"webhook handler"` |

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
