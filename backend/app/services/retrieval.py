import asyncio
import logging
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.config import settings
from app.models import ChunkModel, VideoModel
from app.services.embeddings import embed_text

logger = logging.getLogger(__name__)

RETRY_DELAYS = [1.0, 2.0, 4.0, 8.0]


def format_timestamp(seconds: float) -> str:
    """Formats float seconds into MM:SS or HH:MM:SS string."""
    total_sec = int(seconds)
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    sec = total_sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"


async def search_collection_chunks(
    db: AsyncSession,
    collection_id: uuid.UUID,
    query_text: str,
    limit_sources: int = 4
) -> List[Dict[str, Any]]:
    """
    Performs vector similarity search scoped to collection_id.
    Applies SIMILARITY_THRESHOLD and groups by video_id to surface
    the best chunk per distinct video up to limit_sources.
    """
    # 1. Embed query
    query_vector = await embed_text(query_text)

    # 2. Vector search query with cosine distance
    cosine_distance = ChunkModel.embedding.cosine_distance(query_vector)
    
    stmt = (
        select(
            ChunkModel,
            VideoModel.title,
            VideoModel.thumbnail_url,
            cosine_distance.label("distance")
        )
        .join(
            VideoModel,
            and_(
                ChunkModel.video_id == VideoModel.video_id,
                ChunkModel.collection_id == VideoModel.collection_id
            )
        )
        .where(
            ChunkModel.collection_id == collection_id,
            VideoModel.status == "ready",
            ChunkModel.embedding.isnot(None)
        )
        .order_by(cosine_distance.asc())
        .limit(30)
    )

    result = await db.execute(stmt)
    rows = result.all()

    # 3. Filter by similarity threshold & group by video_id
    grouped_by_video: Dict[str, Dict[str, Any]] = {}
    
    for chunk, video_title, thumbnail_url, dist in rows:
        similarity = 1.0 - float(dist)
        if similarity < settings.SIMILARITY_THRESHOLD:
            continue
        
        # Keep the top-scoring chunk for each distinct video
        if chunk.video_id not in grouped_by_video:
            grouped_by_video[chunk.video_id] = {
                "video_id": chunk.video_id,
                "title": video_title or f"Video {chunk.video_id}",
                "thumbnail": thumbnail_url or f"https://img.youtube.com/vi/{chunk.video_id}/hqdefault.jpg",
                "start_time": chunk.start_time,
                "end_time": chunk.end_time,
                "excerpt": chunk.text,
                "similarity": similarity
            }
            if len(grouped_by_video) >= limit_sources:
                break

    # If no results met strict threshold, but chunks exist, take the top 1 or 2 chunks anyway if distance is reasonable
    if not grouped_by_video and rows:
        for chunk, video_title, thumbnail_url, dist in rows[:2]:
            if chunk.video_id not in grouped_by_video:
                similarity = 1.0 - float(dist)
                grouped_by_video[chunk.video_id] = {
                    "video_id": chunk.video_id,
                    "title": video_title or f"Video {chunk.video_id}",
                    "thumbnail": thumbnail_url or f"https://img.youtube.com/vi/{chunk.video_id}/hqdefault.jpg",
                    "start_time": chunk.start_time,
                    "end_time": chunk.end_time,
                    "excerpt": chunk.text,
                    "similarity": similarity
                }
                if len(grouped_by_video) >= limit_sources:
                    break

    return list(grouped_by_video.values())


async def generate_rag_answer(question: str, sources: List[Dict[str, Any]]) -> str:
    """
    Synthesizes a natural language answer from the retrieved transcript chunks
    using the configured Gemini chat model.
    """
    if not sources:
        return "No relevant information was found in the indexed videos for your question."

    if not settings.GEMINI_API_KEY:
        # Mock/development fallback if key is not yet configured
        return (
            f"[Dev Mode - GEMINI_API_KEY not configured] Found {len(sources)} relevant source(s). "
            f"Top match from '{sources[0]['title']}' at timestamp {format_timestamp(sources[0]['start_time'])}: "
            f"\"{sources[0]['excerpt'][:200]}...\""
        )

    # Build context from sources
    context_blocks = []
    for idx, s in enumerate(sources, 1):
        ts = format_timestamp(s["start_time"])
        context_blocks.append(
            f"Source [{idx}] - Video: \"{s['title']}\" (Timestamp: {ts})\n"
            f"Transcript Excerpt: \"{s['excerpt']}\""
        )
    context_text = "\n\n".join(context_blocks)

    system_prompt = (
        "You are an AI assistant answering questions about YouTube video transcripts. "
        "Answer the user's question accurately, thoroughly, and informatively, using ONLY the retrieved "
        "transcript excerpts provided below. Do not use outside knowledge or hallucinate facts that are not "
        "present in the excerpts. If the excerpts do not contain sufficient information to answer the question, "
        "state that clearly.\n\n"
        f"TRANSCRIPT CONTEXT:\n{context_text}\n\n"
        f"USER QUESTION: {question}\n\n"
        "ANSWER:"
    )

    model_name = settings.GEMINI_CHAT_MODEL
    if not model_name.startswith("models/"):
        model_endpoint = f"models/{model_name}"
    else:
        model_endpoint = model_name

    url = f"https://generativelanguage.googleapis.com/v1beta/{model_endpoint}:generateContent?key={settings.GEMINI_API_KEY}"

    payload = {
        "contents": [
            {
                "parts": [{"text": system_prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1024
        }
    }

    last_exception = None
    for attempt, delay in enumerate([0.0] + RETRY_DELAYS):
        if delay > 0:
            logger.warning(f"Backing off {delay}s before chat generation retry {attempt}")
            await asyncio.sleep(delay)

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                    return "No response generated by model."
                elif resp.status_code == 404 and "gemini-3.6-flash" not in url:
                    logger.warning(f"Model {model_endpoint} returned 404; attempting fallback to gemini-3.6-flash...")
                    fallback_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={settings.GEMINI_API_KEY}"
                    f_resp = await client.post(fallback_url, json=payload)
                    if f_resp.status_code == 200:
                        data = f_resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                return parts[0].get("text", "").strip()
                    url = fallback_url
                elif resp.status_code in (429, 503, 500):
                    logger.warning(f"Gemini chat API error {resp.status_code}: {resp.text}")
                    last_exception = RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
                    continue
                else:
                    raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text}")
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            logger.warning(f"Network error in chat generation attempt {attempt}: {exc}")
            last_exception = exc
            continue

    return f"Unable to generate answer due to upstream Gemini API error: {last_exception}"
