"""Twitter/X collector with thread and handle support."""

import re
from urllib.parse import urlparse

import httpx

from app.collectors.base import BaseCollector
from app.schemas import RawContentItem

_HASHTAG_RE = re.compile(r"#([A-Za-z0-9_]+)")
_META_CONTENT_RE = re.compile(
    r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


class TwitterCollector(BaseCollector):
    """Collect thread-like content from public Twitter/X URLs."""

    def __init__(self) -> None:
        """Initialize Twitter collector metadata."""
        super().__init__(source_type="twitter_thread", source_name="Twitter/X")

    async def fetch_entries(
        self,
        twitter_handle: str | None = None,
        thread_url: str | None = None,
        limit: int = 20,
    ) -> tuple[str, list[RawContentItem]]:
        """Fetch thread content by URL or handle feed fallback."""
        if thread_url:
            return thread_url, [await self._fetch_thread(thread_url)]
        if twitter_handle:
            handle = twitter_handle.strip().lstrip("@")
            rss_url = f"https://nitter.net/{handle}/rss"
            entries = await self._fetch_nitter_rss(rss_url=rss_url, limit=limit)
            return rss_url, entries
        raise ValueError("Provide either twitter_handle or thread_url.")

    async def _fetch_thread(self, thread_url: str) -> RawContentItem:
        """Fetch a single thread URL through fxtwitter mirror for better extractability."""
        mirror_url = (
            thread_url.replace("x.com", "fxtwitter.com")
            .replace("twitter.com", "fxtwitter.com")
        )
        html = await self.get_text(mirror_url)
        description_match = _META_CONTENT_RE.search(html)
        description = description_match.group(1).strip() if description_match else ""
        if not description:
            description = "Twitter thread content could not be extracted from public HTML."
        hashtags = _HASHTAG_RE.findall(description)
        author = self._extract_author(thread_url)
        return RawContentItem(
            source_type=self.source_type,
            source_name=self.source_name,
            title=f"Thread by @{author}" if author else "Twitter/X Thread",
            link=thread_url,
            description=self.clean_text(description),
            content=self.clean_text(description),
            published_at="",
            author=author or None,
            metadata={
                "likes": None,
                "retweets": None,
                "hashtags": hashtags[:12],
                "collection_note": "Best-effort extraction without official API.",
            },
        )

    async def _fetch_nitter_rss(self, rss_url: str, limit: int) -> list[RawContentItem]:
        """Fetch handle timeline via Nitter RSS fallback."""
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.get(rss_url)
            response.raise_for_status()
        from app.collectors.rss import RSSCollector

        rss_collector = RSSCollector(source_type=self.source_type, source_name=self.source_name)
        entries = rss_collector.parse_feed(response.text, limit=limit, feed_url=rss_url)
        for entry in entries:
            hashtags = _HASHTAG_RE.findall(entry.content or entry.description)
            entry.metadata.update(
                {
                    "likes": None,
                    "retweets": None,
                    "hashtags": hashtags[:12],
                    "collection_note": "Handle timeline collected via RSS fallback.",
                }
            )
        return entries

    def _extract_author(self, thread_url: str) -> str:
        """Extract author handle from a twitter/x status URL."""
        parsed = urlparse(thread_url)
        parts = [part for part in parsed.path.split("/") if part]
        if parts:
            return parts[0].lstrip("@")
        return ""
