"""Content-hash embedding cache using .npy files."""

import hashlib
from pathlib import Path
from typing import Optional

import numpy as np


def content_hash(content: str) -> str:
    """SHA-256 hash of file content."""
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


class SemanticCache:
    """On-disk cache mapping content hashes to pre-computed embedding vectors.

    Storage layout::

        cache_dir/
            {sha256}.npy   # each file is a 1-D float32 numpy array
    """

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, hash_key: str) -> Path:
        return self.cache_dir / f"{hash_key}.npy"

    def has(self, hash_key: str) -> bool:
        return self._path_for(hash_key).exists()

    def get(self, hash_key: str) -> Optional[np.ndarray]:
        path = self._path_for(hash_key)
        if not path.exists():
            return None
        return np.load(path).astype(np.float32)

    def put(self, hash_key: str, vector: np.ndarray) -> None:
        np.save(self._path_for(hash_key), vector.astype(np.float32))
