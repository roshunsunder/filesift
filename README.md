# FileSift

**Intelligent file indexing and search system powered by language models**

FileSift enables you to search your filesystem using natural language queries. It intelligently indexes code, documents, images, and data files, making it easy to find what you're looking for using semantic understanding rather than just filename matching.

## Features

- 🔍 **Natural Language Search**: Find files using conversational queries like "Python files about data processing" or "images of charts"
- 🧠 **Semantic Understanding**: Uses embedding models and LLMs to understand file content, not just filenames
- 🚀 **Hybrid Search**: Combines semantic search (FAISS) with keyword search (BM25) for best results
- ⚡ **Incremental Indexing**: Only reindexes changed files, making updates fast
- 🎯 **Smart File Processing**: Specialized processors for:
  - Code files (Python, JavaScript, TypeScript, etc.)
  - Documents (PDF, Markdown, etc.)
  - Images (with automatic captioning)
  - Data files (CSV, JSON, etc.)
  - Configuration files
  - Plain text files
- 🔄 **Daemon Mode**: Background daemon for instant search results without reloading indexes
- 🔌 **OpenAI-Compatible API**: Works with any LLM inference provider that supports the OpenAI API format (OpenAI, LM Studio, Ollama, etc.)

## Installation

### From Source

```bash
git clone https://github.com/yourusername/filesift.git
cd filesift
pip install -e .
```

### From PyPI

```bash
pip install filesift
```

## Quick Start

### Initial Setup

Before you can start indexing, you need to configure your LLM provider settings. FileSift works with any OpenAI-compatible API, including OpenAI, LM Studio, Ollama, and others.

1. **Configure your LLM provider**:

   **For OpenAI** (cloud):
   ```bash
   filesift config set llm.LLM_API_KEY "sk-your-openai-api-key"
   filesift config set models.MAIN_MODEL "gpt-4o-mini"
   ```

   **For LM Studio / Ollama / etc.** (local):
   ```bash
   filesift config set llm.LLM_BASE_URL "http://localhost:{SERVER_PORT}/v1"
   filesift config set llm.LLM_API_KEY "your-api-key"
   filesift config set models.MAIN_MODEL "your-model-name"
   ```

   > **Note**: Leave `LLM_BASE_URL` empty (`""`) to use OpenAI's cloud API. For local providers, set the base URL to your local server's endpoint.

2. **Index a directory**:
   ```bash
   filesift index /path/to/your/project
   ```

3. **Search for files**:
   ```bash
   filesift find "authentication logic"
   ```

4. **Search in a specific directory**:
   ```bash
   filesift find "data processing" --path /path/to/project
   ```

## Configuration

FileSift uses a TOML configuration file that is automatically created on first run. The configuration file is located at:

- **macOS**: `~/Library/Application Support/filesift/config.toml`
- **Linux**: `~/.config/filesift/config.toml`
- **Windows**: `%APPDATA%\filesift\config.toml`

### Managing Configuration

**We recommend using the CLI commands to manage your configuration** rather than editing the config file directly. The CLI provides type validation and ensures your settings are properly formatted.

#### Viewing Configuration

```bash
# List all available configuration sections
filesift config list

# View all configuration with values
filesift config list --all

# View a specific section (e.g., llm, search, daemon)
filesift config list llm
filesift config list search
filesift config list daemon
```

#### Setting Configuration Values

Use the `config set` command with the format `section.KEY`:

```bash
# LLM Provider Setup
# For OpenAI (leave base URL empty)
filesift config set llm.LLM_BASE_URL ""
filesift config set llm.LLM_API_KEY "sk-your-openai-api-key"

# For LM Studio (local)
filesift config set llm.LLM_BASE_URL "http://localhost:1234/v1"
filesift config set llm.LLM_API_KEY "lm-studio"

# For Ollama
filesift config set llm.LLM_BASE_URL "http://localhost:11434/v1"
filesift config set llm.LLM_API_KEY "ollama"

# Model Configuration
filesift config set models.EMBEDDING_MODEL "BAAI/bge-small-en-v1.5"
filesift config set models.IMAGE_MODEL "google/gemma-3-4b"
filesift config set models.MAIN_MODEL "google/gemma-3-1b"

# Search Settings
filesift config set search.MAX_RESULTS 10
filesift config set search.SIMILARITY_THRESHOLD 0.7

# Indexing Settings
filesift config set indexing.CHUNK_SIZE 1000
filesift config set indexing.CHUNK_OVERLAP 200

# Daemon Settings
filesift config set daemon.HOST "127.0.0.1"
filesift config set daemon.PORT 8687
filesift config set daemon.INACTIVITY_TIMEOUT 300

# Boolean values
filesift config set daemon.ENABLE_FEATURE true

# Array values (comma-separated or space-separated)
filesift config set indexing.EXCLUDED_DIRS ".git,node_modules,__pycache__"
```

