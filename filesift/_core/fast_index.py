"""Data structures for the fast (no-LLM) indexing tier."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set


@dataclass
class FileMetadata:
    path: str
    relative_path: str
    size: int
    modified_time: float
    created_time: float
    language: str
    content_hash: str
    line_count: int

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "relative_path": self.relative_path,
            "size": self.size,
            "modified_time": self.modified_time,
            "created_time": self.created_time,
            "language": self.language,
            "content_hash": self.content_hash,
            "line_count": self.line_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FileMetadata":
        return cls(
            path=d["path"],
            relative_path=d["relative_path"],
            size=d["size"],
            modified_time=d["modified_time"],
            created_time=d["created_time"],
            language=d["language"],
            content_hash=d["content_hash"],
            line_count=d["line_count"],
        )


@dataclass
class FastIndexEntry:
    metadata: FileMetadata
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    comments: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "metadata": self.metadata.to_dict(),
            "imports": self.imports,
            "exports": self.exports,
            "functions": self.functions,
            "classes": self.classes,
            "comments": self.comments,
            "keywords": self.keywords,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FastIndexEntry":
        return cls(
            metadata=FileMetadata.from_dict(d["metadata"]),
            imports=d.get("imports", []),
            exports=d.get("exports", []),
            functions=d.get("functions", []),
            classes=d.get("classes", []),
            comments=d.get("comments", []),
            keywords=d.get("keywords", []),
        )


@dataclass
class DependencyGraph:
    imports: Dict[str, List[str]] = field(default_factory=dict)
    dependents: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "imports": self.imports,
            "dependents": self.dependents,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DependencyGraph":
        return cls(
            imports=d.get("imports", {}),
            dependents=d.get("dependents", {}),
        )


@dataclass
class FastIndex:
    root_path: str
    created_at: str  # ISO format
    updated_at: str  # ISO format
    files: Dict[str, FastIndexEntry] = field(default_factory=dict)
    dependency_graph: Optional[DependencyGraph] = None
    version: str = "1.0.0"

    def to_dict(self) -> dict:
        return {
            "root_path": self.root_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "files": {k: v.to_dict() for k, v in self.files.items()},
            "dependency_graph": self.dependency_graph.to_dict() if self.dependency_graph else None,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FastIndex":
        dep_graph = None
        if d.get("dependency_graph"):
            dep_graph = DependencyGraph.from_dict(d["dependency_graph"])
        return cls(
            root_path=d["root_path"],
            created_at=d["created_at"],
            updated_at=d["updated_at"],
            files={k: FastIndexEntry.from_dict(v) for k, v in d.get("files", {}).items()},
            dependency_graph=dep_graph,
            version=d.get("version", "1.0.0"),
        )
