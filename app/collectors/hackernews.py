"""Hacker News collector using official Firebase endpoints."""

from datetime import datetime, timezone
from typing import Any

import httpx

from app.collectors.base import BaseCollector
from app.schemas import RawContentItem


class HackerNewsCollector(BaseCollector):
    """Collect top Hacker News stories and discussion metadata."""

    def __init__(self) -> None:
        """Initialize Hacker News collector metadata."""
        super().__init__(source_type="news", source_name="Hacker News")
        self._base = "https://hacker-news.firebaseio.com/v0"

    async def fetch_entries(self, limit: int = 20) -> tuple[str, list[RawContentItem]]:
        """Fetch top stories and map them into unified content records."""
        top_ids = await self._get_json(f"{self._base}/topstories.json")
        if not isinstance(top_ids, list):
            raise ValueError("Unexpected Hacker News top stories payload.")

        entries: list[RawContentItem] = []
        for story_id in top_ids[:limit]:
            item = await self._get_json(f"{self._base}/item/{story_id}.json")
            if not isinstance(item, dict):
                continue
            entries.append(self._to_item(item))
        return f"{self._base}/topstories.json", entries

    async def _get_json(self, url: str) -> Any:
        """Fetch JSON payload with timeout and rate-aware settings."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    def _to_item(self, item: dict[str, Any]) -> RawContentItem:
        """Convert Hacker News API story payload into unified content."""
        timestamp = item.get("time")
        published_at = ""
        if isinstance(timestamp, int):
            published_at = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
        fallback_url = f"https://news.ycombinator.com/item?id={item.get('id', '')}"
        url = str(item.get("url", "") or fallback_url)
        text = self.clean_text(str(item.get("text", "")))
        title = str(item.get("title", "")).strip()
        return RawContentItem(
            source_type=self.source_type,
            source_name=self.source_name,
            title=title,
            link=url,
            description=text or title,
            content=text or title,
            published_at=published_at,
            author=str(item.get("by", "")).strip() or None,
            metadata={
                "hn_id": item.get("id"),
                "score": item.get("score", 0),
                "comments_count": item.get("descendants", 0),
                "type": item.get("type", "story"),
            },
        )
