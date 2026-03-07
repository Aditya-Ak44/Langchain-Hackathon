"""Embedding service backed by HuggingFace sentence-transformers."""

import asyncio
from functools import lru_cache

from sentence_transformers import SentenceTransformer

_EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """Load the shared sentence-transformer model once."""
    return SentenceTransformer(_EMBEDDING_MODEL_NAME)


class EmbeddingService:
    """Generate normalized embeddings for content records."""

    async def create_embedding(self, text: str) -> list[float]:
        """Return a 384-dimensional embedding vector."""
        model = _get_model()
        vector = await asyncio.to_thread(model.encode, text, normalize_embeddings=True)
        values = vector.tolist()
        return [float(item) for item in values]
