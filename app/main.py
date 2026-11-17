import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.schemas import PostingRequest, PostingResponse
from app.services.posting_service import PostingService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="Automated Multi-Platform Posting System",
    description="Post one message to Telegram, Discord, Bluesky, Mastodon and Slack.",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def ui():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/posting", response_model=PostingResponse)
async def create_posting(payload: PostingRequest):
    service = PostingService()
    return await service.post_to_all(payload.message, platforms=payload.platforms)


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
