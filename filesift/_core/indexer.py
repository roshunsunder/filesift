"""Indexer orchestrator — runs fast tier then semantic tier."""

import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from pathlib import Path

from filesift._core.embeddings import create_embedding_model
from filesift._core.fast_indexer import FastIndexer
from filesift._core.fast_storage import FastIndexStore
from filesift._core.semantic_indexer import SemanticIndexer, SEMANTIC_CACHE_DIR


class Indexer:
    """Thin orchestrator that runs FastIndexer then SemanticIndexer."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def index(self, reindex: bool = False) -> None:
        index_dir = self.root / ".filesift"

        # --- Fast tier ---
        fast_indexer = FastIndexer(self.root)
        existing_fast = None
        if not reindex and FastIndexStore.exists(index_dir):
            existing_fast = FastIndexStore.load(index_dir)

        if existing_fast and not reindex:
            fast_index = fast_indexer.incremental_index(existing_fast)
        else:
            fast_index = fast_indexer.index()

        FastIndexStore.save(fast_index, index_dir)
        print(f"Fast index saved ({len(fast_index.files)} files)")

        # --- Semantic tier ---
        embedding_model = create_embedding_model()
        cache_dir = index_dir / SEMANTIC_CACHE_DIR

        semantic_indexer = SemanticIndexer(self.root, embedding_model, cache_dir)

        existing_entries = None
        if not reindex and SemanticIndexer.exists(index_dir):
            loaded = SemanticIndexer.load(index_dir)
            if loaded:
                _, existing_entries = loaded

        faiss_index, entries, stats = semantic_indexer.index(existing_entries)
        SemanticIndexer.save(faiss_index, entries, index_dir)
        print(f"Semantic index saved ({stats.total_files} files, {stats.new_files} embedded, {stats.cached_files} cached)")
