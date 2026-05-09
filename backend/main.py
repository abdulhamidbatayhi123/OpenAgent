"""
MedMind - FastAPI Backend Server
Private AI Health & Wellness Advisor API
"""

import os
import base64
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from config import API_HOST, API_PORT, BASE_DIR, TELEGRAM_TOKEN
from pipeline.orchestrator import Orchestrator
from rag.chunker import chunk_medical_document


# --- Application Lifespan ----------------------------------------------------

orchestrator: Orchestrator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the pipeline on startup."""
    global orchestrator
    print("\n" + "=" * 60)
    print("  MedMind - Private Health & Wellness Advisor")
    print("  100% Local | No API Keys | Your Data Stays Here")
    print("=" * 60 + "\n")

    orchestrator = Orchestrator()

    # Start Telegram Bot if token is available — share the existing
    # orchestrator instead of building a second one.
    if TELEGRAM_TOKEN:
        try:
            from telegram_bot import run_bot
            bot_thread = threading.Thread(
                target=run_bot, args=(orchestrator,), daemon=True
            )
            bot_thread.start()
            print("[Telegram] Bot started in background thread.")
        except Exception as e:
            print(f"[Telegram] Failed to start bot: {e}")

    stats = orchestrator.get_stats()
    print(f"\n[Ready] Knowledge base: {stats['knowledge_base']['total']} chunks")
    print(f"[Ready] LLM: {stats['llm_model']}")
    print(f"[Ready] Reranker: {'OK' if stats['reranker_enabled'] else 'Disabled'}")
    print(f"\nMedMind is ready at http://localhost:{API_PORT}\n")

    yield

    print("\n[Shutdown] MedMind stopped.")


# --- FastAPI App --------------------------------------------------------------

app = FastAPI(
    title="MedMind API",
    description="Private AI Health & Wellness Advisor - 100% Local",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
frontend_dir = BASE_DIR.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


# --- Request / Response Models ------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    image_base64: Optional[str] = None


class SourceItem(BaseModel):
    label: str
    title: str
    source: str
    url: str
    section: str
    snippet: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    grounded: bool
    confidence: float
    urgency: str
    pipeline_time: float
    timings: Optional[dict] = None
    retrieval_confidence: Optional[float] = None
    steps_completed: int
    image_analysis: Optional[str] = None
    # Extra pipeline transparency for the "How I answered this" UI panel.
    # Populated by the orchestrator; safely Optional so callers that don't
    # set them don't break.
    analysis: Optional[dict] = None
    removed_citations: Optional[list[str]] = None
    # True when the query was handled by the conversational fast-path
    # (no RAG pipeline involved).
    is_conversational: Optional[bool] = None


class ProfileRequest(BaseModel):
    session_id: str
    profile: dict


class StatsResponse(BaseModel):
    knowledge_base: dict
    llm_model: str
    vision_model: str
    models: Optional[dict] = None
    reranker_enabled: bool
    active_session: str
    conversation_turns: int


# --- Chat Endpoint ------------------------------------------------------------

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a health question and receive a cited, verified answer."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        image_bytes = None
        if request.image_base64:
            try:
                image_bytes = base64.b64decode(request.image_base64)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid image data")

        result = orchestrator.process(
            user_message=request.message,
            session_id=request.session_id or "default",
            image_bytes=image_bytes,
        )

        return ChatResponse(
            answer=result["answer"],
            sources=[SourceItem(**s) for s in result.get("sources", [])],
            grounded=result.get("grounded", False),
            confidence=result.get("confidence", 0.0),
            urgency=result.get("urgency", "none"),
            pipeline_time=result.get("pipeline_time", 0.0),
            timings=result.get("timings"),
            retrieval_confidence=result.get("retrieval_confidence"),
            steps_completed=result.get("steps_completed", 0),
            image_analysis=result.get("image_analysis"),
            analysis=result.get("analysis"),
            removed_citations=result.get("removed_citations"),
            is_conversational=result.get("is_conversational"),
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Streaming Chat Endpoint -------------------------------------------------

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """SSE streaming endpoint — tokens arrive as they're generated."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    image_bytes = None
    if request.image_base64:
        try:
            image_bytes = base64.b64decode(request.image_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image data")

    def event_generator():
        try:
            yield from orchestrator.process_stream(
                user_message=request.message,
                session_id=request.session_id or "default",
                image_bytes=image_bytes,
            )
        except Exception as e:
            import json
            print(f"[Stream Error] {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- Document Upload ---------------------------------------------------------

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a PDF or text document to add to the knowledge base."""
    allowed_types = [".pdf", ".txt", ".md", ".docx"]
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {allowed_types}",
        )

    try:
        content = await file.read()
        text = _extract_text(content, ext)

        if not text or len(text.strip()) < 50:
            raise HTTPException(status_code=400, detail="Document is empty or too short")

        chunks = chunk_medical_document(text, title=file.filename)
        if not chunks:
            raise HTTPException(status_code=400, detail="Could not extract meaningful content")

        added = orchestrator.vector_db.add_user_document(chunks, file.filename)

        return {
            "status": "success",
            "filename": file.filename,
            "chunks_added": added,
            "total_characters": len(text),
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Upload Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _extract_text(content: bytes, ext: str) -> str:
    """Extract text from uploaded file based on extension."""
    if ext == ".pdf":
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)

    elif ext == ".docx":
        from docx import Document
        import io
        doc = Document(io.BytesIO(content))
        return "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])

    else:  # .txt, .md
        return content.decode("utf-8", errors="ignore")


# --- Health Profile -----------------------------------------------------------

@app.post("/profile")
async def save_profile(request: ProfileRequest):
    """Save or update the user's health profile."""
    orchestrator.save_profile(request.session_id, request.profile)
    return {"status": "saved", "session_id": request.session_id}


@app.get("/profile/{session_id}")
async def get_profile(session_id: str):
    """Get the user's health profile."""
    profile = orchestrator.get_profile(session_id)
    return {"session_id": session_id, "profile": profile}


# --- History ------------------------------------------------------------------

@app.delete("/history/{session_id}")
async def clear_history(session_id: str):
    """Clear conversation history for a session."""
    orchestrator.clear_history(session_id)
    return {"status": "cleared", "session_id": session_id}


# --- System ------------------------------------------------------------------

@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get system statistics."""
    return orchestrator.get_stats()


@app.get("/health")
async def health():
    """Health check endpoint."""
    db_counts = orchestrator.vector_db.count() if orchestrator else {}
    return {
        "status": "healthy",
        "knowledge_base": db_counts,
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "MedMind API",
        "version": "1.0.0",
        "description": "Private AI Health & Wellness Advisor",
        "docs": "/docs",
    }


# --- Run ----------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)
