"""Medium story collector via feed endpoints."""

from urllib.parse import urlparse

from app.collectors.rss import RSSCollector
from app.schemas import RawContentItem


class MediumCollector:
    """Collect Medium stories using Medium RSS feeds."""

    def __init__(self) -> None:
        """Initialize Medium collector."""
        self._rss = RSSCollector(source_type="medium_story", source_name="Medium")

    async def fetch_entries(self, url: str, limit: int = 20) -> tuple[str, list[RawContentItem]]:
        """Resolve Medium URL into feed URL and fetch entries."""
        feed_url = self._build_feed_url(url)
        entries = await self._rss.fetch_entries(feed_url=feed_url, limit=limit)
        for entry in entries:
            entry.metadata.update({"source_url": url, "quality_signal": "editorial_platform"})
        return feed_url, entries

    def _build_feed_url(self, url: str) -> str:
        """Infer Medium feed endpoint from any Medium URL."""
        parsed = urlparse(url)
        if "/feed/" in parsed.path:
            return url
        path_parts = [part for part in parsed.path.split("/") if part]
        if parsed.netloc.startswith("@"):
            handle = parsed.netloc
            return f"https://medium.com/feed/{handle}"
        if path_parts and path_parts[0].startswith("@"):
            return f"https://medium.com/feed/{path_parts[0]}"
        if path_parts:
            return f"https://medium.com/feed/{path_parts[0]}"
        raise ValueError("Could not infer a Medium feed URL from the provided input.")
