"""Async SurrealDB wrapper."""

import logging
from datetime import datetime, timezone
from typing import Any

from surrealdb import AsyncSurreal

from app.config import get_settings

logger = logging.getLogger(__name__)


class SurrealDBClient:
    """Manage async SurrealDB connections and content persistence."""

    def __init__(self) -> None:
        """Initialize the client with app settings."""
        self.settings = get_settings()
        self._client = AsyncSurreal(self.settings.surrealdb_url)
        self._connected = False

    async def connect(self) -> None:
        """Open connection and authenticate to SurrealDB."""
        if self._connected:
            return

        await self._client.connect()
        await self._client.signin(
            {
                "username": self.settings.surrealdb_username,
                "password": self.settings.surrealdb_password,
            }
        )
        await self._client.use(
            self.settings.surrealdb_namespace,
            self.settings.surrealdb_database,
        )
        self._connected = True
        logger.info("Connected to SurrealDB at %s", self.settings.surrealdb_url)

    async def disconnect(self) -> None:
        """Close connection to SurrealDB."""
        if not self._connected:
            return

        await self._client.close()
        self._connected = False
        logger.info("Disconnected from SurrealDB")

    async def query(self, sql: str, variables: dict[str, Any] | None = None) -> Any:
        """Execute a parameterized query."""
        self._assert_connected()
        params = variables or {}
        return await self._client.query(sql, params)

    async def create_feed(
        self,
        feed_url: str,
        source_type: str,
        fetched_entries: int,
    ) -> str:
        """Create a feed tracking record and return its id."""
        payload = {
            "url": feed_url,
            "source_type": source_type,
            "fetched_entries": fetched_entries,
            "created_at": self._utc_now(),
        }
        result = await self.query(
            "CREATE feed CONTENT $data RETURN AFTER;",
            {"data": payload},
        )
        rows = self._extract_rows(result)
        if not rows:
            raise RuntimeError("Failed to create feed record.")
        return str(rows[0].get("id", ""))

    async def create_article(self, article: dict[str, Any]) -> str:
        """Create an article record and return its id."""
        result = await self.query(
            "CREATE content CONTENT $data RETURN AFTER;",
            {"data": article},
        )
        rows = self._extract_rows(result)
        if not rows:
            raise RuntimeError("Failed to create content record.")
        return str(rows[0].get("id", ""))

    async def create_content_chunks(self, chunks: list[dict[str, Any]]) -> None:
        """Persist content chunks used for semantic retrieval."""
        if not chunks:
            return
        for chunk in chunks:
            await self.query("CREATE content_chunk CONTENT $data;", {"data": chunk})

    async def list_content(self, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        """Return content records ordered by creation time."""
        sql = (
            "SELECT * FROM content "
            "ORDER BY created_at DESC "
            "LIMIT $limit START $offset;"
        )
        result = await self.query(sql, {"limit": limit, "offset": offset})
        return self._extract_rows(result)

    async def count_content(self) -> int:
        """Return the total number of content records."""
        result = await self.query("SELECT count() AS total FROM content GROUP ALL;")
        rows = self._extract_rows(result)
        if not rows:
            return 0
        return int(rows[0].get("total", 0))

    async def list_content_chunks(self, limit: int = 2000) -> list[dict[str, Any]]:
        """Return latest chunk records with embeddings."""
        sql = (
            "SELECT * FROM content_chunk "
            "ORDER BY created_at DESC "
            "LIMIT $limit;"
        )
        result = await self.query(sql, {"limit": limit})
        return self._extract_rows(result)

    async def get_content_map(self, content_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch content records by ids and return id->record map."""
        if not content_ids:
            return {}
        result = await self.query(
            "SELECT * FROM content WHERE id INSIDE $ids;",
            {"ids": content_ids},
        )
        rows = self._extract_rows(result)
        mapped: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = str(row.get("id", ""))
            if row_id:
                mapped[row_id] = row
        return mapped

    def _assert_connected(self) -> None:
        """Ensure the database client is ready for queries."""
        if not self._connected:
            raise RuntimeError("SurrealDB client is not connected.")

    def _extract_rows(self, query_result: Any) -> list[dict[str, Any]]:
        """Normalize SurrealDB query response shapes into row dictionaries."""
        if isinstance(query_result, list):
            if not query_result:
                return []
            first = query_result[0]
            if isinstance(first, dict) and "result" in first:
                result = first.get("result")
                if isinstance(result, list):
                    return [row for row in result if isinstance(row, dict)]
                if isinstance(result, dict):
                    return [result]
            if isinstance(first, dict):
                return [row for row in query_result if isinstance(row, dict)]
        if isinstance(query_result, dict):
            result = query_result.get("result")
            if isinstance(result, list):
                return [row for row in result if isinstance(row, dict)]
            if isinstance(result, dict):
                return [result]
        return []

    def _utc_now(self) -> str:
        """Return UTC timestamp in ISO-8601 format."""
        return datetime.now(tz=timezone.utc).isoformat()
