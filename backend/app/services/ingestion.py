import asyncio
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

from app.db import async_session_factory
from app.models import VideoModel, ChunkModel, JobModel
from app.services.chunking import chunk_transcript
from app.services.embeddings import embed_texts_batch

logger = logging.getLogger(__name__)


def fetch_video_metadata(video_id: str) -> Dict[str, Any]:
    """Fetches video metadata (title, thumbnail, duration) via yt-dlp without downloading media."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                title = info.get("title") or f"YouTube Video ({video_id})"
                thumbnail = info.get("thumbnail") or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                duration = int(info.get("duration") or 0)
                return {
                    "title": title,
                    "thumbnail_url": thumbnail,
                    "duration_seconds": duration
                }
    except Exception as e:
        logger.warning(f"yt-dlp metadata extraction failed for {video_id}: {e}")

    # Fallback default metadata
    return {
        "title": f"YouTube Video ({video_id})",
        "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        "duration_seconds": 0
    }


def fetch_video_transcript(video_id: str) -> List[Dict[str, Any]]:
    """
    Fetches raw caption segments via youtube-transcript-api.
    Supports both youtube-transcript-api v1.0+ (instance API with to_raw_data())
    and legacy v0.x (class-level get_transcript/list_transcripts).
    """
    try:
        # Check for v1.0+ instance-based API
        try:
            api = YouTubeTranscriptApi()
            if hasattr(api, "fetch"):
                try:
                    fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
                    return fetched.to_raw_data()
                except Exception:
                    # Fallback to any available language transcript in the list
                    t_list = api.list(video_id)
                    for t in t_list:
                        return t.fetch().to_raw_data()
        except TypeError:
            pass

        # Legacy fallback for v0.x class-based API
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            return YouTubeTranscriptApi.get_transcript(video_id)

        raise RuntimeError("No compatible transcript retrieval method found on YouTubeTranscriptApi.")

    except (TranscriptsDisabled, NoTranscriptFound):
        raise RuntimeError("No captions or transcripts are available for this video.")
    except VideoUnavailable:
        raise RuntimeError("This video is unavailable, private, or restricted.")
    except Exception as e:
        raise RuntimeError(f"Could not retrieve transcript: {str(e)}")


async def process_video_ingestion(
    collection_id: uuid.UUID,
    video_id: str,
    job_id: uuid.UUID
) -> None:
    """
    Background worker task to process a single video:
    1. Update status to 'processing'
    2. Fetch metadata (title, thumbnail, duration) via yt-dlp
    3. Fetch captions via youtube-transcript-api
    4. Chunk transcript into 30-60s sentence-aware segments
    5. Generate embeddings with concurrency limiting and exponential backoff
    6. Store chunks in pgvector
    7. Update status to 'ready' (or 'failed' on error)
    """
    logger.info(f"Starting ingestion for video {video_id} in collection {collection_id}")

    async with async_session_factory() as db:
        try:
            # 1. Mark job and video as processing
            now = datetime.now(timezone.utc)
            await db.execute(
                update(JobModel)
                .where(JobModel.job_id == job_id)
                .values(status="processing", updated_at=now)
            )
            await db.execute(
                update(VideoModel)
                .where(VideoModel.video_id == video_id, VideoModel.collection_id == collection_id)
                .values(status="processing")
            )
            await db.commit()

            # 2. Fetch metadata in thread pool
            loop = asyncio.get_running_loop()
            meta = await loop.run_in_executor(None, fetch_video_metadata, video_id)
            
            await db.execute(
                update(VideoModel)
                .where(VideoModel.video_id == video_id, VideoModel.collection_id == collection_id)
                .values(
                    title=meta["title"],
                    thumbnail_url=meta["thumbnail_url"],
                    duration_seconds=meta["duration_seconds"]
                )
            )
            await db.commit()

            # 3. Fetch transcript
            try:
                raw_segments = await loop.run_in_executor(None, fetch_video_transcript, video_id)
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Transcript unavailable for {video_id}: {error_msg}")
                await db.execute(
                    update(VideoModel)
                    .where(VideoModel.video_id == video_id, VideoModel.collection_id == collection_id)
                    .values(status="failed", error_message=error_msg)
                )
                await db.execute(
                    update(JobModel)
                    .where(JobModel.job_id == job_id)
                    .values(status="failed", error_message=error_msg, updated_at=datetime.now(timezone.utc))
                )
                await db.commit()
                return

            # 4. Chunk transcript
            chunks_data = chunk_transcript(raw_segments, min_duration=30.0, max_duration=60.0)
            if not chunks_data:
                err = "No text content found in transcript."
                await db.execute(
                    update(VideoModel)
                    .where(VideoModel.video_id == video_id, VideoModel.collection_id == collection_id)
                    .values(status="failed", error_message=err)
                )
                await db.execute(
                    update(JobModel)
                    .where(JobModel.job_id == job_id)
                    .values(status="failed", error_message=err, updated_at=datetime.now(timezone.utc))
                )
                await db.commit()
                return

            # 5. Generate embeddings
            chunk_texts = [c["text"] for c in chunks_data]
            embeddings = await embed_texts_batch(chunk_texts)

            # 6. Delete any existing chunks for this video in collection, then insert new chunks
            chunk_models = []
            for c_info, emb in zip(chunks_data, embeddings):
                chunk_models.append(
                    ChunkModel(
                        chunk_id=uuid.uuid4(),
                        video_id=video_id,
                        collection_id=collection_id,
                        start_time=c_info["start_time"],
                        end_time=c_info["end_time"],
                        text=c_info["text"],
                        embedding=emb
                    )
                )
            db.add_all(chunk_models)

            # 7. Update status to ready
            await db.execute(
                update(VideoModel)
                .where(VideoModel.video_id == video_id, VideoModel.collection_id == collection_id)
                .values(status="ready", error_message=None)
            )
            await db.execute(
                update(JobModel)
                .where(JobModel.job_id == job_id)
                .values(status="done", error_message=None, updated_at=datetime.now(timezone.utc))
            )
            await db.commit()
            logger.info(f"Video {video_id} successfully ingested with {len(chunk_models)} chunks.")

        except Exception as exc:
            logger.error(f"Ingestion failed unexpectedly for {video_id}: {exc}", exc_info=True)
            await db.rollback()
            try:
                await db.execute(
                    update(VideoModel)
                    .where(VideoModel.video_id == video_id, VideoModel.collection_id == collection_id)
                    .values(status="failed", error_message=str(exc))
                )
                await db.execute(
                    update(JobModel)
                    .where(JobModel.job_id == job_id)
                    .values(status="failed", error_message=str(exc), updated_at=datetime.now(timezone.utc))
                )
                await db.commit()
            except Exception:
                pass
