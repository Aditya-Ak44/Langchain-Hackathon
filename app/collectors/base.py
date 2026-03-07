"""Base collector utilities and interface."""

import re

import httpx

_TAG_RE = re.compile(r"<[^>]+>")


class BaseCollector:
    """Shared HTTP and text-normalization behavior for collectors."""

    def __init__(self, source_type: str, source_name: str) -> None:
        """Initialize common collector settings."""
        self.source_type = source_type
        self.source_name = source_name
        self.timeout = httpx.Timeout(25.0, connect=8.0)

    async def get_text(self, url: str) -> str:
        """Fetch URL content as text with redirect support."""
        headers = {"User-Agent": "ContentAggregatorBot/1.0 (+https://localhost)"}
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def clean_text(self, value: str) -> str:
        """Remove markup and normalize whitespace."""
        no_tags = _TAG_RE.sub(" ", value or "")
        return " ".join(no_tags.split())
