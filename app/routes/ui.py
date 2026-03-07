"""Frontend page routes."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["ui"])


@router.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """Serve the learning assistant UI."""
    file_path = Path(__file__).resolve().parents[1] / "web" / "index.html"
    return FileResponse(file_path)
