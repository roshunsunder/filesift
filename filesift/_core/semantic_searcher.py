"""Semantic searcher — load FAISS index, embed query, return ranked results."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import faiss
import numpy as np

from filesift._core.embeddings.base import EmbeddingModel
from filesift._core.semantic_indexer import SemanticEntry, SemanticIndexer

logger = logging.getLogger(__name__)


@dataclass
class SemanticSearchResult:
    file_path: str
    relative_path: str
    score: float  # 0-1 (cosine similarity via IP on normalized vectors)
    language: str
    line_count: int


class SemanticSearcher:
    """Search a FAISS IndexFlatIP built by SemanticIndexer."""

    def __init__(
        self,
        faiss_index: faiss.IndexFlatIP,
        entries: Dict[str, SemanticEntry],
        embedding_model: EmbeddingModel,
    ):
        self.faiss_index = faiss_index
        self._ordered_keys: List[str] = list(entries.keys())
        self._entries = entries
        self.embedding_model = embedding_model

    def search(self, query: str, max_results: int = 10) -> List[SemanticSearchResult]:
        if self.faiss_index.ntotal == 0:
            return []

        query_vec = self.embedding_model.embed_query(query).reshape(1, -1)
        k = min(self.faiss_index.ntotal, max_results * 3)
        scores, indices = self.faiss_index.search(query_vec, k)

        best: Dict[str, float] = {}
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._ordered_keys):
                continue
            rel = self._ordered_keys[idx]
            clamped = float(max(0.0, min(1.0, score)))
            if rel not in best or clamped > best[rel]:
                best[rel] = clamped

        ranked = sorted(best.items(), key=lambda x: x[1], reverse=True)[:max_results]

        results = []
        for rel, score in ranked:
            entry = self._entries[rel]
            results.append(
                SemanticSearchResult(
                    file_path=entry.relative_path,
                    relative_path=entry.relative_path,
                    score=score,
                    language=entry.language,
                    line_count=entry.line_count,
                )
            )
        return results

    @classmethod
    def from_disk(cls, directory: Path, embedding_model: EmbeddingModel) -> Optional["SemanticSearcher"]:
        loaded = SemanticIndexer.load(directory)
        if loaded is None:
            return None
        faiss_index, entries = loaded
        return cls(faiss_index, entries, embedding_model)
