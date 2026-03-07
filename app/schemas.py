"""Shared API and domain schemas."""

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, HttpUrl

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response envelope."""

    success: bool
    data: T | None = None
    error: str | None = None


class HealthData(BaseModel):
    """Data payload for service health checks."""

    status: str = Field(default="ok")
    app_name: str
    environment: str
    timestamp: datetime

    @classmethod
    def build(cls, app_name: str, environment: str) -> "HealthData":
        """Create a health payload with current UTC time."""
        return cls(
            app_name=app_name,
            environment=environment,
            timestamp=datetime.now(tz=timezone.utc),
        )


class FeedCreateRequest(BaseModel):
    """Request payload for adding a new RSS feed."""

    url: HttpUrl
    limit: int = Field(default=20, ge=1, le=50)


class FeedCreateData(BaseModel):
    """Response payload for feed ingestion trigger."""

    feed_id: str
    feed_url: str
    source_type: str
    fetched_entries: int
    queued_entries: int
    status: str


class RawContentItem(BaseModel):
    """Unified raw content model before processing."""

    source_type: str
    source_name: str
    title: str
    link: str
    description: str
    content: str
    published_at: str
    author: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SummarySet(BaseModel):
    """Multiple summary sizes for frontend display."""

    short: str
    medium: str
    long: str


class ProcessedArticle(BaseModel):
    """Processed content model returned to the dashboard."""

    id: str
    feed_id: str
    feed_url: str
    source_type: str
    source_name: str
    title: str
    link: str
    published_at: str
    author: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    topics: list[str]
    keywords: list[str]
    summaries: SummarySet
    embedding_dimensions: int
    processing_status: str
    error: str | None = None
    created_at: datetime


class ContentListData(BaseModel):
    """Content listing payload for dashboard consumption."""

    items: list[ProcessedArticle]
    total: int
    limit: int
    offset: int


class AskRequest(BaseModel):
    """Request payload for agent-powered question answering."""

    question: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=10)


class YouTubeFeedRequest(BaseModel):
    """Request payload for YouTube feed ingestion."""

    channel_url: HttpUrl | None = None
    channel_id: str | None = None
    username: str | None = None
    limit: int = Field(default=20, ge=1, le=50)


class TwitterFeedRequest(BaseModel):
    """Request payload for Twitter/X ingestion."""

    twitter_handle: str | None = None
    thread_url: HttpUrl | None = None
    limit: int = Field(default=20, ge=1, le=50)


class HackerNewsFeedRequest(BaseModel):
    """Request payload for Hacker News ingestion."""

    limit: int = Field(default=20, ge=1, le=100)


class UrlFeedRequest(BaseModel):
    """Request payload for generic URL ingestion."""

    any_url: HttpUrl
    limit: int = Field(default=20, ge=1, le=50)


class SourceItem(BaseModel):
    """Retrieved source metadata returned with an answer."""

    id: str
    title: str
    link: str
    score: float
    excerpt: str
    summary: str
    topics: list[str]
    keywords: list[str]


class AskData(BaseModel):
    """Agent answer payload with retrieval context."""

    question: str
    answer: str
    top_k: int
    langsmith_project_id: str
    sources: list[SourceItem]
