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

1. **Index a directory**:
   ```bash
   filesift index /path/to/your/project
   ```

2. **Search for files**:
   ```bash
   filesift find "authentication logic"
   ```

3. **Search in a specific directory**:
   ```bash
   filesift find "data processing" --path /path/to/project
   ```

## Configuration

FileSift uses a TOML configuration file that is automatically created on first run. The configuration file is located at:

- **macOS/Linux**: `~/.config/filesift/config.toml`
- **Windows**: `%APPDATA%\filesift\config.toml`

### Setting Up Your Configuration

#### 1. LLM Provider Setup

FileSift works with any LLM inference provider that supports the OpenAI API format. Configure your provider in the config file:

**For OpenAI:**
```toml
[llm]
LLM_BASE_URL = ""  # Leave empty for OpenAI
LLM_API_KEY = "sk-your-openai-api-key"
```

**For LM Studio (local):**
```toml
[llm]
LLM_BASE_URL = "http://localhost:1234/v1"
LLM_API_KEY = "lm-studio"  # Can be any placeholder
```

**For Ollama:**
```toml
[llm]
LLM_BASE_URL = "http://localhost:11434/v1"
LLM_API_KEY = "ollama"  # Can be any placeholder
```

**For other providers:**
Set `LLM_BASE_URL` to your provider's API endpoint and `LLM_API_KEY` to your API key (if required).

#### 2. Model Configuration

You can customize which models are used for different tasks:

```toml
[models]
# Embedding model for semantic search (Hugging Face model)
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

# Image processing model (for vision-language tasks)
IMAGE_MODEL = "google/gemma-3-4b"

# Code processing model (for code understanding)
CODE_MODEL = "google/gemma-3-1b"
```

#### 3. Search Settings

```toml
[search]
# Maximum number of results to return
MAX_RESULTS = 10

# Similarity threshold (0.0 to 1.0) - only return results above this threshold
SIMILARITY_THRESHOLD = 0.7
```

#### 4. Indexing Settings

```toml
[indexing]
# Chunk size for splitting large files
CHUNK_SIZE = 1000

# Overlap between chunks (helps maintain context)
CHUNK_OVERLAP = 200

# Directories to exclude from indexing
EXCLUDED_DIRS = [
    ".git",
    "node_modules",
    "__pycache__",
    "venv",
    "env",
    ".env",
    "build",
    "dist",
    ".filesift"
]
```

#### 5. Daemon Settings

```toml
[daemon]
# Host and port for the daemon server
HOST = "127.0.0.1"
PORT = 8687

# Auto-shutdown after inactivity (in seconds)
# Set to 0 to disable auto-shutdown
INACTIVITY_TIMEOUT = 300  # 5 minutes
```

### Environment Variables

You can override configuration values using environment variables. The config system will check for environment variables with the same names (e.g., `LLM_API_KEY`, `LLM_BASE_URL`).

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

You can also use the CLI to manage all config related variables, if updating config files isn't your thing.

```bash
# Set a configuration value (TODO: implementation pending)
filesift config set KEY VALUE

# Show configuration file path
filesift config path
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
