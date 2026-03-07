"""Content retrieval endpoints."""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.database import SurrealDBClient
from app.schemas import ApiResponse, ContentListData, ProcessedArticle, SummarySet

router = APIRouter(prefix="/content", tags=["content"])
logger = logging.getLogger(__name__)


@router.get("", response_model=ApiResponse[ContentListData])
async def list_content(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ApiResponse[ContentListData]:
    """Return processed content records ready for dashboard rendering."""
    db: SurrealDBClient = request.app.state.db
    try:
        rows = await db.list_content(limit=limit, offset=offset)
        total = await db.count_content()
    except Exception as exc:
        logger.exception("Failed to fetch content: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch content.") from exc

    items = [_to_processed_article(row) for row in rows]
    data = ContentListData(items=items, total=total, limit=limit, offset=offset)
    return ApiResponse[ContentListData](success=True, data=data, error=None)


def _to_processed_article(row: dict[str, Any]) -> ProcessedArticle:
    """Map database record into API response model."""
    created_at = row.get("created_at", "")
    parsed_dt = _parse_timestamp(created_at)
    return ProcessedArticle(
        id=str(row.get("id", "")),
        feed_id=str(row.get("feed_id", "")),
        feed_url=str(row.get("feed_url", "")),
        source_type=str(row.get("source_type", "unknown")),
        source_name=str(row.get("source_name", "unknown")),
        title=str(row.get("title", "")),
        link=str(row.get("link", "")),
        published_at=str(row.get("published_at", "")),
        author=row.get("author"),
        metadata=row.get("metadata", {}) if isinstance(row.get("metadata", {}), dict) else {},
        topics=[str(item) for item in row.get("topics", [])],
        keywords=[str(item) for item in row.get("keywords", [])],
        summaries=SummarySet(
            short=str(row.get("summary_short", "")),
            medium=str(row.get("summary_medium", "")),
            long=str(row.get("summary_long", "")),
        ),
        embedding_dimensions=int(row.get("embedding_dimensions", 0)),
        processing_status=str(row.get("processing_status", "unknown")),
        error=row.get("error"),
        created_at=parsed_dt,
    )


def _parse_timestamp(value: str) -> datetime:
    """Safely parse ISO datetime values and fallback to UTC now."""
    if not value:
        return datetime.now(tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(tz=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
