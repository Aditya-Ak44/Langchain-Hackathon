"""RSS and Atom feed collector."""

from xml.etree import ElementTree

from app.collectors.base import BaseCollector
from app.schemas import RawContentItem


class RSSCollector(BaseCollector):
    """Collect and normalize entries from RSS/Atom feeds."""

    def __init__(self, source_type: str = "rss", source_name: str = "RSS/Atom") -> None:
        """Initialize RSS collector metadata."""
        super().__init__(source_type=source_type, source_name=source_name)

    async def fetch_entries(self, feed_url: str, limit: int = 20) -> list[RawContentItem]:
        """Fetch the latest entries from a feed URL."""
        xml_text = await self.get_text(feed_url)
        return self.parse_feed(xml_text=xml_text, limit=limit, feed_url=feed_url)

    def parse_feed(self, xml_text: str, limit: int, feed_url: str) -> list[RawContentItem]:
        """Parse RSS or Atom XML into unified content objects."""
        root = ElementTree.fromstring(xml_text)
        channel_items = root.findall("./channel/item")
        atom_entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        if channel_items:
            return self._parse_rss_items(channel_items, limit, feed_url)
        if atom_entries:
            return self._parse_atom_entries(atom_entries, limit, feed_url)
        raise ValueError("Unsupported feed format: no RSS or Atom entries found.")

    def _parse_rss_items(
        self,
        items: list[ElementTree.Element],
        limit: int,
        feed_url: str,
    ) -> list[RawContentItem]:
        """Parse RSS `<item>` nodes."""
        entries: list[RawContentItem] = []
        for item in items[:limit]:
            description = item.findtext("description", default="")
            content = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded", default="")
            entries.append(
                RawContentItem(
                    source_type=self.source_type,
                    source_name=self.source_name,
                    title=item.findtext("title", default="").strip(),
                    link=item.findtext("link", default="").strip(),
                    description=self.clean_text(description),
                    content=self.clean_text(content or description),
                    published_at=item.findtext("pubDate", default="").strip(),
                    author=item.findtext("author", default="").strip() or None,
                    metadata={"feed_url": feed_url},
                )
            )
        return entries

    def _parse_atom_entries(
        self,
        entries: list[ElementTree.Element],
        limit: int,
        feed_url: str,
    ) -> list[RawContentItem]:
        """Parse Atom `<entry>` nodes."""
        atom_ns = "{http://www.w3.org/2005/Atom}"
        parsed: list[RawContentItem] = []
        for entry in entries[:limit]:
            link_el = entry.find(f"{atom_ns}link")
            summary = entry.findtext(f"{atom_ns}summary", default="")
            content = entry.findtext(f"{atom_ns}content", default="")
            author = entry.findtext(f"{atom_ns}author/{atom_ns}name", default="")
            parsed.append(
                RawContentItem(
                    source_type=self.source_type,
                    source_name=self.source_name,
                    title=entry.findtext(f"{atom_ns}title", default="").strip(),
                    link=(link_el.attrib.get("href", "") if link_el is not None else "").strip(),
                    description=self.clean_text(summary),
                    content=self.clean_text(content or summary),
                    published_at=entry.findtext(f"{atom_ns}updated", default="").strip(),
                    author=author.strip() or None,
                    metadata={"feed_url": feed_url},
                )
            )
        return parsed
