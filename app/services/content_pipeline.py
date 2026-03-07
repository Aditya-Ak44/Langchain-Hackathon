"""Background content processing pipeline."""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.database import SurrealDBClient
from app.processors.embeddings import EmbeddingService
from app.processors.summarizer import OllamaSummarizer
from app.schemas import RawContentItem

logger = logging.getLogger(__name__)
_WHITESPACE_RE = re.compile(r"\s+")


class ContentPipeline:
    """Queue-based async pipeline for article processing."""

    def __init__(
        self,
        db: SurrealDBClient,
        summarizer: OllamaSummarizer,
        embedding_service: EmbeddingService,
    ) -> None:
        """Create a pipeline with all dependencies."""
        self.db = db
        self.summarizer = summarizer
        self.embedding_service = embedding_service
        self.settings = get_settings()
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []

    async def start(self, worker_count: int) -> None:
        """Start background worker tasks."""
        if self._workers:
            return
        for worker_idx in range(worker_count):
            task = asyncio.create_task(self._worker(worker_idx))
            self._workers.append(task)
        logger.info("Content pipeline started with %s workers", worker_count)

    async def stop(self) -> None:
        """Stop background workers gracefully."""
        if not self._workers:
            return

        await self._queue.join()
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Content pipeline stopped")

    async def enqueue_articles(
        self, feed_id: str, feed_url: str, articles: list[RawContentItem]
    ) -> int:
        """Queue articles for asynchronous processing."""
        for article in articles:
            await self._queue.put(
                {
                    "feed_id": feed_id,
                    "feed_url": feed_url,
                    "article": article,
                }
            )
        return len(articles)

    async def _worker(self, worker_idx: int) -> None:
        """Continuously process queued articles."""
        while True:
            item = await self._queue.get()
            try:
                await self._process_article(item)
            except Exception:
                logger.exception("Worker %s failed processing a queue item", worker_idx)
            finally:
                self._queue.task_done()

    async def _process_article(self, item: dict[str, Any]) -> None:
        """Process one article and persist success/failure states."""
        article: RawContentItem = item["article"]
        feed_id = str(item["feed_id"])
        feed_url = str(item["feed_url"])
        cleaned_text = self._extract_text(article)

        base_payload: dict[str, Any] = {
            "feed_id": feed_id,
            "feed_url": feed_url,
            "source_type": article.source_type,
            "source_name": article.source_name,
            "title": article.title,
            "link": article.link,
            "published_at": article.published_at,
            "author": article.author,
            "metadata": article.metadata,
            "raw_description": article.description,
            "raw_content": article.content,
            "created_at": self._utc_now(),
        }

        try:
            if not cleaned_text:
                raise ValueError("Article content is empty after cleaning.")

            summaries = await self.summarizer.generate_summaries(cleaned_text)
            topics, keywords = await self.summarizer.extract_topics_keywords(cleaned_text)
            embedding = await self.embedding_service.create_embedding(cleaned_text)
            chunks = self._chunk_text(cleaned_text)
            chunk_payloads: list[dict[str, Any]] = []
            for index, chunk_text in enumerate(chunks):
                chunk_embedding = await self.embedding_service.create_embedding(chunk_text)
                chunk_payloads.append(
                    {
                        "chunk_index": index,
                        "chunk_text": chunk_text,
                        "embedding": chunk_embedding,
                        "embedding_dimensions": len(chunk_embedding),
                    }
                )

            content_id = await self.db.create_article(
                {
                    **base_payload,
                    "topics": topics,
                    "keywords": keywords,
                    "summary_short": summaries.short,
                    "summary_medium": summaries.medium,
                    "summary_long": summaries.long,
                    "embedding": embedding,
                    "embedding_dimensions": len(embedding),
                    "processing_status": "processed",
                    "error": None,
                }
            )
            chunk_rows = [
                {
                    **payload,
                    "content_id": content_id,
                    "created_at": self._utc_now(),
                }
                for payload in chunk_payloads
            ]
            await self.db.create_content_chunks(chunk_rows)
        except Exception as exc:
            logger.exception("Article processing failed for %s", article.link)
            failure_payload = {
                **base_payload,
                "topics": [],
                "keywords": [],
                "summary_short": "",
                "summary_medium": "",
                "summary_long": "",
                "embedding": [],
                "embedding_dimensions": 0,
                "processing_status": "failed",
                "error": str(exc),
            }
            await self.db.create_article(failure_payload)

    def _extract_text(self, article: RawContentItem) -> str:
        """Build cleaned text for downstream LLM and embedding jobs."""
        joined = f"{article.title}\n\n{article.content or article.description}".strip()
        compact = _WHITESPACE_RE.sub(" ", joined)
        max_chars = self.settings.max_article_chars
        return compact[:max_chars]

    def _chunk_text(self, text: str) -> list[str]:
        """Split cleaned text into overlapping chunks for vector search."""
        chunk_size = self.settings.chunk_size_chars
        overlap = self.settings.chunk_overlap_chars
        max_chunks = self.settings.max_chunks_per_item
        if chunk_size <= 0:
            return [text]

        chunks: list[str] = []
        start = 0
        while start < len(text) and len(chunks) < max_chunks:
            end = min(start + chunk_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
        return chunks or [text]

    def _utc_now(self) -> str:
        """Return UTC timestamp in ISO-8601 format."""
        return datetime.now(tz=timezone.utc).isoformat()
