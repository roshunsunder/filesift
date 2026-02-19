"""Jina Code v2 embeddings via sentence-transformers."""

import numpy as np

from filesift._core.embeddings.base import EmbeddingModel


class JinaCodeEmbedModel(EmbeddingModel):
    """Local embedding model using jinaai/jina-embeddings-v2-base-code.

    Embeddings are L2-normalized so inner product == cosine similarity.
    """

    def __init__(self):
        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(1)

        device = "cuda" if torch.cuda.is_available() else "cpu"

        self._model = SentenceTransformer(
            "jinaai/jina-embeddings-v2-base-code",
            trust_remote_code=True,
            device=device,
        )
        self._model.max_seq_length = self.max_tokens

    def embed(self, text: str) -> np.ndarray:
        vec = self._model.encode([text], normalize_embeddings=True)
        return vec[0].astype(np.float32)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        vecs = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return vecs.astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        vec = self._model.encode([query], normalize_embeddings=True)
        return vec[0].astype(np.float32)

    @property
    def dimension(self) -> int:
        return 768

    @property
    def model_name(self) -> str:
        return "jinaai/jina-embeddings-v2-base-code"

    @property
    def max_tokens(self) -> int:
        return 2048
