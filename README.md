# Graph Mind - Your Personal Learning Assistant

## Our Ideology: Taming the Information Overload

In our day-to-day lives, we consume a massive amount of data from countless resources. A decade ago, things were different—we'd search through books and Stack Overflow for answers. Thanks to content creators, YouTube, and AI, we now have abundant information at our fingertips. But with this privilege comes a new challenge: just like great power requires great responsibility, so does this wealth of knowledge.

We often save articles, videos, and posts to revisit "later" when we have time—but that time never comes. Enter **Graph Mind**, your intelligent learning companion. Share your interests, and let it send you summaries or interact with it to get exactly what you need, when you need it.

This is a Proof of Concept (POC) where we've ingested YouTube videos and LangChain's blog posts, focusing on learning about LangChain. In real-world scenarios, Graph Mind can expand to any topic or interest you have.

At its core is an **Agent Hive Mind** that connects to your interests. We're evolving this into an even better version where, after a few days, it automatically discovers and ingests content related to your interests—you won't need to manually share resources anymore.

## Quick Start

Get up and running in minutes:

```bash
uv sync
cp .env.example .env
# Edit .env with your API keys (e.g., TAVILY_API_KEY, OLLAMA_BASE_URL, etc.)
uv run --no-project uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open the web UI at `http://localhost:8080/` and start ingesting content!

## Features

- **Multi-Source Ingestion**: Collect from RSS feeds, YouTube channels/videos, Twitter threads, Hacker News, Medium stories, and generic URLs.
- **Intelligent Processing**: Automatic summarization (short, medium, long), topic/keyword extraction, and semantic embeddings using Ollama and Sentence Transformers.
- **Chunk-Level Retrieval**: Content is chunked for precise, context-aware search.
- **Interactive Q&A**: Ask questions grounded in your ingested knowledge, with optional web augmentation via Tavily.
- **Async-First Architecture**: Built with FastAPI for high performance and scalability.
- **Web UI**: Simple interface to add resources and ask questions.

## Supported Content Sources

- **RSS Feeds**: Blogs, news, dev.to, Medium, Substack.
- **YouTube**: Channel feeds or direct video URLs with transcript extraction.
- **Twitter/X**: Threads or handle feeds (best-effort public access). (Future Improvement)
- **Hacker News**: Top stories via official API. (Future Improvement)
- **Medium**: Feed resolution and story ingestion. (Future Improvement)
- **Generic URLs**: Metadata extraction from any web page. (Future Improvement)

Each ingested item is normalized into a unified format with titles, authors, content, summaries, embeddings, and metadata.

## How It Works

1. **Ingestion**: Share a URL or feed—Graph Mind collects and processes it asynchronously.
2. **Processing**: Content is cleaned, summarized using Ollama (Llama 3.2:3b), embedded with Sentence Transformers, and chunked for retrieval.
3. **Storage**: Persisted in SurrealDB with document-level and chunk-level embeddings.
4. **Q&A**: Ask questions—the agent retrieves relevant chunks, synthesizes answers, and optionally augments with Tavily web search.

## API Endpoints

- `GET /api/health`: Service health check.
- `POST /api/feeds`: Ingest RSS/Atom feeds.
- `POST /api/feeds/youtube`: YouTube channels/videos.
- `POST /api/feeds/twitter`: Twitter threads/handles.
- `POST /api/feeds/hackernews`: Hacker News top stories.
- `POST /api/feeds/url`: Generic URLs.
- `GET /api/content`: List processed content.
- `POST /api/ask`: Ask questions with semantic retrieval.

All responses follow a consistent envelope: `{"success": true, "data": {}, "error": null}`.

## Future Roadmap

- **Automatic Interest Discovery**: Graph Mind proactively finds and ingests content based on your patterns.
- **Personalized Learning Paths**: Concept maps, prerequisites, study plans, and quizzes.
- **Observability Dashboards**: Metrics on ingestion success, retrieval quality, and latency.
- **Multi-User Support**: Auth and per-user knowledge spaces.
- **Advanced Agents**: Hive mind evolution for collaborative learning.

## Local Runbook

```bash
# Install dependencies
uv sync

# Set up environment
cp .env.example .env
# Fill in your keys: TAVILY_API_KEY, OLLAMA_BASE_URL, SURREALDB_URL, etc.

# Start Ollama (for summarization)
ollama run llama3.2:3b

# Run the app
uv run --no-project uvicorn app.main:app --host 0.0.0.0 --port 8080

# Access:
# - UI: http://localhost:8080/
# - API Docs: http://localhost:8080/docs
```

Built with ❤️ for lifelong learners. Turn information overload into actionable knowledge!
