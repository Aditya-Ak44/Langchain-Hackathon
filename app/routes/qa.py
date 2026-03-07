"""Question-answering endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.agents.langchain_qa import LangChainQAAgent
from app.schemas import ApiResponse, AskData, AskRequest

router = APIRouter(prefix="/ask", tags=["qa"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ApiResponse[AskData])
async def ask_question(payload: AskRequest, request: Request) -> ApiResponse[AskData]:
    """Answer a question using the LangChain retrieval agent."""
    agent: LangChainQAAgent = request.app.state.qa_agent
    try:
        answer = await agent.ask(payload.question, top_k=payload.top_k)
    except Exception as exc:
        logger.exception("Agent answer generation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to generate answer.") from exc

    return ApiResponse[AskData](success=True, data=answer, error=None)
