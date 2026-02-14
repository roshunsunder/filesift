"""Semantic indexer — embed file contents directly into FAISS (no LLM)."""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import faiss
import numpy as np
from tqdm import tqdm

from filesift._config.config import config_dict
from filesift._core.embeddings.base import EmbeddingModel
from filesift._core.extractors import SUPPORTED_EXTENSIONS, detect_language
from filesift._core.semantic_cache import SemanticCache, content_hash

logger = logging.getLogger(__name__)

SEMANTIC_INDEX_FILE = "semantic_index.faiss"
SEMANTIC_META_FILE = "semantic_index.json"
SEMANTIC_CACHE_DIR = "semantic_cache"


@dataclass
class SemanticEntry:
    file_path: str
    relative_path: str
    content_hash: str
    language: str
    line_count: int
    model_used: str
    indexed_at: str


@dataclass
class SemanticIndexStats:
    total_files: int = 0
    new_files: int = 0
    cached_files: int = 0
    skipped_files: int = 0


class SemanticIndexer:
    """Read files, embed content directly, and build a FAISS IndexFlatIP."""

    BATCH_SIZE = 32

    def __init__(self, root: Path, embedding_model: EmbeddingModel, cache_dir: Path):
        self.root = Path(root).resolve()
        self.embedding_model = embedding_model
        self.cache = SemanticCache(cache_dir)
        self.excluded_dirs: List[str] = config_dict["indexing"]["EXCLUDED_DIRS"]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _should_index(self, file_path: Path) -> bool:
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return False
        for excluded in self.excluded_dirs:
            if excluded in str(file_path):
                return False
        return True

    def _prepare_content(self, content: str, file_path: Path) -> str:
        """Prepare file content for embedding.

        For files within the token budget, use the full content.
        For large files, extract a representative sample:
        imports/signatures at the top, a middle sample, and the tail.
        """
        max_chars = self.embedding_model.max_tokens * 4  # rough char estimate
        if len(content) <= max_chars:
            return content

        lines = content.splitlines()
        budget = max_chars

        # Take first 30% (imports, class/fn signatures)
        head_end = max(1, int(len(lines) * 0.3))
        head = "\n".join(lines[:head_end])
        if len(head) > budget * 0.4:
            head = head[: int(budget * 0.4)]

        # Take a middle sample
        mid_start = len(lines) // 2 - len(lines) // 10
        mid_end = len(lines) // 2 + len(lines) // 10
        middle = "\n".join(lines[max(0, mid_start):mid_end])
        if len(middle) > budget * 0.3:
            middle = middle[: int(budget * 0.3)]

        # Take tail
        tail = "\n".join(lines[-max(1, int(len(lines) * 0.1)):])
        if len(tail) > budget * 0.2:
            tail = tail[: int(budget * 0.2)]

        return f"{head}\n\n...\n\n{middle}\n\n...\n\n{tail}"

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------

    def index(
        self,
        existing_entries: Optional[Dict[str, SemanticEntry]] = None,
        progress_callback: Optional[callable] = None,
    ) -> Tuple[faiss.IndexFlatIP, Dict[str, SemanticEntry], SemanticIndexStats]:
        """Scan files, embed, and build a FAISS index.

        Args:
            existing_entries: Previous entries keyed by relative_path.
                Files whose content hash matches are loaded from cache
                instead of re-embedded.
            progress_callback: Optional function (status_dict) -> None to report progress.

        Returns:
            (faiss_index, entries_dict, stats)
        """
        existing_entries = existing_entries or {}
        stats = SemanticIndexStats()

        # Discover files
        files_to_consider: List[Path] = []
        for fp in self.root.rglob("*"):
            if fp.is_dir():
                continue
            if self._should_index(fp):
                files_to_consider.append(fp)

        stats.total_files = len(files_to_consider)
        print(f"\nFound {stats.total_files} file(s) for semantic indexing")

        if not files_to_consider:
            idx = faiss.IndexFlatIP(self.embedding_model.dimension)
            return idx, {}, stats

        entries: Dict[str, SemanticEntry] = {}
        vectors: List[np.ndarray] = []  # ordered parallel to entries
        order: List[str] = []  # relative paths in insertion order

        # Separate cached vs. needs-embedding
        to_embed_paths: List[Path] = []
        to_embed_contents: List[str] = []

        pbar = tqdm(
            total=len(files_to_consider),
            desc="Scanning files",
            unit="file",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}",
            leave=False,
            disable=bool(progress_callback),
        )

        for fp in files_to_consider:
            try:
                raw = fp.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                logger.warning("Could not read %s: %s", fp, e)
                stats.skipped_files += 1
                pbar.update(1)
                continue

            try:
                rel = str(fp.relative_to(self.root))
            except ValueError:
                rel = str(fp)

            chash = content_hash(raw)
            language = detect_language(fp.suffix)
            line_count = raw.count("\n") + 1

            # Check if unchanged and cached
            old = existing_entries.get(rel)
            if old and old.content_hash == chash and self.cache.has(chash):
                vec = self.cache.get(chash)
                if vec is not None:
                    entries[rel] = SemanticEntry(
                        file_path=str(fp),
                        relative_path=rel,
                        content_hash=chash,
                        language=language,
                        line_count=line_count,
                        model_used=self.embedding_model.model_name,
                        indexed_at=old.indexed_at,
                    )
                    vectors.append(vec)
                    order.append(rel)
                    stats.cached_files += 1
                    pbar.update(1)
                    if progress_callback:
                        progress_callback({
                            "phase": "scanning",
                            "total": len(files_to_consider),
                            "current": pbar.n,
                            "percent": (pbar.n / len(files_to_consider)) * 100
                        })
                    continue

            # Queue for batch embedding
            content = self._prepare_content(raw, fp)
            to_embed_paths.append(fp)
            to_embed_contents.append(content)
            pbar.update(1)
            if progress_callback:
                progress_callback({
                    "phase": "scanning",
                    "total": len(files_to_consider),
                    "current": pbar.n,
                    "percent": (pbar.n / len(files_to_consider)) * 100
                })

        pbar.close()

        # Batch embed
        if to_embed_contents:
            print(f"Embedding {len(to_embed_contents)} file(s) ({stats.cached_files} cached)...")
            now = datetime.now().isoformat()

            embed_pbar = tqdm(
                total=len(to_embed_contents),
                desc="Generating embeddings",
                unit="chunk",
                bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
                leave=False,
                disable=bool(progress_callback),
            )

            if progress_callback:
                progress_callback({
                    "phase": "embedding",
                    "total": len(to_embed_contents),
                    "current": 0,
                    "percent": 0.0
                })

            for batch_start in range(0, len(to_embed_contents), self.BATCH_SIZE):
                batch_end = min(batch_start + self.BATCH_SIZE, len(to_embed_contents))
                batch_texts = to_embed_contents[batch_start:batch_end]
                batch_paths = to_embed_paths[batch_start:batch_end]

                batch_vecs = self.embedding_model.embed_batch(batch_texts)

                for i, fp in enumerate(batch_paths):
                    vec = batch_vecs[i]
                    try:
                        rel = str(fp.relative_to(self.root))
                    except ValueError:
                        rel = str(fp)

                    raw = fp.read_text(encoding="utf-8", errors="replace")
                    chash = content_hash(raw)
                    language = detect_language(fp.suffix)
                    line_count = raw.count("\n") + 1

                    self.cache.put(chash, vec)

                    entries[rel] = SemanticEntry(
                        file_path=str(fp),
                        relative_path=rel,
                        content_hash=chash,
                        language=language,
                        line_count=line_count,
                        model_used=self.embedding_model.model_name,
                        indexed_at=now,
                    )
                    vectors.append(vec)
                    order.append(rel)
                    stats.new_files += 1
                
                embed_pbar.update(len(batch_texts))
                if progress_callback:
                    progress_callback({
                        "phase": "embedding",
                        "total": len(to_embed_contents),
                        "current": embed_pbar.n,
                        "percent": (embed_pbar.n / len(to_embed_contents)) * 100
                    })
            
            embed_pbar.close()
        elif stats.cached_files:
            print(f"All {stats.cached_files} file(s) loaded from cache")

        # Build FAISS index
        dim = self.embedding_model.dimension
        faiss_index = faiss.IndexFlatIP(dim)
        if vectors:
            matrix = np.stack(vectors).astype(np.float32)
            faiss_index.add(matrix)

        # Reorder entries dict to match FAISS row order
        ordered_entries: Dict[str, SemanticEntry] = {}
        for rel in order:
            ordered_entries[rel] = entries[rel]

        return faiss_index, ordered_entries, stats

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @staticmethod
    def save(
        faiss_index: faiss.IndexFlatIP,
        entries: Dict[str, SemanticEntry],
        directory: Path,
    ) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        faiss.write_index(faiss_index, str(directory / SEMANTIC_INDEX_FILE))

        meta = {
            "entries": [asdict(e) for e in entries.values()],
            "order": list(entries.keys()),
        }
        with open(directory / SEMANTIC_META_FILE, "w") as f:
            json.dump(meta, f, indent=2)

    @staticmethod
    def load(directory: Path) -> Optional[Tuple[faiss.IndexFlatIP, Dict[str, SemanticEntry]]]:
        directory = Path(directory)
        index_path = directory / SEMANTIC_INDEX_FILE
        meta_path = directory / SEMANTIC_META_FILE

        if not index_path.exists() or not meta_path.exists():
            return None

        faiss_index = faiss.read_index(str(index_path))

        with open(meta_path) as f:
            meta = json.load(f)

        entries: Dict[str, SemanticEntry] = {}
        for entry_data in meta["entries"]:
            e = SemanticEntry(**entry_data)
            entries[e.relative_path] = e

        return faiss_index, entries

    @staticmethod
    def exists(directory: Path) -> bool:
        directory = Path(directory)
        return (directory / SEMANTIC_INDEX_FILE).exists() and (
            directory / SEMANTIC_META_FILE
        ).exists()

    def is_index_stale(self, directory: Path) -> bool:
        """Check if the index is stale by comparing file mtimes with index build time."""
        directory = Path(directory)
        if not self.exists(directory):
            return True

        # Load metadata to find build time
        meta_path = directory / SEMANTIC_META_FILE
        try:
            with open(meta_path) as f:
                meta = json.load(f)
            # Find the latest 'indexed_at' timestamp
            if not meta.get("entries"):
                return True # Empty index is effectively stale if files exist
            
            # This is a heuristic: check if any file in root is newer than the index file
            # or newer than the latest entry.
            # Using index file mtime is a good proxy for "last build time".
            index_mtime = meta_path.stat().st_mtime
            
            # Check a sample of files or all files for freshness
            # For speed, we can check recent mtimes in a quick scan
            for fp in self.root.rglob("*"):
                if fp.is_file() and self._should_index(fp):
                    if fp.stat().st_mtime > index_mtime:
                        return True
            return False
            
        except Exception as e:
            logger.warning(f"Failed to check staleness: {e}")
            return True
