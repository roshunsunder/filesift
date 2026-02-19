"""Persistence for the fast index (JSON + BM25 pickle cache)."""

import json
import logging
import pickle
from pathlib import Path
from typing import Optional

from filesift._core.fast_index import FastIndex

logger = logging.getLogger(__name__)

FAST_INDEX_FILE = "fast_index.json"
FAST_BM25_FILE = "fast_bm25.pkl"


class FastIndexStore:
    @staticmethod
    def save(index: FastIndex, directory: Path) -> None:
        """Persist *index* to *directory* as JSON (source of truth) + BM25 pickle cache."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        # JSON — full index
        with open(directory / FAST_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index.to_dict(), f, indent=2)

        # BM25 pickle cache
        try:
            from rank_bm25 import BM25Okapi

            corpus = FastIndexStore._build_bm25_corpus(index)
            if corpus:
                bm25 = BM25Okapi(corpus)
                with open(directory / FAST_BM25_FILE, "wb") as f:
                    pickle.dump(bm25, f)
        except Exception as e:
            logger.warning("Could not build/save BM25 cache: %s", e)

    @staticmethod
    def load(directory: Path) -> Optional[FastIndex]:
        """Load a FastIndex from *directory*. Returns None if not found."""
        directory = Path(directory)
        json_path = directory / FAST_INDEX_FILE
        if not json_path.exists():
            return None

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return FastIndex.from_dict(data)
        except Exception as e:
            logger.error("Failed to load fast index from %s: %s", json_path, e)
            return None

    @staticmethod
    def load_bm25(directory: Path):
        """Load the cached BM25 index. Returns None if missing or corrupt."""
        pkl_path = Path(directory) / FAST_BM25_FILE
        if not pkl_path.exists():
            return None
        try:
            with open(pkl_path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            logger.warning("Could not load BM25 cache: %s", e)
            return None

    @staticmethod
    def exists(directory: Path) -> bool:
        return (Path(directory) / FAST_INDEX_FILE).exists()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _build_bm25_corpus(index: FastIndex):
        """Tokenize each file entry into a single BM25 document (list of tokens)."""
        corpus = []
        for _rel, entry in sorted(index.files.items()):
            tokens = list(entry.keywords)
            tokens.extend(fn.lower() for fn in entry.functions)
            tokens.extend(cls.lower() for cls in entry.classes)
            tokens.extend(imp.rsplit(".", 1)[-1].lower() for imp in entry.imports)
            for comment in entry.comments:
                tokens.extend(comment.lower().split())
            corpus.append(tokens)
        return corpus
