"""
Session Routes - Chat history and session management
"""
from fastapi import APIRouter, HTTPException
from loguru import logger

from ..models.model import (
    TitleGenerateRequest, TitleGenerateResponse,
    SessionCreateRequest, SessionResponse, SessionListResponse,
    MessageSaveRequest, MessageSaveResponse, MessagesListResponse,
    MessageResponse
)
from ..services.database import chat_db

router = APIRouter(prefix="/api/v1/sessions", tags=["Sessions"])


@router.post("", response_model=SessionResponse)
async def create_session(request: SessionCreateRequest):
    """Create a new chat session"""
    try:
        session = chat_db.create_session(
            title=request.title,
            session_id=request.session_id
        )
        return SessionResponse(**session, message_count=0)
    except Exception as e:
        logger.error(f"❌ Create session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=SessionListResponse)
async def list_sessions(limit: int = 50, offset: int = 0):
    """Get all sessions ordered by most recent"""
    try:
        sessions = chat_db.list_sessions(limit=limit, offset=offset)
        return SessionListResponse(
            sessions=[SessionResponse(**s) for s in sessions],
            total=len(sessions)
        )
    except Exception as e:
        logger.error(f"❌ List sessions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get a single session by ID"""
    session = chat_db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(**session)


@router.delete("/{session_id}", response_model=MessageResponse)
async def delete_session(session_id: str):
    """Delete a session and all its messages"""
    existed = chat_db.delete_session(session_id)
    if not existed:
        raise HTTPException(status_code=404, detail="Session not found")
    return MessageResponse(message=f"Session {session_id} deleted")


@router.patch("/{session_id}/title", response_model=MessageResponse)
async def update_title(session_id: str, request: TitleGenerateRequest):
    """Manually update session title"""
    updated = chat_db.update_session_title(session_id, request.message)
    if not updated:
        raise HTTPException(status_code=404, detail="Session not found")
    return MessageResponse(message="Title updated")


@router.get("/{session_id}/messages", response_model=MessagesListResponse)
async def get_messages(session_id: str, limit: int = 100, offset: int = 0):
    """Get all messages for a session"""
    if not chat_db.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    messages = chat_db.get_messages(session_id, limit=limit, offset=offset)
    return MessagesListResponse(
        session_id=session_id,
        messages=messages,
        total=len(messages)
    )


@router.post("/{session_id}/messages", response_model=MessageSaveResponse)
async def save_message(session_id: str, request: MessageSaveRequest):
    """Save a message to a session"""
    try:
        msg = chat_db.add_message(
            session_id=session_id,
            role=request.role,
            content=request.content,
            sql_query=request.sql_query,
            results=request.results
        )
        return MessageSaveResponse(**msg)
    except Exception as e:
        logger.error(f"❌ Save message error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-title", response_model=TitleGenerateResponse)
async def generate_title(request: TitleGenerateRequest):
    """Generate a concise session title from the user's first message"""
    try:
        from ..services.ai_service import azure_openai_service as ai

        response = ai.client.chat.completions.create(
            model=ai.deployment,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate concise 3-4 word titles for chat sessions. "
                        "Return ONLY the title, no punctuation, no quotes, nothing else."
                    )
                },
                {
                    "role": "user",
                    "content": f"Generate a title for this query: {request.message}"
                }
            ],
            temperature=0.3,
            max_tokens=20
        )

        title = response.choices[0].message.content.strip()
        logger.info(f"✓ Generated title: '{title}' for: '{request.message[:50]}'")
        return TitleGenerateResponse(title=title)

    except Exception as e:
        logger.error(f"❌ Title generation error: {e}")
        # Fallback — use first 5 words of message
        fallback = " ".join(request.message.split()[:5])
        return TitleGenerateResponse(title=fallback)