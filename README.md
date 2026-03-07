# Content Aggregator API

Async-first FastAPI scaffold for a modern content aggregator.
Now extended as a learning assistant: ingest resources, chunk/embed content, and ask questions.

## Quick start

```bash
uv sync
cp .env.example .env
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## Health endpoint

`GET /api/health`

## Pipeline endpoints

- `POST /api/feeds`
- `POST /api/feeds/youtube`
- `POST /api/feeds/twitter`
- `POST /api/feeds/hackernews`
- `POST /api/feeds/url`
- `GET /api/content`
- `POST /api/ask`

## Web UI

- Open `http://localhost:8080/`
- Add resources from RSS, YouTube, Twitter/X, Hacker News, or generic URLs
- Ask learning questions from the same interface

## Multi-source collection

Supported source types:

- `rss` (blogs/news/dev.to/medium/substack feed URLs)
- `video` (YouTube channel feeds)
- `twitter_thread` (X/Twitter thread URLs or handle feed fallback)
- `news` (Hacker News top stories)
- `medium_story` (Medium feed sources)
- `url` (generic web pages with metadata extraction)

Unified stored item shape includes:

- `source_type`, `source_name`
- `title`, `link`, `author`, `published_at`
- `raw_content`, summaries, topics, keywords
- `embedding` + `embedding_dimensions`
- chunk embeddings in `content_chunk` records for better retrieval
- `metadata` (source-specific fields like channel/story/engagement values)

YouTube notes:

- Channel source: videos come from the YouTube feed and are then enriched with transcripts.
- Direct video URL: collector pulls one video and attempts transcript extraction.
- Embeddings use transcript text when available, otherwise fallback to description/title text.

## Agent + search tools

- Local semantic tool: chunk-level retrieval from your stored content
- Optional web tool: Tavily search (`TAVILY_API_KEY`) for fresh external context
# Langchain-Hackathon
