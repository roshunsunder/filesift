<p align="center">
  <img src="assets/logo.png" alt="FileSift" width="200">
</p>

<h1 align="center">FileSift</h1>

<p align="center">
  <em>A local, open-source utility that helps AI coding agents intelligently search and understand codebases.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/filesift/"><img src="https://img.shields.io/pypi/v/filesift" alt="PyPI"></a>
  <a href="https://pypi.org/project/filesift/"><img src="https://img.shields.io/pypi/pyversions/filesift" alt="Python"></a>
</p>

---

FileSift lets your AI coding agent search across a codebase based on what code **does**, rather than what it looks like. Instead of sifting through entire files after a `grep`, your agent can jump straight to the most relevant code using natural language queries like *"authentication middleware"* or *"database connection pooling"*. Everything runs **locally on your machine** — your code never leaves your environment.

**Key benefits:**
- **Smarter search** — hybrid keyword + semantic search finds code by intent, not just string matching
- **Less context wasted** — agents get pointed to the right files immediately, saving token budget on exploration

## Installation

```bash
pip install filesift
```

## Usage

There are three ways to use FileSift, depending on your workflow:

### 1. CLI

The most straightforward approach. Good for testing queries, managing indexes, and configuring settings.

```bash
# Index a project
filesift index /path/to/your/project

# Search for files by what they do
filesift find "authentication and session handling"

# Search in a specific directory
filesift find "retry logic for API calls" --path /path/to/project
```

### 2. MCP Server
<!-- mcp-name: io.github.roshunsunder/filesift -->
Installing FileSift also provides a `filesift-mcp` command — a lightweight [MCP](https://modelcontextprotocol.io/) server that exposes indexing and search as tools over STDIO. This works with most popular coding agents including Claude Code, Cursor, Copilot, and more.

Add it to your agent's MCP configuration:

```json
{
  "mcpServers": {
    "filesift": {
      "command": "filesift-mcp"
    }
  }
}
```

The MCP server exposes four tools:
- `filesift_search` — search an indexed codebase by natural language query
- `filesift_find_related` — find files related to a given file via imports and semantic similarity
- `filesift_index` — index a directory to enable searching
- `filesift_status` — check indexing status of a directory

### 3. Skills

FileSift ships with a `search-codebase` skill that can be installed directly into your coding agent's skill directory. This lets the agent interact with the FileSift CLI through bash, without requiring MCP support.

```bash
# Install for Claude Code (default)
filesift skill install

# Install for other agents
filesift skill install --agent cursor
filesift skill install --agent copilot
filesift skill install --agent codex
```

Supported agents: `claude`, `codex`, `cursor`, `copilot`, `gemini`, `roo`, `windsurf`.

## How It Works

FileSift uses a daemonized embedding model to keep searches fast. At its core, it generates embeddings from code descriptions and performs searches against small vector stores called **indexes**.

1. **Indexing** — `filesift index` first builds a fast keyword/structural index (completes in seconds), then triggers background semantic indexing that generates embeddings for each file.

2. **Daemon** — A background daemon loads indexes into memory and automatically shuts down after a configurable period of inactivity. After the first cold-start search, subsequent searches are near-instant.

3. **Search** — Queries are matched using both keyword (BM25) and semantic (FAISS) search, then combined via [Reciprocal Rank Fusion](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) for the best of both approaches.

Indexes are stored in a `.filesift` directory within each indexed project.

## Configuration

FileSift uses a TOML configuration file, manageable via the CLI:

```bash
# View all settings
filesift config list --all

# Set a value
filesift config set search.MAX_RESULTS 20
filesift config set daemon.INACTIVITY_TIMEOUT 600

# Manage ignore patterns
filesift config add-ignore "node_modules" ".venv"
filesift config list-ignore
```

Configuration sections: `search`, `indexing`, `daemon`, `models`, `paths`.

## Contributing

Contributions are welcome! To get started:

```bash
git clone https://github.com/roshunsunder/filesift.git
cd filesift
pip install -e .
```

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes and open a pull request

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
