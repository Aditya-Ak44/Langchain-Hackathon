"""Generic URL collector with source-specific dispatch."""

import re
from urllib.parse import urlparse

from app.collectors.base import BaseCollector
from app.collectors.medium import MediumCollector
from app.collectors.rss import RSSCollector
from app.collectors.twitter import TwitterCollector
from app.collectors.youtube import YouTubeCollector
from app.schemas import RawContentItem

_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_DESC_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_OG_DESC_RE = re.compile(
    r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


class GenericCollector(BaseCollector):
    """Collect content from arbitrary URLs with intelligent routing."""

    def __init__(self) -> None:
        """Initialize dependent collectors."""
        super().__init__(source_type="url", source_name="Generic URL")
        self.rss_collector = RSSCollector()
        self.youtube_collector = YouTubeCollector()
        self.twitter_collector = TwitterCollector()
        self.medium_collector = MediumCollector()

    async def fetch_entries(
        self,
        any_url: str,
        limit: int = 20,
    ) -> tuple[str, list[RawContentItem]]:
        """Dispatch URL to best-fit collector, then fallback to generic extraction."""
        parsed = urlparse(any_url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()

        if "youtube.com" in host or "youtu.be" in host:
            return await self.youtube_collector.fetch_entries(channel_url=any_url, limit=limit)
        if host.endswith("x.com") or host.endswith("twitter.com"):
            return await self.twitter_collector.fetch_entries(thread_url=any_url, limit=limit)
        if "medium.com" in host:
            return await self.medium_collector.fetch_entries(url=any_url, limit=limit)
        if path.endswith(".xml") or "rss" in path or "atom" in path or "feed" in path:
            return any_url, await self.rss_collector.fetch_entries(feed_url=any_url, limit=limit)

        html = await self.get_text(any_url)
        if "<rss" in html.lower() or "<feed" in html.lower():
            return any_url, self.rss_collector.parse_feed(
                xml_text=html,
                limit=limit,
                feed_url=any_url,
            )
        return any_url, [self._extract_web_document(any_url, html)]

    def _extract_web_document(self, url: str, html: str) -> RawContentItem:
        """Extract basic title/description from arbitrary HTML pages."""
        title_match = _TITLE_RE.search(html)
        desc_match = _DESC_RE.search(html) or _OG_DESC_RE.search(html)
        title = self.clean_text(title_match.group(1)) if title_match else url
        description = self.clean_text(desc_match.group(1)) if desc_match else ""
        content = description or title
        return RawContentItem(
            source_type=self.source_type,
            source_name=self.source_name,
            title=title,
            link=url,
            description=description,
            content=content,
            published_at="",
            author=None,
            metadata={"collection_note": "Generic HTML extraction."},
        )
