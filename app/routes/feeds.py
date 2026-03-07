"""Multi-source ingestion endpoints."""

import logging
from typing import Awaitable

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.database import SurrealDBClient
from app.schemas import (
    ApiResponse,
    FeedCreateData,
    FeedCreateRequest,
    HackerNewsFeedRequest,
    RawContentItem,
    TwitterFeedRequest,
    UrlFeedRequest,
    YouTubeFeedRequest,
)
from app.services.collection_service import CollectionService
from app.services.content_pipeline import ContentPipeline

router = APIRouter(prefix="/feeds", tags=["feeds"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ApiResponse[FeedCreateData])
async def add_feed(payload: FeedCreateRequest, request: Request) -> ApiResponse[FeedCreateData]:
    """Collect RSS/Atom feed entries and queue processing."""
    service: CollectionService = request.app.state.collection_service
    source_type, resolved_url, entries = await _collect_with_handling(
        source_label="rss",
        collect_coro=service.from_rss(url=str(payload.url), limit=payload.limit),
    )
    data = await _queue_feed(request, source_type, resolved_url, entries)
    return ApiResponse[FeedCreateData](success=True, data=data, error=None)


@router.post("/youtube", response_model=ApiResponse[FeedCreateData])
async def add_youtube_feed(
    payload: YouTubeFeedRequest,
    request: Request,
) -> ApiResponse[FeedCreateData]:
    """Collect YouTube channel videos and queue processing."""
    service: CollectionService = request.app.state.collection_service
    source_type, resolved_url, entries = await _collect_with_handling(
        source_label="youtube",
        collect_coro=service.from_youtube(
            channel_url=str(payload.channel_url) if payload.channel_url else None,
            channel_id=payload.channel_id,
            username=payload.username,
            limit=payload.limit,
        ),
    )
    data = await _queue_feed(request, source_type, resolved_url, entries)
    return ApiResponse[FeedCreateData](success=True, data=data, error=None)


@router.post("/twitter", response_model=ApiResponse[FeedCreateData])
async def add_twitter_feed(
    payload: TwitterFeedRequest,
    request: Request,
) -> ApiResponse[FeedCreateData]:
    """Collect Twitter/X thread or handle entries and queue processing."""
    service: CollectionService = request.app.state.collection_service
    source_type, resolved_url, entries = await _collect_with_handling(
        source_label="twitter",
        collect_coro=service.from_twitter(
            twitter_handle=payload.twitter_handle,
            thread_url=str(payload.thread_url) if payload.thread_url else None,
            limit=payload.limit,
        ),
    )
    data = await _queue_feed(request, source_type, resolved_url, entries)
    return ApiResponse[FeedCreateData](success=True, data=data, error=None)


@router.post("/hackernews", response_model=ApiResponse[FeedCreateData])
async def add_hackernews_feed(
    payload: HackerNewsFeedRequest,
    request: Request,
) -> ApiResponse[FeedCreateData]:
    """Collect Hacker News top stories and queue processing."""
    service: CollectionService = request.app.state.collection_service
    source_type, resolved_url, entries = await _collect_with_handling(
        source_label="hackernews",
        collect_coro=service.from_hackernews(limit=payload.limit),
    )
    data = await _queue_feed(request, source_type, resolved_url, entries)
    return ApiResponse[FeedCreateData](success=True, data=data, error=None)


@router.post("/url", response_model=ApiResponse[FeedCreateData])
async def add_generic_url(
    payload: UrlFeedRequest,
    request: Request,
) -> ApiResponse[FeedCreateData]:
    """Collect content from any URL and queue processing."""
    service: CollectionService = request.app.state.collection_service
    source_type, resolved_url, entries = await _collect_with_handling(
        source_label="url",
        collect_coro=service.from_url(any_url=str(payload.any_url), limit=payload.limit),
    )
    data = await _queue_feed(request, source_type, resolved_url, entries)
    return ApiResponse[FeedCreateData](success=True, data=data, error=None)


async def _collect_with_handling(
    source_label: str,
    collect_coro: Awaitable[tuple[str, str, list[RawContentItem]]],
) -> tuple[str, str, list[RawContentItem]]:
    """Run source-specific collection with normalized API errors."""
    try:
        source_type, resolved_url, entries = await collect_coro
    except httpx.HTTPError as exc:
        logger.exception("%s fetch failed: %s", source_label, exc)
        raise HTTPException(
            status_code=400,
            detail=f"Could not fetch {source_label} source.",
        ) from exc
    except ValueError as exc:
        logger.exception("%s parse failed: %s", source_label, exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected %s ingestion error: %s", source_label, exc)
        raise HTTPException(status_code=500, detail=f"{source_label} ingestion failed.") from exc

    if not entries:
        raise HTTPException(status_code=400, detail=f"{source_label} source contains no entries.")
    return source_type, resolved_url, entries


async def _queue_feed(
    request: Request,
    source_type: str,
    resolved_url: str,
    entries: list[RawContentItem],
) -> FeedCreateData:
    """Persist feed metadata and enqueue entries for processing."""
    db: SurrealDBClient = request.app.state.db
    pipeline: ContentPipeline = request.app.state.pipeline
    try:
        feed_id = await db.create_feed(
            feed_url=resolved_url,
            source_type=source_type,
            fetched_entries=len(entries),
        )
        queued_count = await pipeline.enqueue_articles(feed_id, resolved_url, entries)
    except Exception as exc:
        logger.exception("Failed to queue entries for %s: %s", source_type, exc)
        raise HTTPException(status_code=500, detail="Failed to queue entries.") from exc

    return FeedCreateData(
        feed_id=feed_id,
        feed_url=resolved_url,
        source_type=source_type,
        fetched_entries=len(entries),
        queued_entries=queued_count,
        status="processing_started",
    )
