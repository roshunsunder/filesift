"""Nomic Embed Text v1.5 via sentence-transformers."""

import numpy as np
from filesift._core.embeddings.base import EmbeddingModel


class NomicEmbedModel(EmbeddingModel):
    """Local embedding model using nomic-ai/nomic-embed-text-v1.5.

    Nomic requires task-specific prefixes:
      - "search_document: " for indexing
      - "search_query: " for searching

    Embeddings are L2-normalized so inner product == cosine similarity.
    """

    DOCUMENT_PREFIX = "search_document: "
    QUERY_PREFIX = "search_query: "

    def __init__(self):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(
            "nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True
        )

    def embed(self, text: str) -> np.ndarray:
        prefixed = self.DOCUMENT_PREFIX + text
        vec = self._model.encode([prefixed], normalize_embeddings=True)
        return vec[0].astype(np.float32)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        prefixed = [self.DOCUMENT_PREFIX + t for t in texts]
        vecs = self._model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
        return vecs.astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        prefixed = self.QUERY_PREFIX + query
        vec = self._model.encode([prefixed], normalize_embeddings=True)
        return vec[0].astype(np.float32)

    @property
    def dimension(self) -> int:
        return 768

    @property
    def model_name(self) -> str:
        return "nomic-ai/nomic-embed-text-v1.5"

    @property
    def max_tokens(self) -> int:
        return 8192
