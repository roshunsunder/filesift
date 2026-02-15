"""FileSift MCP server — exposes indexing and search as MCP tools over STDIO."""

import asyncio
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State management — caches QueryDrivers and tracks background indexing
# ---------------------------------------------------------------------------


class _State:
    """Caches QueryDriver instances and manages background semantic indexing."""

    def __init__(self):
        self._drivers: Dict[str, Any] = {}  # path -> QueryDriver
        self._fast_indexes: Dict[str, Any] = {}  # path -> FastIndex
        self._indexing_threads: Dict[str, threading.Thread] = {}
        self._indexing_status: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _normalize(path: str) -> str:
        p = Path(path).resolve()
        if p.name == ".filesift":
            p = p.parent
        return str(p)

    def get_driver(self, path: str):
        """Get or load a QueryDriver for *path*."""
        from filesift._core.query import QueryDriver

        key = self._normalize(path)
        with self._lock:
            if key in self._drivers:
                return self._drivers[key]

        driver = QueryDriver()
        driver.load_from_disk(key)
        with self._lock:
            self._drivers[key] = driver
        return driver

    def get_fast_index(self, path: str):
        """Get or load the FastIndex for *path*."""
        from filesift._core.fast_storage import FastIndexStore

        key = self._normalize(path)
        with self._lock:
            if key in self._fast_indexes:
                return self._fast_indexes[key]

        index_dir = Path(key) / ".filesift"
        fast_index = FastIndexStore.load(index_dir)
        if fast_index:
            with self._lock:
                self._fast_indexes[key] = fast_index
        return fast_index

    def invalidate(self, path: str):
        key = self._normalize(path)
        with self._lock:
            self._drivers.pop(key, None)
            self._fast_indexes.pop(key, None)

    def trigger_semantic_index(self, path: str, reindex: bool = False):
        """Start background semantic indexing (same pattern as daemon.py)."""
        from filesift._core.embeddings import create_embedding_model
        from filesift._core.semantic_indexer import SemanticIndexer, SEMANTIC_CACHE_DIR

        key = self._normalize(path)
        with self._lock:
            if key in self._indexing_threads:
                return  # already running
            self._indexing_status[key] = {"phase": "starting", "percent": 0}

        def _bg_index():
            try:
                root = Path(key)
                index_dir = root / ".filesift"

                with self._lock:
                    self._indexing_status[key] = {"phase": "loading_model", "percent": 0}

                embedding_model = create_embedding_model()
                cache_dir = index_dir / SEMANTIC_CACHE_DIR

                indexer = SemanticIndexer(root, embedding_model, cache_dir)

                existing_entries = None
                if not reindex and SemanticIndexer.exists(index_dir):
                    loaded = SemanticIndexer.load(index_dir)
                    if loaded:
                        _, existing_entries = loaded

                def progress_cb(status):
                    with self._lock:
                        self._indexing_status[key] = status

                faiss_index, entries, stats = indexer.index(
                    existing_entries, progress_callback=progress_cb
                )

                with self._lock:
                    self._indexing_status[key] = {"phase": "saving", "percent": 100}

                SemanticIndexer.save(faiss_index, entries, index_dir)
                self.invalidate(key)

                with self._lock:
                    self._indexing_status[key] = {"phase": "complete", "percent": 100}

            except Exception as e:
                logger.error("Background indexing failed for %s: %s", key, e)
                with self._lock:
                    self._indexing_status[key] = {"phase": "error", "error": str(e)}
            finally:
                with self._lock:
                    self._indexing_threads.pop(key, None)

        thread = threading.Thread(target=_bg_index, daemon=True)
        with self._lock:
            self._indexing_threads[key] = thread
        thread.start()

    def get_indexing_status(self, path: str) -> Optional[Dict[str, Any]]:
        key = self._normalize(path)
        with self._lock:
            return self._indexing_status.get(key)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    Tool(
        name="filesift_search",
        description=(
            "Search an indexed codebase by natural language query. "
            "Combines keyword/structural search (BM25, function/class names) "
            "with semantic embedding search (FAISS), merged via Reciprocal Rank Fusion. "
            "Returns ranked file paths with similarity scores. "
            "Use conceptual descriptions like 'authentication middleware' or "
            "'database connection pooling', not code syntax. "
            "Read the top results to understand the actual implementation."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural language search query. Good: 'user authentication and session management', "
                        "'error handling and retry logic'. Bad: specific function names (use find_related for that)."
                    ),
                },
                "path": {
                    "type": "string",
                    "description": "Absolute path to the project root (must contain .filesift/). Defaults to working directory.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return (default: 10).",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="filesift_find_related",
        description=(
            "Find files related to a given file via import/dependency relationships "
            "and semantic similarity. Useful for understanding how a file connects "
            "to the rest of the codebase."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative path to the file within the project (e.g., 'src/auth/middleware.py').",
                },
                "path": {
                    "type": "string",
                    "description": "Absolute path to the project root. Defaults to working directory.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum related files to return (default: 10).",
                    "default": 10,
                },
            },
            "required": ["file_path"],
        },
    ),
    Tool(
        name="filesift_status",
        description=(
            "Check the indexing status of a directory. Reports which index tiers "
            "are available (fast keyword, semantic embedding), file counts, and "
            "whether background indexing is in progress. Use before searching to "
            "verify an index exists."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the project root directory to check.",
                },
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="filesift_index",
        description=(
            "Index a directory to enable searching. Fast indexing (keyword/structural) "
            "runs immediately and completes in seconds. Semantic indexing (embeddings) "
            "runs in the background and may take 1-3 minutes for large codebases. "
            "You can search with fast-only results immediately while semantic indexing completes."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the directory to index.",
                },
                "reindex": {
                    "type": "boolean",
                    "description": "Force full re-indexing even if an index exists (default: false).",
                    "default": False,
                },
            },
            "required": ["path"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def _resolve_path(args: Dict[str, Any]) -> str:
    raw = args.get("path") or os.getcwd()
    return str(Path(raw).resolve())


def _handle_search(state: _State, args: Dict[str, Any]) -> Dict[str, Any]:
    query = args["query"]
    path = _resolve_path(args)
    max_results = args.get("max_results", 10)

    index_dir = Path(path) / ".filesift"
    if not index_dir.exists():
        return {
            "error": f"No index found at {path}. Use filesift_index to index this directory first."
        }

    try:
        driver = state.get_driver(path)
    except Exception as e:
        return {"error": f"Failed to load index: {e}"}

    from filesift._config.config import config_dict

    old_max = config_dict["search"]["MAX_RESULTS"]
    config_dict["search"]["MAX_RESULTS"] = max_results
    try:
        results = driver.search(query)
    finally:
        config_dict["search"]["MAX_RESULTS"] = old_max

    # Enrich with fast index metadata if available
    fast_index = state.get_fast_index(path)
    enriched = []
    for r in results:
        entry: Dict[str, Any] = {
            "file_path": r.path,
            "score": round(r.score, 4),
        }
        entry.update(r.metadata)
        if fast_index and r.path in fast_index.files:
            fi = fast_index.files[r.path]
            entry.setdefault("language", fi.metadata.language)
            entry.setdefault("line_count", fi.metadata.line_count)
            entry["functions"] = len(fi.functions)
            entry["classes"] = len(fi.classes)
        enriched.append(entry)

    response: Dict[str, Any] = {
        "query": query,
        "result_count": len(enriched),
        "results": enriched,
    }

    # Note if semantic index is still building
    idx_status = state.get_indexing_status(path)
    if idx_status and idx_status.get("phase") not in ("complete", "error", None):
        response["note"] = (
            "Semantic index is still building. "
            "Current results may be keyword-only. Re-search after indexing completes for better results."
        )

    return response


def _handle_find_related(state: _State, args: Dict[str, Any]) -> Dict[str, Any]:
    file_path = args["file_path"]
    path = _resolve_path(args)
    max_results = args.get("max_results", 10)

    index_dir = Path(path) / ".filesift"
    if not index_dir.exists():
        return {"error": f"No index found at {path}. Use filesift_index first."}

    related: List[Dict[str, Any]] = []
    seen: set = set()

    # 1. Dependency graph from fast index
    fast_index = state.get_fast_index(path)
    if fast_index:
        # Normalize the file_path to match index keys
        target = file_path
        if target not in fast_index.files:
            # Try matching by suffix
            for key in fast_index.files:
                if key.endswith(file_path) or file_path.endswith(key):
                    target = key
                    break
            else:
                # File not in index
                return {
                    "error": f"File '{file_path}' not found in fast index.",
                    "hint": "Use a path relative to the project root.",
                }

        dep = fast_index.dependency_graph
        if dep:
            # Files this file imports
            for imp in dep.imports.get(target, []):
                if imp not in seen and imp != target:
                    related.append({"file_path": imp, "relationship": "imports", "score": 1.0})
                    seen.add(imp)
            # Files that import this file
            for dep_file in dep.dependents.get(target, []):
                if dep_file not in seen and dep_file != target:
                    related.append({"file_path": dep_file, "relationship": "imported_by", "score": 1.0})
                    seen.add(dep_file)

    # 2. Semantic similarity
    try:
        from filesift._core.embeddings import create_embedding_model
        from filesift._core.semantic_searcher import SemanticSearcher

        embedding_model = create_embedding_model()
        searcher = SemanticSearcher.from_disk(index_dir, embedding_model)
        if searcher:
            # Read the file and embed it as a query
            full_file = Path(path) / file_path
            if full_file.exists():
                content = full_file.read_text(encoding="utf-8", errors="replace")
                # Truncate for embedding
                if len(content) > 8000:
                    content = content[:4000] + "\n...\n" + content[-2000:]
                sem_results = searcher.search(content, max_results=max_results + 5)
                for sr in sem_results:
                    if sr.file_path not in seen and sr.file_path != file_path:
                        related.append({
                            "file_path": sr.file_path,
                            "relationship": "semantically_similar",
                            "score": round(sr.score, 4),
                        })
                        seen.add(sr.file_path)
    except Exception as e:
        logger.warning("Semantic similarity lookup failed: %s", e)

    # Sort: dependency links first (score=1.0), then by semantic score
    related.sort(key=lambda x: x["score"], reverse=True)
    related = related[:max_results]

    return {"file_path": file_path, "related_count": len(related), "related_files": related}


def _handle_status(state: _State, args: Dict[str, Any]) -> Dict[str, Any]:
    path = _resolve_path(args)
    index_dir = Path(path) / ".filesift"

    result: Dict[str, Any] = {"path": path, "indexed": False}

    if not index_dir.exists():
        result["message"] = "No .filesift directory found. Use filesift_index to index this directory."
        return result

    # Fast index
    from filesift._core.fast_storage import FastIndexStore

    if FastIndexStore.exists(index_dir):
        fast_index = state.get_fast_index(path)
        if fast_index:
            result["indexed"] = True
            result["fast_index"] = {
                "available": True,
                "file_count": len(fast_index.files),
                "updated_at": fast_index.updated_at,
            }
    else:
        result["fast_index"] = {"available": False}

    # Semantic index
    from filesift._core.semantic_indexer import SemanticIndexer

    if SemanticIndexer.exists(index_dir):
        loaded = SemanticIndexer.load(index_dir)
        if loaded:
            _, entries = loaded
            result["indexed"] = True
            result["semantic_index"] = {
                "available": True,
                "file_count": len(entries),
            }
            if entries:
                first = next(iter(entries.values()))
                result["semantic_index"]["model"] = first.model_used
    else:
        result["semantic_index"] = {"available": False}

    # Background indexing status
    idx_status = state.get_indexing_status(path)
    if idx_status:
        result["background_indexing"] = idx_status

    return result


def _handle_index(state: _State, args: Dict[str, Any]) -> Dict[str, Any]:
    path = _resolve_path(args)
    reindex = args.get("reindex", False)

    root = Path(path)
    if not root.is_dir():
        return {"error": f"Directory not found: {path}"}

    # Fast index (synchronous — completes in seconds)
    from filesift._core.indexer import Indexer

    try:
        indexer = Indexer(root)
        indexer.index(reindex=reindex, semantic=False)
    except Exception as e:
        return {"error": f"Fast indexing failed: {e}"}

    fast_index = state.get_fast_index(path)
    fast_count = len(fast_index.files) if fast_index else 0

    # Invalidate cached driver so next search picks up new fast index
    state.invalidate(path)

    result: Dict[str, Any] = {
        "path": path,
        "fast_index": {"status": "complete", "file_count": fast_count},
    }

    # Semantic index (background)
    state.trigger_semantic_index(path, reindex=reindex)
    result["semantic_index"] = {
        "status": "indexing_in_background",
        "message": "Semantic indexing started. Use filesift_status to check progress. You can search now with fast-only results.",
    }

    return result


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

_HANDLERS = {
    "filesift_search": _handle_search,
    "filesift_find_related": _handle_find_related,
    "filesift_status": _handle_status,
    "filesift_index": _handle_index,
}


def create_server() -> Server:
    server = Server("filesift")
    state = _State()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        handler = _HANDLERS.get(name)
        if not handler:
            result = {"error": f"Unknown tool: {name}"}
        else:
            try:
                result = await asyncio.to_thread(handler, state, arguments)
            except Exception as e:
                logger.exception("Tool %s failed", name)
                result = {"error": str(e)}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    return server


async def _amain():
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_options)


def main():
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
