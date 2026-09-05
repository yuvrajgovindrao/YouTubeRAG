import asyncio
import logging
from typing import List, Optional, Callable, Awaitable
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# Concurrency limiter: capped at 2 concurrent calls
_semaphore = asyncio.Semaphore(2)

# Exponential backoff schedule
RETRY_DELAYS = [1.0, 2.0, 4.0, 8.0]


async def embed_text(text: str) -> List[float]:
    """
    Generates an embedding vector for a single text using Gemini embedding API
    with concurrency limiting and exponential backoff.
    """
    results = await embed_texts_batch([text])
    if not results:
        raise RuntimeError("Failed to generate embedding")
    return results[0]


async def embed_texts_batch(
    texts: List[str],
    on_progress: Optional[Callable[[int, int], Awaitable[None]]] = None
) -> List[List[float]]:
    """
    Generates embeddings for a batch of texts.
    Processes sequentially or in small sub-batches to respect rate limits.
    Optionally invokes on_progress(completed_count, total_count) after each item.
    """
    if not texts:
        return []

    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set. Returning zero-vectors for mock/testing.")
        return [[0.0] * settings.EMBEDDING_DIMENSION for _ in texts]

    results: List[List[float]] = []
    total = len(texts)
    
    # Process texts through the concurrency limiter
    for idx, text in enumerate(texts):
        vector = await _embed_single_with_retry(text)
        results.append(vector)
        if on_progress:
            try:
                await on_progress(idx + 1, total)
            except Exception as e:
                logger.warning(f"Error in on_progress callback: {e}")

    return results


async def _embed_single_with_retry(text: str) -> List[float]:
    model_name = settings.GEMINI_API_KEY and settings.GEMINI_EMBEDDING_MODEL
    # Normalize model path if needed
    if not model_name.startswith("models/"):
        endpoint_model = f"models/{model_name}"
    else:
        endpoint_model = model_name

    url = f"https://generativelanguage.googleapis.com/v1beta/{endpoint_model}:embedContent?key={settings.GEMINI_API_KEY}"

    payload = {
        "model": endpoint_model,
        "content": {
            "parts": [{"text": text}]
        }
    }
    # If the model supports output_dimensionality, pass it
    if settings.EMBEDDING_DIMENSION:
        payload["outputDimensionality"] = settings.EMBEDDING_DIMENSION

    async with _semaphore:
        last_exception = None
        for attempt, delay in enumerate([0.0] + RETRY_DELAYS):
            if delay > 0:
                logger.warning(f"Backing off for {delay}s before retry attempt {attempt} for embedding call")
                await asyncio.sleep(delay)

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, json=payload)
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        values = data.get("embedding", {}).get("values", [])
                        # Adjust dimension if needed
                        if len(values) > settings.EMBEDDING_DIMENSION:
                            values = values[:settings.EMBEDDING_DIMENSION]
                        elif len(values) < settings.EMBEDDING_DIMENSION and len(values) > 0:
                            values = values + [0.0] * (settings.EMBEDDING_DIMENSION - len(values))
                        return values
                    elif resp.status_code in (429, 503, 500):
                        logger.warning(f"Gemini API rate limit or error {resp.status_code}: {resp.text}")
                        last_exception = RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
                        continue
                    else:
                        error_msg = f"Gemini API error {resp.status_code}: {resp.text}"
                        logger.error(error_msg)
                        raise RuntimeError(error_msg)
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                logger.warning(f"Network error on embedding attempt {attempt}: {exc}")
                last_exception = exc
                continue

        error_summary = f"Exhausted retries for embedding: {last_exception}"
        logger.error(error_summary)
        raise RuntimeError(error_summary)
