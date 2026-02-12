"""Unified query driver — merges fast tier + semantic tier via RRF."""

import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from filesift._config.config import config_dict

logger = logging.getLogger(__name__)


class SearchResult:
    """Represents a single search result."""

    def __init__(self, path: str, score: float, metadata: Dict[str, Any]):
        self.path = path
        self.score = score
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        return {"path": self.path, "score": self.score, "metadata": self.metadata}


class QueryDriver:
    """Load fast + semantic indexes and merge results via Reciprocal Rank Fusion."""

    def __init__(self):
        self._fast_searcher = None
        self._semantic_searcher = None

    def load_from_disk(self, path: str) -> None:
        path_obj = Path(path)

        # Fast tier
        try:
            from filesift._core.fast_storage import FastIndexStore
            from filesift._core.fast_searcher import FastSearcher

            if FastIndexStore.exists(path_obj):
                fast_index = FastIndexStore.load(path_obj)
                if fast_index:
                    bm25 = FastIndexStore.load_bm25(path_obj)
                    self._fast_searcher = FastSearcher(fast_index, bm25=bm25)
        except Exception as e:
            logger.warning("Could not load fast index: %s", e)

        # Semantic tier
        try:
            from filesift._core.embeddings import create_embedding_model
            from filesift._core.semantic_searcher import SemanticSearcher

            embedding_model = create_embedding_model()
            searcher = SemanticSearcher.from_disk(path_obj, embedding_model)
            if searcher:
                self._semantic_searcher = searcher
        except Exception as e:
            logger.warning("Could not load semantic index: %s", e)

        if not self._fast_searcher and not self._semantic_searcher:
            raise ValueError(f"No indexes found in {path}")

    def search(
        self, query: str, filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        max_results = config_dict["search"]["MAX_RESULTS"]
        threshold = config_dict["search"]["SIMILARITY_THRESHOLD"]

        fast_results = []
        semantic_results = []

        if self._fast_searcher:
            fast_results = self._fast_searcher.search(query, max_results=max_results * 2)

        if self._semantic_searcher:
            semantic_results = self._semantic_searcher.search(query, max_results=max_results * 2)

        # If both tiers are available, merge via RRF
        if fast_results and semantic_results:
            return self._merge_rrf(fast_results, semantic_results, max_results)

        # Single-tier fallback
        if semantic_results:
            results = []
            for r in semantic_results[:max_results]:
                if r.score >= threshold:
                    results.append(SearchResult(
                        path=r.file_path,
                        score=r.score,
                        metadata={"language": r.language, "line_count": r.line_count},
                    ))
            return results

        if fast_results:
            return [
                SearchResult(
                    path=r.file_path,
                    score=r.score,
                    metadata=r.metadata,
                )
                for r in fast_results[:max_results]
            ]

        return []

    @staticmethod
    def _merge_rrf(fast_results, semantic_results, max_results, alpha=0.5, k=60):
        """Reciprocal Rank Fusion across fast and semantic tiers."""
        rrf_scores: Dict[str, float] = {}
        metadata_map: Dict[str, Dict[str, Any]] = {}

        for rank, r in enumerate(fast_results):
            path = r.file_path
            rrf_scores[path] = rrf_scores.get(path, 0.0) + (1 - alpha) / (k + rank + 1)
            if path not in metadata_map:
                metadata_map[path] = r.metadata

        for rank, r in enumerate(semantic_results):
            path = r.file_path
            rrf_scores[path] = rrf_scores.get(path, 0.0) + alpha / (k + rank + 1)
            if path not in metadata_map:
                metadata_map[path] = {"language": r.language, "line_count": r.line_count}

        ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:max_results]

        return [
            SearchResult(path=path, score=score, metadata=metadata_map.get(path, {}))
            for path, score in ranked
        ]
