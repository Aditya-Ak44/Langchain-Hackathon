"""YouTube content collector with transcript extraction."""

import asyncio
import logging
import re
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

import httpx
from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled, YouTubeTranscriptApi

from app.collectors.base import BaseCollector
from app.schemas import RawContentItem

logger = logging.getLogger(__name__)
_OG_DESC_RE = re.compile(
    r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


class YouTubeCollector(BaseCollector):
    """Collect YouTube videos via channel feeds and transcript extraction."""

    def __init__(self) -> None:
        """Initialize YouTube collector metadata."""
        super().__init__(source_type="video", source_name="YouTube")

    async def fetch_entries(
        self,
        channel_url: str | None = None,
        channel_id: str | None = None,
        username: str | None = None,
        limit: int = 20,
    ) -> tuple[str, list[RawContentItem]]:
        """Fetch videos from a channel source or single video URL."""
        video_id = self._extract_video_id_from_url(channel_url) if channel_url else ""
        if video_id:
            entry = await self._fetch_single_video(channel_url or "", video_id)
            return channel_url or "", [entry]

        feed_url = self._build_feed_url(
            channel_url=channel_url,
            channel_id=channel_id,
            username=username,
        )
        xml_text = await self.get_text(feed_url)
        parsed = self._parse_feed(xml_text, limit)
        enriched = await self._enrich_with_transcripts(parsed)
        return feed_url, enriched

    def _build_feed_url(
        self,
        channel_url: str | None,
        channel_id: str | None,
        username: str | None,
    ) -> str:
        """Resolve YouTube input into a channel feed URL."""
        if channel_id:
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id.strip()}"
        if username:
            handle = username.strip().lstrip("@")
            return f"https://www.youtube.com/feeds/videos.xml?user={handle}"
        if channel_url:
            parsed = urlparse(channel_url)
            query = parse_qs(parsed.query)
            if "channel_id" in query and query["channel_id"]:
                channel_id_value = query["channel_id"][0]
                return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id_value}"
            parts = [part for part in parsed.path.split("/") if part]
            if "channel" in parts:
                idx = parts.index("channel")
                if idx + 1 < len(parts):
                    return f"https://www.youtube.com/feeds/videos.xml?channel_id={parts[idx + 1]}"
            if "@" in parsed.path:
                handle = parsed.path.strip("/").lstrip("@")
                return f"https://www.youtube.com/feeds/videos.xml?user={handle}"
        raise ValueError("Provide channel_id, username, channel URL, or a direct video URL.")

    def _parse_feed(self, xml_text: str, limit: int) -> list[RawContentItem]:
        """Parse YouTube Atom feed entries."""
        root = ElementTree.fromstring(xml_text)
        atom_ns = "{http://www.w3.org/2005/Atom}"
        yt_ns = "{http://www.youtube.com/xml/schemas/2015}"
        entries = root.findall(f"{atom_ns}entry")
        channel_title = root.findtext(f"{atom_ns}title", default="YouTube Channel").strip()

        parsed: list[RawContentItem] = []
        for entry in entries[:limit]:
            title = entry.findtext(f"{atom_ns}title", default="").strip()
            link_el = entry.find(f"{atom_ns}link")
            description = entry.findtext(f"{atom_ns}group/{atom_ns}description", default="")
            if not description:
                description = entry.findtext(f"{yt_ns}description", default="")
            published_at = entry.findtext(f"{atom_ns}published", default="").strip()
            video_id = entry.findtext(f"{yt_ns}videoId", default="").strip()
            author = entry.findtext(f"{atom_ns}author/{atom_ns}name", default="").strip() or None
            link = (link_el.attrib.get("href", "") if link_el is not None else "").strip()

            parsed.append(
                RawContentItem(
                    source_type=self.source_type,
                    source_name=self.source_name,
                    title=title,
                    link=link,
                    description=self.clean_text(description),
                    content=self.clean_text(description),
                    published_at=published_at,
                    author=author,
                    metadata={
                        "channel_title": channel_title,
                        "video_id": video_id,
                        "duration_seconds": None,
                        "transcript_available": False,
                    },
                )
            )
        return parsed

    async def _fetch_single_video(self, video_url: str, video_id: str) -> RawContentItem:
        """Collect a single shared YouTube video using oEmbed + transcript."""
        title = video_url
        author = None
        description_text = ""
        oembed_url = f"https://www.youtube.com/oembed?url={video_url}&format=json"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(oembed_url)
                response.raise_for_status()
                payload = response.json()
                title = str(payload.get("title", title))
                author_name = str(payload.get("author_name", "")).strip()
                author = author_name or None
        except Exception:
            logger.warning("YouTube oEmbed fetch failed for %s", video_url)

        try:
            page_html = await self.get_text(f"https://www.youtube.com/watch?v={video_id}")
            desc_match = _OG_DESC_RE.search(page_html)
            description_text = desc_match.group(1).strip() if desc_match else ""
        except Exception:
            logger.info("YouTube page description fetch failed for video_id=%s", video_id)

        transcript = await self._fetch_transcript(video_id)
        transcript_clean = self.clean_text(transcript)
        transcript_ok = self._is_useful_transcript(transcript_clean)
        fallback = self.clean_text(description_text) or title
        content = transcript_clean if transcript_ok else fallback
        return RawContentItem(
            source_type=self.source_type,
            source_name=self.source_name,
            title=title,
            link=video_url,
            description=self.clean_text(description_text) or title,
            content=content,
            published_at="",
            author=author,
            metadata={
                "video_id": video_id,
                "duration_seconds": None,
                "transcript_available": transcript_ok,
                "transcript_chars": len(transcript_clean),
            },
        )

    async def _enrich_with_transcripts(self, items: list[RawContentItem]) -> list[RawContentItem]:
        """Attach transcript text to entries when available."""
        tasks = [self._attach_transcript(item) for item in items]
        return await asyncio.gather(*tasks)

    async def _attach_transcript(self, item: RawContentItem) -> RawContentItem:
        """Update item content with transcript text if retrievable."""
        video_id = str(item.metadata.get("video_id", ""))
        if not video_id:
            return item
        transcript = await self._fetch_transcript(video_id)
        transcript_clean = self.clean_text(transcript)
        if self._is_useful_transcript(transcript_clean):
            item.content = self.clean_text(transcript)
            item.metadata["transcript_available"] = True
            item.metadata["transcript_chars"] = len(transcript_clean)
        else:
            item.metadata["transcript_available"] = False
            item.metadata["transcript_chars"] = len(transcript_clean)
        return item

    async def _fetch_transcript(self, video_id: str) -> str:
        """Fetch video transcript text with language fallback."""
        def _sync_fetch() -> str:
            api = YouTubeTranscriptApi()
            preferred_langs = ["en", "en-US", "en-GB"]

            try:
                fetched = api.fetch(video_id, languages=preferred_langs)
            except NoTranscriptFound:
                transcript_list = api.list(video_id)
                try:
                    transcript = transcript_list.find_transcript(preferred_langs)
                except NoTranscriptFound:
                    try:
                        transcript = transcript_list.find_generated_transcript(["en"])
                    except NoTranscriptFound:
                        return ""
                fetched = transcript.fetch()
            except TranscriptsDisabled:
                return ""

            pieces: list[str] = []
            for snippet in fetched:
                text = str(getattr(snippet, "text", "")).strip()
                if text:
                    pieces.append(text)
            return " ".join(pieces)

        try:
            return await asyncio.to_thread(_sync_fetch)
        except Exception as exc:
            logger.info(
                "Transcript unavailable for video_id=%s reason=%s",
                video_id,
                type(exc).__name__,
            )
            return ""

    def _is_useful_transcript(self, transcript: str) -> bool:
        """Check if transcript has enough signal for summarization/embedding."""
        if not transcript:
            return False
        words = transcript.split()
        unique_words = len(set(word.lower() for word in words))
        return len(transcript) >= 350 and len(words) >= 80 and unique_words >= 40

    def _extract_video_id_from_url(self, url: str | None) -> str:
        """Extract video id from watch/youtu.be style URLs."""
        if not url:
            return ""
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if "youtu.be" in host:
            return parsed.path.strip("/")
        query = parse_qs(parsed.query)
        if "v" in query and query["v"]:
            return query["v"][0]
        return ""
