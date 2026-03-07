"""Tavily search service wrapper."""

import json
from typing import Any

import httpx

from app.config import Settings


class TavilyService:
    """Async client for Tavily search API."""

    def __init__(self, settings: Settings) -> None:
        """Initialize Tavily endpoint details."""
        self.settings = settings
        self.base_url = settings.tavily_base_url.rstrip("/")
        self.api_key = settings.tavily_api_key
        self.timeout = httpx.Timeout(15.0, connect=5.0)

    async def search(self, query: str, max_results: int = 5) -> str:
        """Return Tavily search results as JSON text."""
        if not self.api_key:
            payload = {
                "warning": "TAVILY_API_KEY is not configured.",
                "results": [],
            }
            return json.dumps(payload, ensure_ascii=True)

        request_body = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max(1, min(max_results, 10)),
            "search_depth": "basic",
            "include_raw_content": False,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/search", json=request_body)
            response.raise_for_status()
            data: dict[str, Any] = response.json()

        results = data.get("results", [])
        minimal = []
        for row in results if isinstance(results, list) else []:
            if not isinstance(row, dict):
                continue
            minimal.append(
                {
                    "title": row.get("title", ""),
                    "url": row.get("url", ""),
                    "content": row.get("content", ""),
                    "score": row.get("score", 0),
                }
            )
        return json.dumps({"results": minimal}, ensure_ascii=True)
