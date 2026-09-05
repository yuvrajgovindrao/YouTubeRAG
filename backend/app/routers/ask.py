import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import CollectionModel, VideoModel
from app.services.retrieval import search_collection_chunks, generate_rag_answer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/collections", tags=["Ask / RAG"])


class AskRequest(BaseModel):
    question: str = Field(..., min_length=2, description="Natural language question to ask the indexed videos")


class SourceItem(BaseModel):
    video_id: str
    title: str
    thumbnail: str
    start_time: float
    end_time: Optional[float] = None
    excerpt: str
    similarity: float


class AskResponse(BaseModel):
    answer: str
    sources: List[SourceItem]


@router.post("/{collection_id}/ask", response_model=AskResponse)
async def ask_question(
    collection_id: uuid.UUID,
    payload: AskRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Asks a natural language question against the user's collection.
    1. Embeds the question.
    2. Performs vector similarity search scoped to this collection.
    3. Groups results by video_id, selecting the best chunk per video.
    4. Synthesizes an answer using the configured Gemini chat model.
    5. Returns the answer and ranked source cards.
    """
    session_id: uuid.UUID = request.state.session_id

    # Verify collection ownership
    col_stmt = select(CollectionModel).where(
        CollectionModel.collection_id == collection_id,
        CollectionModel.session_id == session_id
    )
    col_res = await db.execute(col_stmt)
    if not col_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found or does not belong to the current session."
        )

    # Check if there are any ready videos in this collection
    vid_stmt = select(VideoModel).where(
        VideoModel.collection_id == collection_id,
        VideoModel.status == "ready"
    )
    ready_videos = (await db.execute(vid_stmt)).scalars().all()
    if not ready_videos:
        return AskResponse(
            answer="No videos in this collection are ready yet. Please wait for ingestion to complete before asking questions.",
            sources=[]
        )

    # Retrieve relevant sources
    sources = await search_collection_chunks(
        db=db,
        collection_id=collection_id,
        query_text=payload.question,
        limit_sources=settings.MAX_SOURCES_RETURNED
    )

    if not sources:
        return AskResponse(
            answer="I could not find any relevant information in the transcripts to answer your question.",
            sources=[]
        )

    # Generate synthesized RAG answer
    answer = await generate_rag_answer(payload.question, sources)

    return AskResponse(
        answer=answer,
        sources=[SourceItem(**s) for s in sources]
    )
