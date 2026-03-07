"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.agents.langchain_qa import LangChainQAAgent
from app.config import get_settings
from app.database import SurrealDBClient
from app.logging_config import setup_logging
from app.processors.embeddings import EmbeddingService
from app.processors.summarizer import OllamaSummarizer
from app.routes.content import router as content_router
from app.routes.feeds import router as feeds_router
from app.routes.health import router as health_router
from app.routes.qa import router as qa_router
from app.routes.ui import router as ui_router
from app.services.collection_service import CollectionService
from app.services.content_pipeline import ContentPipeline
from app.services.retrieval import SemanticRetriever

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Handle startup and shutdown lifecycle events."""
    settings = get_settings()
    setup_logging(settings.log_level)
    db_client = SurrealDBClient()
    collection_service = CollectionService()
    summarizer = OllamaSummarizer()
    embedding_service = EmbeddingService()
    retriever = SemanticRetriever(db=db_client, embeddings=embedding_service)
    qa_agent = LangChainQAAgent(retriever=retriever, settings=settings)
    pipeline = ContentPipeline(
        db=db_client,
        summarizer=summarizer,
        embedding_service=embedding_service,
    )

    app.state.db = db_client
    app.state.collection_service = collection_service
    app.state.pipeline = pipeline
    app.state.qa_agent = qa_agent
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)
    await db_client.connect()
    await pipeline.start(settings.queue_workers)
    yield
    await pipeline.stop()
    await db_client.disconnect()
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        lifespan=lifespan,
    )
    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(feeds_router, prefix=settings.api_prefix)
    app.include_router(content_router, prefix=settings.api_prefix)
    app.include_router(qa_router, prefix=settings.api_prefix)
    app.include_router(ui_router)
    static_dir = Path(__file__).parent / "web"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    return app


app = create_app()
