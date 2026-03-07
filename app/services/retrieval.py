"""Semantic retrieval over chunk embeddings."""

import math
from typing import Any

from app.database import SurrealDBClient
from app.processors.embeddings import EmbeddingService
from app.schemas import SourceItem


class SemanticRetriever:
    """Retrieve semantically similar sources using chunk-level vectors."""

    def __init__(self, db: SurrealDBClient, embeddings: EmbeddingService) -> None:
        """Initialize retriever dependencies."""
        self.db = db
        self.embeddings = embeddings

    async def search(self, query: str, top_k: int = 4) -> list[SourceItem]:
        """Return top-k similar content sources for a query string."""
        query_vec = await self.embeddings.create_embedding(query)
        content_rows = await self.db.list_content(limit=1500, offset=0)
        content_map = {
            str(row.get("id", "")): row
            for row in content_rows
            if row.get("processing_status") == "processed" and str(row.get("id", ""))
        }
        if not content_map:
            return []

        chunk_rows = await self.db.list_content_chunks(limit=4000)
        scored_chunks: list[tuple[float, dict[str, Any]]] = []
        for row in chunk_rows:
            raw_embedding = row.get("embedding")
            if not isinstance(raw_embedding, list) or not raw_embedding:
                continue
            candidate = [float(item) for item in raw_embedding]
            score = _cosine_similarity(query_vec, candidate)
            scored_chunks.append((score, row))

        by_content: dict[str, tuple[float, str]] = {}
        scored_chunks.sort(key=lambda item: item[0], reverse=True)
        for score, chunk in scored_chunks:
            content_id = str(chunk.get("content_id", ""))
            if not content_id or content_id not in content_map:
                continue
            current = by_content.get(content_id)
            if current is None or score > current[0]:
                excerpt = str(chunk.get("chunk_text", ""))[:500]
                by_content[content_id] = (score, excerpt)

        # Backward-compatible fallback for previously ingested records without chunks.
        for content_id, row in content_map.items():
            if content_id in by_content:
                continue
            raw_embedding = row.get("embedding")
            if not isinstance(raw_embedding, list) or not raw_embedding:
                continue
            candidate = [float(item) for item in raw_embedding]
            score = _cosine_similarity(query_vec, candidate)
            excerpt = str(row.get("raw_content", "") or row.get("summary_medium", ""))[:500]
            by_content[content_id] = (score, excerpt)

        top_items = sorted(by_content.items(), key=lambda item: item[1][0], reverse=True)[:top_k]
        results: list[SourceItem] = []
        for content_id, (score, excerpt) in top_items:
            content = content_map.get(content_id)
            if not content:
                continue
            results.append(_to_source_item(score=score, row=content, excerpt=excerpt))
        return results


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity with safe zero-vector handling."""
    if len(vec_a) != len(vec_b):
        min_len = min(len(vec_a), len(vec_b))
        vec_a = vec_a[:min_len]
        vec_b = vec_b[:min_len]
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def _to_source_item(score: float, row: dict[str, Any], excerpt: str) -> SourceItem:
    """Convert a content record and top chunk into source metadata."""
    return SourceItem(
        id=str(row.get("id", "")),
        title=str(row.get("title", "")),
        link=str(row.get("link", "")),
        score=round(float(score), 4),
        excerpt=excerpt,
        summary=str(row.get("summary_medium", "")),
        topics=[str(item) for item in row.get("topics", [])],
        keywords=[str(item) for item in row.get("keywords", [])],
    )
