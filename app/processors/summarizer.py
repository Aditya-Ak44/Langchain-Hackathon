"""Async summarization and topic extraction via Ollama."""

import asyncio
import json
import logging

import httpx

from app.config import get_settings
from app.schemas import SummarySet

logger = logging.getLogger(__name__)


class OllamaSummarizer:
    """Generate summaries and topic metadata through Ollama."""

    def __init__(self) -> None:
        """Initialize summarizer with HTTP endpoint configuration."""
        settings = get_settings()
        self._model = settings.ollama_model
        self._endpoint = (
            f"{settings.ollama_base_url.rstrip('/')}{settings.ollama_generate_path}"
        )
        self._timeout = httpx.Timeout(45.0, connect=5.0)

    async def generate_summaries(self, text: str) -> SummarySet:
        """Generate short, medium, and long summaries for a text block."""
        short_prompt = self._summary_prompt(text, words=40)
        medium_prompt = self._summary_prompt(text, words=100)
        long_prompt = self._summary_prompt(text, words=180)

        short, medium, long = await self._gather_generations(
            [short_prompt, medium_prompt, long_prompt]
        )
        return SummarySet(short=short, medium=medium, long=long)

    async def extract_topics_keywords(self, text: str) -> tuple[list[str], list[str]]:
        """Extract topics and keywords from text as two short lists."""
        prompt = (
            "Analyze the text and return valid JSON with keys "
            "'topics' and 'keywords'. Each key must be an array of up to 6 short strings.\n\n"
            f"Text:\n{text}"
        )
        raw = await self._generate(prompt)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Failed to parse topic JSON from Ollama output.")
            return [], []

        topics = parsed.get("topics", [])
        keywords = parsed.get("keywords", [])
        if not isinstance(topics, list) or not isinstance(keywords, list):
            return [], []
        topic_values = [str(item).strip() for item in topics if str(item).strip()][:6]
        keyword_values = [str(item).strip() for item in keywords if str(item).strip()][:6]
        return topic_values, keyword_values

    async def _gather_generations(self, prompts: list[str]) -> tuple[str, str, str]:
        """Run multiple generate calls and return ordered text outputs."""
        outputs = await asyncio.gather(*(self._generate(prompt) for prompt in prompts))
        return outputs[0], outputs[1], outputs[2]

    def _summary_prompt(self, text: str, words: int) -> str:
        """Build a deterministic summary prompt."""
        return (
            f"Summarize the text in <= {words} words. "
            "Keep factual details and avoid filler.\n\n"
            f"Text:\n{text}"
        )

    async def _generate(self, prompt: str) -> str:
        """Call Ollama `/api/generate` and return plain response text."""
        payload = {"model": self._model, "prompt": prompt, "stream": False}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._endpoint, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception("Ollama generation failed: %s", exc)
            raise RuntimeError("Failed to generate text with Ollama.") from exc

        body = response.json()
        output = body.get("response")
        if not isinstance(output, str) or not output.strip():
            raise RuntimeError("Ollama returned an invalid text response.")
        return output.strip()
