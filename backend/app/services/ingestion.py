import asyncio
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import json
import urllib.request
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

from app.db import async_session_factory
from app.models import VideoModel, ChunkModel, JobModel
from app.services.chunking import chunk_transcript
from app.services.embeddings import embed_texts_batch

logger = logging.getLogger(__name__)


YTDLP_EXTRACTOR_ARGS = {
    'youtube': {
        'player_client': ['android', 'ios']
    }
}


def fetch_video_metadata(video_id: str) -> Dict[str, Any]:
    """Fetches video metadata (title, thumbnail, duration) via yt-dlp without downloading media."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'extractor_args': YTDLP_EXTRACTOR_ARGS,
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


def fetch_transcript_via_ytdlp(video_id: str) -> List[Dict[str, Any]]:
    """
    Fallback transcript extractor using yt-dlp's client-impersonated signed timedtext API.
    Bypasses YouTube IP bans and rate-limits on caption endpoints.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extractor_args': YTDLP_EXTRACTOR_ARGS,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return []

            sub_dict = info.get('subtitles', {}) or {}
            auto_sub_dict = info.get('automatic_captions', {}) or {}

            # Prioritize manual subtitles, then auto captions
            merged_subs = {**auto_sub_dict, **sub_dict}
            if not merged_subs:
                return []

            # Search in order: explicit English, then any available language
            ordered_langs = ['en', 'en-US', 'en-GB'] + [
                lang for lang in merged_subs.keys() if lang not in ('en', 'en-US', 'en-GB')
            ]

            for lang in ordered_langs:
                if lang in merged_subs:
                    formats = merged_subs[lang]
                    json3_fmt = next((f for f in formats if isinstance(f, dict) and f.get('ext') == 'json3'), None)
                    if json3_fmt and json3_fmt.get('url'):
                        req = urllib.request.Request(
                            json3_fmt['url'],
                            headers={'User-Agent': 'com.google.android.youtube/19.29.37 (Linux; U; Android 11)'}
                        )
                        with urllib.request.urlopen(req, timeout=15) as resp:
                            data = json.loads(resp.read().decode('utf-8'))
                            segments = []
                            for event in data.get('events', []):
                                segs = event.get('segs')
                                if not segs:
                                    continue
                                text = ''.join(s.get('utf8', '') for s in segs).strip()
                                if text and text != '\n':
                                    start = round(float(event.get('tStartMs', 0)) / 1000.0, 2)
                                    duration = round(float(event.get('dDurationMs', 0)) / 1000.0, 2)
                                    segments.append({
                                        'start': start,
                                        'duration': duration,
                                        'text': text
                                    })
                            if segments:
                                return segments
    except Exception as e:
        logger.warning(f"yt-dlp subtitle extraction error for {video_id}: {e}")

    return []


def fetch_video_transcript(video_id: str) -> List[Dict[str, Any]]:
    """
    Fetches raw caption segments via youtube-transcript-api,
    with an automatic fallback to yt-dlp signed timedtext extraction
    when IP bans, RequestBlocked, or missing transcripts occur.
    """
    # 1. Try youtube-transcript-api first
    try:
        try:
            api = YouTubeTranscriptApi()
            if hasattr(api, "fetch"):
                try:
                    fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
                    return fetched.to_raw_data()
                except Exception:
                    t_list = api.list(video_id)
                    for t in t_list:
                        return t.fetch().to_raw_data()
        except TypeError:
            pass

        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            return YouTubeTranscriptApi.get_transcript(video_id)
    except Exception as err:
        logger.info(f"youtube-transcript-api failed for {video_id} ({err}); falling back to yt-dlp...")

    # 2. Fallback to yt-dlp signed timedtext extraction (bypasses IP blocks)
    try:
        ytdlp_segments = fetch_transcript_via_ytdlp(video_id)
        if ytdlp_segments:
            logger.info(f"Successfully retrieved {len(ytdlp_segments)} caption segments via yt-dlp for {video_id}")
            return ytdlp_segments
    except Exception as fallback_err:
        logger.warning(f"yt-dlp fallback also failed for {video_id}: {fallback_err}")

    raise RuntimeError("No captions or transcripts could be retrieved for this video.")


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