The CLI automatically handles type conversion (strings, integers, floats, booleans, arrays) and validates that the configuration keys exist.

#### Configuration Sections

Available configuration sections:
- `llm` - LLM provider settings (base URL, API key)
- `models` - Model selection (embedding, image, code models)
- `search` - Search behavior (max results, similarity threshold)
- `indexing` - Indexing settings (chunk size, overlap, excluded directories)
- `daemon` - Daemon server settings (host, port, inactivity timeout)
- `api_keys` - API keys for external services
- `paths` - Path-related settings

### Environment Variables

You can override configuration values using environment variables. The config system will check for environment variables with the same names (e.g., `LLM_API_KEY`, `LLM_BASE_URL`).

### Manual Configuration Editing

While the CLI is recommended, you can also edit the configuration file directly if needed. The file uses TOML format and will be automatically created with default values on first run.

## CLI Commands

### Indexing

```bash
# Index a directory
filesift index /path/to/directory

# Force a complete reindex (overwrites existing index)
filesift index /path/to/directory --reindex
```

### Searching

```bash
# Search in the current directory's index
filesift find "your search query"

# Search in a specific directory
filesift find "your search query" --path /path/to/directory
```

### Daemon Management

The daemon runs in the background and keeps indexes loaded in memory for faster searches.

```bash
# Start the daemon
filesift daemon start

# Stop the daemon
filesift daemon stop

# Check daemon status
filesift daemon status

# List all running daemon processes
filesift daemon list

# Kill daemon process(es)
filesift daemon kill              # Kill registered daemon
filesift daemon kill --pid 12345  # Kill specific PID
filesift daemon kill --all        # Kill all daemon processes
```

The daemon automatically starts when you run `filesift find` or `filesift index`, and it will auto-shutdown after a period of inactivity (configurable).

### Configuration Management

The CLI provides comprehensive configuration management:

```bash
# List all configuration sections
filesift config list

# List all configuration with values
filesift config list --all

# List a specific section
filesift config list llm

# Set a configuration value (format: section.KEY)
filesift config set llm.LLM_API_KEY "sk-your-key"
filesift config set search.MAX_RESULTS 20
filesift config set daemon.INACTIVITY_TIMEOUT 600

# Show configuration file path
filesift config path

# Manage ignore patterns (indexing.EXCLUDED_DIRS)
filesift config list-ignore
filesift config add-ignore ".idea" ".tox"
filesift config add-ignore --file ./ignore.txt
filesift config remove-ignore ".idea"
```

## How It Works

1. **Indexing**: FileSift scans your directory and processes files using specialized processors:
   - Code files are analyzed for structure and functionality
   - Images are automatically captioned using vision-language models
   - Documents are parsed and chunked for semantic search
   - Data files are analyzed for structure and content

2. **Storage**: Indexes are stored in a `.filesift` directory within each indexed folder, containing:
   - FAISS vector store for semantic search
   - BM25 index for keyword search
   - Metadata about indexed files

3. **Search**: When you search:
   - Your query is processed using the same embedding model
   - Both semantic (vector) and keyword (BM25) searches are performed
   - Results are combined using Reciprocal Rank Fusion (RRF)
   - Results are filtered and ranked by relevance

4. **Daemon**: The daemon keeps indexes loaded in memory, eliminating the need to reload them for each search, making subsequent searches much faster.

## Project Structure

```
filesift/
├── filesift/
│   ├── _config/          # Configuration management
│   ├── _core/            # Core indexing and search logic
│   │   ├── indexer.py    # File system indexing
│   │   ├── query.py      # Search functionality
│   │   ├── daemon.py     # Daemon server
│   │   └── file_processors/  # File type handlers
│   ├── cli/              # Command-line interface
│   └── api/              # API endpoints (future)
├── tests/                # Test cases
└── pyproject.toml        # Package configuration
```

## Requirements

- Python 3.11+
- See `requirements.txt` for dependencies

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
