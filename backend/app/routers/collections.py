import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import CollectionModel, VideoModel, JobModel
from app.services.url_parser import parse_and_cap_urls
from app.services.ingestion import process_video_ingestion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/collections", tags=["Collections"])


# Schemas
class CollectionResponse(BaseModel):
    collection_id: uuid.UUID
    session_id: uuid.UUID
    created_at: str


class VideoIngestRequest(BaseModel):
    links: str = Field(..., description="Raw text containing one or more YouTube video or playlist links")


class VideoItemStatus(BaseModel):
    video_id: str
    title: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    status: str
    progress_percent: int = 0
    error_message: Optional[str] = None


class IngestionStatusResponse(BaseModel):
    collection_id: uuid.UUID
    total_videos: int
    ready_count: int
    processing_count: int
    failed_count: int
    pending_count: int
    is_complete: bool
    videos: List[VideoItemStatus]


class IngestSubmissionResponse(BaseModel):
    collection_id: uuid.UUID
    accepted_video_ids: List[str]
    job_ids: List[uuid.UUID]
    truncated: bool
    dropped_count: int
    total_detected: int
    message: str


@router.post("", response_model=CollectionResponse)
async def get_or_create_collection(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new collection for the current session or returns the active existing one.
    """
    session_id: uuid.UUID = request.state.session_id

    stmt = (
        select(CollectionModel)
        .where(CollectionModel.session_id == session_id)
        .order_by(CollectionModel.created_at.desc())
    )
    result = await db.execute(stmt)
    collection = result.scalars().first()

    if not collection:
        collection = CollectionModel(
            collection_id=uuid.uuid4(),
            session_id=session_id
        )
        db.add(collection)
        await db.commit()
        await db.refresh(collection)

    return CollectionResponse(
        collection_id=collection.collection_id,
        session_id=collection.session_id,
        created_at=collection.created_at.isoformat()
    )


@router.post("/{collection_id}/videos", response_model=IngestSubmissionResponse)
async def submit_videos(
    collection_id: uuid.UUID,
    payload: VideoIngestRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Submits raw text of links/playlists for ingestion.
    Enforces the configurable video cap, registers jobs, and dispatches background ingestion.
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

    # Check currently existing videos
    vid_stmt = select(VideoModel.video_id).where(VideoModel.collection_id == collection_id)
    existing_vids = set((await db.execute(vid_stmt)).scalars().all())

    # Calculate remaining slots
    max_cap = settings.MAX_VIDEOS_PER_COLLECTION
    remaining_slots = max(0, max_cap - len(existing_vids))

    if max_cap > 0 and remaining_slots <= 0:
        return IngestSubmissionResponse(
            collection_id=collection_id,
            accepted_video_ids=[],
            job_ids=[],
            truncated=True,
            dropped_count=1,
            total_detected=1,
            message=f"Collection has reached the maximum allowed limit of {max_cap} videos."
        )

    # Parse and cap URLs
    parsed = parse_and_cap_urls(payload.links, max_videos=remaining_slots)
    accepted_vids = [v for v in parsed["video_ids"] if v not in existing_vids]

    # If any was already in collection or dropped
    dropped_count = parsed["dropped_count"] + (len(parsed["video_ids"]) - len(accepted_vids))
    truncated = parsed["truncated"] or dropped_count > 0

    job_ids = []
    for vid in accepted_vids:
        # Create video row
        video_record = VideoModel(
            video_id=vid,
            collection_id=collection_id,
            status="pending"
        )
        db.add(video_record)

        # Create job row
        job_id = uuid.uuid4()
        job_record = JobModel(
            job_id=job_id,
            collection_id=collection_id,
            video_id=vid,
            status="queued"
        )
        db.add(job_record)
        job_ids.append(job_id)

        # Queue background task
        background_tasks.add_task(process_video_ingestion, collection_id, vid, job_id)

    await db.commit()

    msg = f"Accepted {len(accepted_vids)} video(s) for ingestion."
    if truncated:
        msg += f" Note: {dropped_count} video(s) were truncated to respect the maximum cap of {max_cap}."

    return IngestSubmissionResponse(
        collection_id=collection_id,
        accepted_video_ids=accepted_vids,
        job_ids=job_ids,
        truncated=truncated,
        dropped_count=dropped_count,
        total_detected=parsed["total_detected"],
        message=msg
    )


@router.get("/{collection_id}/status", response_model=IngestionStatusResponse)
async def get_collection_status(
    collection_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns real-time ingestion status and progress for all videos in a collection.
    """
    session_id: uuid.UUID = request.state.session_id

    # Verify collection ownership
    col_stmt = select(CollectionModel).where(
        CollectionModel.collection_id == collection_id,
        CollectionModel.session_id == session_id
    )
    if not (await db.execute(col_stmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found."
        )

    vid_stmt = (
        select(VideoModel)
        .where(VideoModel.collection_id == collection_id)
        .order_by(VideoModel.added_at.asc())
    )
    videos = (await db.execute(vid_stmt)).scalars().all()

    ready = 0
    processing = 0
    failed = 0
    pending = 0

    items: List[VideoItemStatus] = []
    for v in videos:
        if v.status == "ready":
            ready += 1
        elif v.status == "processing":
            processing += 1
        elif v.status == "failed":
            failed += 1
        else:
            pending += 1

        prog = getattr(v, "progress_percent", 0) or 0
        if v.status == "ready":
            prog = 100

        items.append(
            VideoItemStatus(
                video_id=v.video_id,
                title=v.title,
                thumbnail_url=v.thumbnail_url,
                duration_seconds=v.duration_seconds,
                status=v.status,
                progress_percent=prog,
                error_message=v.error_message
            )
        )

    is_complete = len(videos) > 0 and (processing == 0 and pending == 0)

    return IngestionStatusResponse(
        collection_id=collection_id,
        total_videos=len(videos),
        ready_count=ready,
        processing_count=processing,
        failed_count=failed,
        pending_count=pending,
        is_complete=is_complete,
        videos=items
    )


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Manually clears a collection and all associated videos, chunks, and jobs.
    """
    session_id: uuid.UUID = request.state.session_id

    stmt = select(CollectionModel).where(
        CollectionModel.collection_id == collection_id,
        CollectionModel.session_id == session_id
    )
    col = (await db.execute(stmt)).scalar_one_or_none()
    if not col:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found."
        )

    await db.delete(col)
    await db.commit()

    return {"status": "success", "message": "Collection and associated data deleted successfully."}
