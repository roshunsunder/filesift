"""Fast searcher — BM25 + name matching + path matching over a FastIndex."""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
from rank_bm25 import BM25Okapi

from filesift._core.fast_index import FastIndex


@dataclass
class FastSearchResult:
    file_path: str
    score: float
    match_type: str  # "keyword" | "name" | "path" | "composite"
    matched_terms: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class FastSearcher:
    def __init__(self, index: FastIndex, bm25: Optional[BM25Okapi] = None):
        self.index = index
        # Matches the BM25 corpus built in FastIndexStore
        self._sorted_keys = sorted(index.files.keys())
        self._bm25 = bm25 if bm25 is not None else self._build_bm25()

    # ------------------------------------------------------------------
    # BM25
    # ------------------------------------------------------------------

    def _build_bm25(self) -> Optional[BM25Okapi]:
        corpus = []
        for key in self._sorted_keys:
            entry = self.index.files[key]
            tokens = list(entry.keywords)
            tokens.extend(fn.lower() for fn in entry.functions)
            tokens.extend(cls.lower() for cls in entry.classes)
            tokens.extend(imp.rsplit(".", 1)[-1].lower() for imp in entry.imports)
            for comment in entry.comments:
                tokens.extend(comment.lower().split())
            corpus.append(tokens)
        if not corpus:
            return None
        return BM25Okapi(corpus)

    def _bm25_search(self, query_tokens: List[str]) -> Dict[str, float]:
        """Return {relative_path: raw_bm25_score}."""
        if self._bm25 is None or not self._sorted_keys:
            return {}
        scores = self._bm25.get_scores(query_tokens)
        results: Dict[str, float] = {}
        for idx, score in enumerate(scores):
            if score > 0:
                results[self._sorted_keys[idx]] = float(score)
        return results

    # ------------------------------------------------------------------
    # Name matching
    # ------------------------------------------------------------------

    def _name_match(self, query: str) -> Dict[str, float]:
        """Case-insensitive substring match on function/class names."""
        q_lower = query.lower()
        q_tokens = q_lower.split()
        results: Dict[str, float] = {}

        for rel_path, entry in self.index.files.items():
            score = 0.0
            all_names = [n.lower() for n in entry.functions + entry.classes]
            for name in all_names:
                if name == q_lower:
                    score = max(score, 1.0)
                elif q_lower in name:
                    score = max(score, 0.7)
                elif name in q_lower:
                    score = max(score, 0.5)
                else:
                    for tok in q_tokens:
                        if tok in name:
                            score = max(score, 0.3)
            if score > 0:
                results[rel_path] = score
        return results

    # ------------------------------------------------------------------
    # Path matching
    # ------------------------------------------------------------------

    def _path_match(self, query: str) -> Dict[str, float]:
        """Substring match on file paths."""
        q_lower = query.lower()
        q_tokens = q_lower.split()
        results: Dict[str, float] = {}

        for rel_path in self.index.files:
            path_lower = rel_path.lower()
            score = 0.0
            if q_lower in path_lower:
                score = 1.0
            else:
                matched = sum(1 for tok in q_tokens if tok in path_lower)
                if matched:
                    score = matched / len(q_tokens) * 0.6
            if score > 0:
                results[rel_path] = score
        return results

    # ------------------------------------------------------------------
    # Combined search
    # ------------------------------------------------------------------

    def search(self, query: str, max_results: int = 10) -> List[FastSearchResult]:
        query_tokens = query.lower().split()

        bm25_scores = self._bm25_search(query_tokens)
        name_scores = self._name_match(query)
        path_scores = self._path_match(query)

        # Normalize BM25 scores to 0-1
        if bm25_scores:
            max_bm25 = max(bm25_scores.values())
            if max_bm25 > 0:
                bm25_scores = {k: v / max_bm25 for k, v in bm25_scores.items()}

        # Combine all candidate paths
        all_paths = set(bm25_scores) | set(name_scores) | set(path_scores)

        combined: Dict[str, float] = {}
        for path in all_paths:
            bm25_s = bm25_scores.get(path, 0.0)
            name_s = name_scores.get(path, 0.0)
            path_s = path_scores.get(path, 0.0)
            combined[path] = 0.5 * bm25_s + 0.3 * name_s + 0.2 * path_s

        # Sort by score descending
        ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:max_results]

        results: List[FastSearchResult] = []
        for rel_path, score in ranked:
            entry = self.index.files[rel_path]

            # Determine dominant match type
            bm25_s = bm25_scores.get(rel_path, 0.0)
            name_s = name_scores.get(rel_path, 0.0)
            path_s = path_scores.get(rel_path, 0.0)
            scores_by_type = {"keyword": bm25_s, "name": name_s, "path": path_s}
            dominant = max(scores_by_type, key=scores_by_type.get)
            if sum(1 for v in scores_by_type.values() if v > 0) > 1:
                match_type = "composite"
            else:
                match_type = dominant

            # Collect matched terms
            matched_terms: List[str] = []
            for tok in query_tokens:
                for name in entry.functions + entry.classes:
                    if tok in name.lower():
                        matched_terms.append(name)
                if tok in rel_path.lower():
                    matched_terms.append(rel_path)
            matched_terms = list(dict.fromkeys(matched_terms))[:10]

            results.append(FastSearchResult(
                file_path=rel_path,
                score=round(score, 4),
                match_type=match_type,
                matched_terms=matched_terms,
                metadata={
                    "language": entry.metadata.language,
                    "size": entry.metadata.size,
                    "line_count": entry.metadata.line_count,
                    "functions": len(entry.functions),
                    "classes": len(entry.classes),
                    "imports": len(entry.imports),
                },
            ))

        return results
