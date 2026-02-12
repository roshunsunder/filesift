"""Factory for constructing embedding models from config."""

from filesift._core.embeddings.base import EmbeddingModel


def create_embedding_model(config: dict | None = None) -> EmbeddingModel:
    """Create an embedding model from the configuration.

    Reads ``config["models"]["EMBEDDING_MODEL"]`` (default ``"nomic"``).
    """
    if config is None:
        from filesift._config.config import config_dict
        config = config_dict

    model_key = config.get("models", {}).get("EMBEDDING_MODEL", "nomic")

    if model_key in ("nomic", "nomic-ai/nomic-embed-text-v1.5"):
        from filesift._core.embeddings.nomic import NomicEmbedModel
        return NomicEmbedModel()

    raise ValueError(
        f"Unknown embedding model: {model_key!r}. Supported: 'nomic'"
    )
