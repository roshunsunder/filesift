"""Abstract embedding model interface."""

from abc import ABC, abstractmethod
import numpy as np


class EmbeddingModel(ABC):
    """Base class for all embedding models.

    Implementations must return float32 numpy arrays for FAISS compatibility.
    """

    @abstractmethod
    def embed(self, text: str) -> np.ndarray:
        """Embed a single document text. Returns a 1-D float32 array."""

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Embed a batch of document texts. Returns a 2-D float32 array (N x dim)."""

    @abstractmethod
    def embed_query(self, query: str) -> np.ndarray:
        """Embed a search query. May apply a different prefix than embed()."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensionality of the output vectors."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Human-readable model identifier."""

    @property
    def max_tokens(self) -> int:
        """Maximum token window for the model. Override in subclasses."""
        return 8192
