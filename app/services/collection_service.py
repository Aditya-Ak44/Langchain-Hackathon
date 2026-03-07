"""Content collection orchestrator for multiple source types."""

from app.collectors.generic import GenericCollector
from app.collectors.hackernews import HackerNewsCollector
from app.collectors.medium import MediumCollector
from app.collectors.rss import RSSCollector
from app.collectors.twitter import TwitterCollector
from app.collectors.youtube import YouTubeCollector
from app.schemas import RawContentItem


class CollectionService:
    """Facade over source-specific collectors."""

    def __init__(self) -> None:
        """Initialize all supported collectors."""
        self.rss = RSSCollector()
        self.youtube = YouTubeCollector()
        self.twitter = TwitterCollector()
        self.hackernews = HackerNewsCollector()
        self.medium = MediumCollector()
        self.generic = GenericCollector()

    async def from_rss(self, url: str, limit: int) -> tuple[str, str, list[RawContentItem]]:
        """Collect entries from an RSS/Atom feed URL."""
        return "rss", url, await self.rss.fetch_entries(feed_url=url, limit=limit)

    async def from_youtube(
        self,
        channel_url: str | None,
        channel_id: str | None,
        username: str | None,
        limit: int,
    ) -> tuple[str, str, list[RawContentItem]]:
        """Collect entries from a YouTube channel source."""
        feed_url, entries = await self.youtube.fetch_entries(
            channel_url=channel_url,
            channel_id=channel_id,
            username=username,
            limit=limit,
        )
        return "youtube", feed_url, entries

    async def from_twitter(
        self,
        twitter_handle: str | None,
        thread_url: str | None,
        limit: int,
    ) -> tuple[str, str, list[RawContentItem]]:
        """Collect entries from Twitter/X source."""
        feed_url, entries = await self.twitter.fetch_entries(
            twitter_handle=twitter_handle,
            thread_url=thread_url,
            limit=limit,
        )
        return "twitter", feed_url, entries

    async def from_hackernews(self, limit: int) -> tuple[str, str, list[RawContentItem]]:
        """Collect entries from Hacker News top stories."""
        feed_url, entries = await self.hackernews.fetch_entries(limit=limit)
        return "hackernews", feed_url, entries

    async def from_url(self, any_url: str, limit: int) -> tuple[str, str, list[RawContentItem]]:
        """Collect content from any URL using source detection."""
        resolved_url, entries = await self.generic.fetch_entries(any_url=any_url, limit=limit)
        source_type = entries[0].source_type if entries else "url"
        return source_type, resolved_url, entries
