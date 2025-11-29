# LLM Filesystem

Search your file system with natural language queries, powered by advanced language models.

## Features

- **Natural Language Search**: Find files using natural language queries
- **Smart Code Understanding**: Uses GPT-3.5 to understand and index code files
- **Image Search**: Automatically generates captions for images using VIT-GPT2
- **Incremental Indexing**: Only reindexes changed files
- **Search Filters**: Filter by file type, date, size
- **Result Caching**: Caches search results for better performance
- **Modern API**: RESTful API with proper error handling and documentation

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/llm-filesystem.git
cd llm-filesystem
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Create a `.env` file with your API keys:
```env
OPENAI_API_KEY=your_openai_key_here
HF_BEARER_TOKEN=your_huggingface_token_here
ROOT_PATH=/path/to/index
API_HOST=127.0.0.1
API_PORT=8686
DEBUG_MODE=False
```

4. Run the server:
```bash
python -m filesift.api.server
```

## API Endpoints

### Search Files
```http
POST /search
Content-Type: application/json

{
    "query": "python files about data processing",
    "filters": {
        "file_type": "code",
        "min_date": "2023-01-01",
        "max_size": 1000000
    }
}
```

### Force Reindex
```http
POST /reindex
```

### Get Statistics
```http
GET /stats
```

### Health Check
```http
GET /health
```

## Project Structure

```
llm-filesystem/
├── src/
│   ├── core/
│   │   ├── indexer.py          # File system indexing
│   │   ├── query.py           # Search functionality
│   │   └── file_processors/   # File type handlers
│   ├── api/
│   │   └── server.py         # API endpoints
│   ├── config/
│   │   └── settings.py       # Configuration
│   └── utils/
├── frontend/                 # Frontend code (if any)
├── tests/                   # Test cases
└── docs/                   # Documentation
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
