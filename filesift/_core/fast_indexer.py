"""Fast indexer — structural/keyword indexing without LLM calls."""

import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from tqdm import tqdm

from filesift._config.config import config_dict
from filesift._core.extractors import (
    SUPPORTED_EXTENSIONS,
    ExtractionResult,
    detect_language,
    extract,
)
from filesift._core.fast_index import (
    DependencyGraph,
    FastIndex,
    FastIndexEntry,
    FileMetadata,
)

logger = logging.getLogger(__name__)


class FastIndexer:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.excluded_dirs: List[str] = config_dict["indexing"]["EXCLUDED_DIRS"]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _should_index(self, file_path: Path) -> bool:
        """Return True if the file extension is supported and it isn't in an excluded dir."""
        # Always exclude .filesift directories (including nested ones)
        if ".filesift" in str(file_path):
            return False
            
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return False
        for excluded in self.excluded_dirs:
            if excluded in str(file_path):
                return False
        return True

    @staticmethod
    def _compute_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()

    @staticmethod
    def _build_keywords(relative_path: str, result: ExtractionResult) -> List[str]:
        """Combine path components + structural names into a keyword list."""
        kw: Set[str] = set()

        # Path components (split on separators)
        for part in re.split(r"[/\\_.\-]+", relative_path):
            part = part.lower().strip()
            if len(part) > 1:
                kw.add(part)

        for name in result.functions:
            # Split camelCase / snake_case
            for token in re.split(r"[_]+", name):
                parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)", token)
                for p in parts:
                    if len(p) > 1:
                        kw.add(p.lower())
            kw.add(name.lower())

        for name in result.classes:
            for token in re.split(r"[_]+", name):
                parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)", token)
                for p in parts:
                    if len(p) > 1:
                        kw.add(p.lower())
            kw.add(name.lower())

        for imp in result.imports:
            # Take the last component of dotted imports
            last = imp.rsplit(".", 1)[-1].rsplit("/", 1)[-1].rsplit("::", 1)[-1]
            if len(last) > 1:
                kw.add(last.lower())

        return sorted(kw)

    # ------------------------------------------------------------------
    # Index a single file
    # ------------------------------------------------------------------

    def index_file(self, file_path: Path) -> Optional[FastIndexEntry]:
        """Read, extract, and return a FastIndexEntry for one file."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.warning("Could not read %s: %s", file_path, e)
            return None

        language = detect_language(file_path.suffix)
        result = extract(language, content)

        try:
            relative_path = str(file_path.relative_to(self.root))
        except ValueError:
            relative_path = str(file_path)

        stat = file_path.stat()
        metadata = FileMetadata(
            path=str(file_path),
            relative_path=relative_path,
            size=stat.st_size,
            modified_time=stat.st_mtime,
            created_time=stat.st_ctime,
            language=language,
            content_hash=self._compute_hash(content),
            line_count=content.count("\n") + 1,
        )

        keywords = self._build_keywords(relative_path, result)

        return FastIndexEntry(
            metadata=metadata,
            imports=result.imports,
            exports=result.exports,
            functions=result.functions,
            classes=result.classes,
            comments=result.comments[:50],  # cap stored comments
            keywords=keywords,
        )

    # ------------------------------------------------------------------
    # Full index
    # ------------------------------------------------------------------

    def index(self) -> FastIndex:
        """Scan all files under root and build a FastIndex from scratch."""
        files_to_index: List[Path] = []
        for file_path in self.root.rglob("*"):
            if file_path.is_dir():
                continue
            if self._should_index(file_path):
                files_to_index.append(file_path)

        print(f"\nFound {len(files_to_index)} file(s) to fast-index")

        entries: Dict[str, FastIndexEntry] = {}
        pbar = tqdm(
            total=len(files_to_index),
            desc="Fast indexing",
            unit="file",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}",
            leave=False,
        )

        for fp in files_to_index:
            entry = self.index_file(fp)
            if entry:
                entries[entry.metadata.relative_path] = entry
            pbar.update(1)

        pbar.close()

        now = datetime.now().isoformat()
        fast_index = FastIndex(
            root_path=str(self.root),
            created_at=now,
            updated_at=now,
            files=entries,
        )

        fast_index.dependency_graph = self.build_dependency_graph(fast_index)
        return fast_index

    # ------------------------------------------------------------------
    # Incremental index
    # ------------------------------------------------------------------

    def incremental_index(self, existing: FastIndex) -> FastIndex:
        """Re-index only files that changed (by content hash) or are new; remove deleted files."""
        current_files: Dict[str, Path] = {}
        for file_path in self.root.rglob("*"):
            if file_path.is_dir():
                continue
            if self._should_index(file_path):
                try:
                    rel = str(file_path.relative_to(self.root))
                except ValueError:
                    rel = str(file_path)
                current_files[rel] = file_path

        # Determine what changed
        to_index: List[Path] = []
        unchanged: Dict[str, FastIndexEntry] = {}

        for rel_path, fp in current_files.items():
            old_entry = existing.files.get(rel_path)
            if old_entry:
                try:
                    content = fp.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    to_index.append(fp)
                    continue
                current_hash = self._compute_hash(content)
                if current_hash == old_entry.metadata.content_hash:
                    unchanged[rel_path] = old_entry
                    continue
            to_index.append(fp)

        if not to_index:
            removed = set(existing.files.keys()) - set(current_files.keys())
            if removed:
                for r in removed:
                    existing.files.pop(r, None)
                existing.updated_at = datetime.now().isoformat()
                existing.dependency_graph = self.build_dependency_graph(existing)
            print(f"\nNo changed files detected ({len(unchanged)} unchanged, {len(removed) if removed else 0} removed)")
            return existing

        print(f"\nFast indexing: {len(to_index)} changed/new, {len(unchanged)} unchanged")

        pbar = tqdm(
            total=len(to_index),
            desc="Fast indexing",
            unit="file",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}",
            leave=False,
        )

        new_entries: Dict[str, FastIndexEntry] = dict(unchanged)
        for fp in to_index:
            entry = self.index_file(fp)
            if entry:
                new_entries[entry.metadata.relative_path] = entry
            pbar.update(1)

        pbar.close()

        fast_index = FastIndex(
            root_path=str(self.root),
            created_at=existing.created_at,
            updated_at=datetime.now().isoformat(),
            files=new_entries,
            version=existing.version,
        )
        fast_index.dependency_graph = self.build_dependency_graph(fast_index)
        return fast_index

    # ------------------------------------------------------------------
    # Dependency graph
    # ------------------------------------------------------------------

    def build_dependency_graph(self, index: FastIndex) -> DependencyGraph:
        """Resolve import strings to project-internal file paths."""
        graph = DependencyGraph()

        # Build a lookup: module-style name -> relative path
        # e.g. "filesift._core.fast_index" or "fast_index" -> "filesift/_core/fast_index.py"
        module_lookup: Dict[str, str] = {}
        for rel_path in index.files:
            # Strip extension, convert path separators to dots
            stem = rel_path
            for ext in SUPPORTED_EXTENSIONS:
                if stem.endswith(ext):
                    stem = stem[: -len(ext)]
                    break
            dotted = stem.replace("/", ".").replace("\\", ".")
            module_lookup[dotted] = rel_path
            # Also map the last component for short imports
            last = dotted.rsplit(".", 1)[-1]
            if last not in module_lookup:
                module_lookup[last] = rel_path
            # Also map the bare filename (without extension)
            basename = Path(rel_path).stem
            if basename not in module_lookup:
                module_lookup[basename] = rel_path

        for rel_path, entry in index.files.items():
            resolved: List[str] = []
            for imp in entry.imports:
                # Normalize: replace / or :: with dots
                normalized = imp.replace("/", ".").replace("::", ".")
                # Try full match, then progressively shorter prefixes
                target = module_lookup.get(normalized)
                if not target:
                    # Try last component
                    last = normalized.rsplit(".", 1)[-1]
                    target = module_lookup.get(last)
                if target and target != rel_path:
                    resolved.append(target)

            if resolved:
                graph.imports[rel_path] = sorted(set(resolved))
                for target in resolved:
                    deps = graph.dependents.setdefault(target, [])
                    if rel_path not in deps:
                        deps.append(rel_path)

        # Sort dependents lists for determinism
        for key in graph.dependents:
            graph.dependents[key] = sorted(graph.dependents[key])

        return graph
