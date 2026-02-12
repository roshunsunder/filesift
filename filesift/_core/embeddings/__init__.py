"""Embedding model abstraction layer."""

from filesift._core.embeddings.base import EmbeddingModel
from filesift._core.embeddings.factory import create_embedding_model

__all__ = ["EmbeddingModel", "create_embedding_model"]
