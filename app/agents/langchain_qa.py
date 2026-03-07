"""LangChain agent for question answering over ingested content."""

import json
import logging
import os
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from app.config import Settings
from app.schemas import AskData, SourceItem
from app.services.retrieval import SemanticRetriever
from app.services.tavily import TavilyService

logger = logging.getLogger(__name__)


class LangChainQAAgent:
    """Tool-using LangChain agent that answers questions with retrieved sources."""

    def __init__(self, retriever: SemanticRetriever, settings: Settings) -> None:
        """Initialize model, tool function, and agent graph."""
        self.retriever = retriever
        self.settings = settings
        self.tavily = TavilyService(settings=settings)
        self._configure_langsmith()
        self._llm = ChatOllama(
            base_url=self.settings.ollama_base_url,
            model=self.settings.ollama_model,
            temperature=0.1,
        )
        self._agent = create_agent(
            model=self._llm,
            tools=[self._semantic_search_tool, self._tavily_search_tool],
            system_prompt=(
                "You are a precise learning assistant. Use semantic_search first. "
                "Use tavily_search only when local sources are insufficient or stale."
            ),
        )

    async def ask(self, question: str, top_k: int) -> AskData:
        """Answer a user question using retrieval-augmented agent reasoning."""
        sources = await self.retriever.search(question, top_k=top_k)
        if not sources:
            return AskData(
                question=question,
                answer="I could not find relevant processed content to answer this question yet.",
                top_k=top_k,
                langsmith_project_id=self.settings.langsmith_project_id,
                sources=[],
            )

        prompt = (
            f"Question: {question}\n"
            f"When using semantic_search, use top_k={top_k}. "
            "Give a concise answer and cite source titles."
        )
        runnable_config: dict[str, Any] = {
            "tags": [f"langsmith_project_id:{self.settings.langsmith_project_id}"],
            "metadata": {
                "langsmith_project_id": self.settings.langsmith_project_id,
                "top_k": top_k,
            },
        }
        result = await self._agent.ainvoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config=runnable_config,
        )
        answer = self._extract_answer(result)
        if self._looks_like_tool_call(answer) or self._is_low_confidence_answer(answer, sources):
            answer = await self._synthesize_from_sources(question, sources)
        return AskData(
            question=question,
            answer=answer,
            top_k=top_k,
            langsmith_project_id=self.settings.langsmith_project_id,
            sources=sources,
        )

    async def _semantic_search_tool(self, query: str, top_k: int = 4) -> str:
        """Tool implementation returning retrieval results as JSON text."""
        results: list[SourceItem] = await self.retriever.search(query, top_k=top_k)
        payload = [item.model_dump() for item in results]
        return json.dumps(payload, ensure_ascii=True)

    async def _tavily_search_tool(self, query: str, max_results: int = 5) -> str:
        """Tool implementation for Tavily web search."""
        return await self.tavily.search(query=query, max_results=max_results)

    def _extract_answer(self, result: dict[str, Any]) -> str:
        """Extract the final assistant message from LangChain agent output."""
        messages = result.get("messages", [])
        if not isinstance(messages, list):
            return "No answer generated."

        for message in reversed(messages):
            if isinstance(message, AIMessage):
                return self._message_content_to_text(message)
            if isinstance(message, BaseMessage) and getattr(message, "type", "") == "ai":
                return self._message_content_to_text(message)
            if isinstance(message, dict) and message.get("role") == "assistant":
                content = message.get("content", "")
                return str(content).strip() or "No answer generated."
        return "No answer generated."

    def _looks_like_tool_call(self, text: str) -> bool:
        """Detect whether model output is a serialized tool-call payload."""
        if not text:
            return True
        lowered = text.lower()
        return (
            '"name"' in lowered
            and '"semantic_search"' in lowered
            and '"parameters"' in lowered
        )

    def _is_low_confidence_answer(self, answer: str, sources: list[SourceItem]) -> bool:
        """Detect weak fallback answers when relevant local sources exist."""
        if not answer:
            return True
        lowered = answer.lower()
        weak_phrases = [
            "couldn't find",
            "sources are insufficient",
            "no information",
            "not enough information",
        ]
        has_weak_signal = any(phrase in lowered for phrase in weak_phrases)
        best_score = max((source.score for source in sources), default=0.0)
        return has_weak_signal and best_score >= 0.65

    async def _synthesize_from_sources(
        self, question: str, sources: list[SourceItem]
    ) -> str:
        """Create a final grounded answer from retrieved source summaries."""
        context_lines: list[str] = []
        for idx, source in enumerate(sources, start=1):
            context_lines.append(
                f"[{idx}] Title: {source.title}\n"
                f"Link: {source.link}\n"
                f"Excerpt: {source.excerpt}\n"
                f"Summary: {source.summary}\n"
                f"Topics: {', '.join(source.topics) if source.topics else 'n/a'}\n"
                f"Keywords: {', '.join(source.keywords) if source.keywords else 'n/a'}\n"
            )
        context_block = "\n".join(context_lines)
        messages = [
            SystemMessage(
                content=(
                    "You are a factual learning assistant. Use only the supplied sources. "
                    "If at least one source is relevant, produce a direct answer first, then "
                    "briefly cite sources. Only say insufficient when sources truly do not cover "
                    "the question."
                )
            ),
            HumanMessage(
                content=(
                    f"Question: {question}\n\n"
                    f"Sources:\n{context_block}\n\n"
                    "Return a concise answer and cite sources by [number]."
                )
            ),
        ]
        response = await self._llm.ainvoke(messages)
        content = response.content
        if isinstance(content, str):
            return content.strip() or "No answer generated."
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]).strip())
                else:
                    parts.append(str(item).strip())
            text = " ".join(part for part in parts if part)
            return text or "No answer generated."
        return str(content).strip() or "No answer generated."

    def _message_content_to_text(self, message: BaseMessage) -> str:
        """Convert LangChain message content variants into plain text."""
        content = message.content
        if isinstance(content, str):
            return content.strip() or "No answer generated."
        if isinstance(content, list):
            pieces: list[str] = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    pieces.append(str(item["text"]))
                else:
                    pieces.append(str(item))
            text = " ".join(piece.strip() for piece in pieces if piece.strip())
            return text or "No answer generated."
        return str(content).strip() or "No answer generated."

    def _configure_langsmith(self) -> None:
        """Configure LangSmith tracing environment values."""
        os.environ["LANGSMITH_TRACING"] = str(self.settings.langsmith_tracing).lower()
        os.environ["LANGCHAIN_TRACING_V2"] = str(self.settings.langsmith_tracing).lower()
        os.environ["LANGSMITH_ENDPOINT"] = self.settings.langsmith_endpoint
        os.environ["LANGSMITH_PROJECT"] = self.settings.langsmith_project
        os.environ["LANGCHAIN_PROJECT"] = self.settings.langsmith_project
        if self.settings.langsmith_api_key:
            os.environ["LANGSMITH_API_KEY"] = self.settings.langsmith_api_key
        logger.info("LangSmith project configured: %s", self.settings.langsmith_project)
