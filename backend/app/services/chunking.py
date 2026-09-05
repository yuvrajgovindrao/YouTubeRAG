import re
from typing import List, Dict, Any

SENTENCE_ENDINGS = re.compile(r'[.!?]\s*$')


def chunk_transcript(
    segments: List[Dict[str, Any]],
    min_duration: float = 30.0,
    max_duration: float = 60.0
) -> List[Dict[str, Any]]:
    """
    Merges adjacent raw transcript segments into chunks targeting 30-60 seconds of speech,
    preserving the exact start_time of the first segment in the chunk for accurate seeking.

    Each segment is expected to have:
      - 'text': str
      - 'start': float
      - 'duration': float (or calculated from next start)

    Returns a list of dicts:
      - 'start_time': float
      - 'end_time': float
      - 'text': str
    """
    if not segments:
        return []

    chunks: List[Dict[str, Any]] = []
    
    current_texts: List[str] = []
    current_start: float = float(segments[0].get("start", 0.0))
    current_end: float = current_start

    for seg in segments:
        raw_text = seg.get("text", "").strip()
        if not raw_text:
            continue

        seg_start = float(seg.get("start", 0.0))
        seg_duration = float(seg.get("duration", 0.0))
        seg_end = seg_start + seg_duration

        # If current_texts already has content, check if adding this segment would exceed max_duration
        if current_texts:
            potential_duration = seg_end - current_start
            if potential_duration > max_duration:
                # Flush the current chunk before adding this segment
                merged_text = " ".join(current_texts)
                merged_text = re.sub(r'\s+', ' ', merged_text).strip()
                chunks.append({
                    "start_time": round(current_start, 2),
                    "end_time": round(current_end, 2),
                    "text": merged_text
                })
                # Reset for next chunk with this segment
                current_texts = [raw_text]
                current_start = seg_start
                current_end = seg_end
                continue

        # Add segment to current chunk
        if not current_texts:
            current_start = seg_start

        current_texts.append(raw_text)
        current_end = max(current_end, seg_end)

        chunk_duration = current_end - current_start
        has_sentence_end = bool(SENTENCE_ENDINGS.search(raw_text))

        # Split if we have reached min_duration and have a sentence boundary
        if chunk_duration >= min_duration and has_sentence_end:
            merged_text = " ".join(current_texts)
            merged_text = re.sub(r'\s+', ' ', merged_text).strip()
            chunks.append({
                "start_time": round(current_start, 2),
                "end_time": round(current_end, 2),
                "text": merged_text
            })
            current_texts = []

    # Flush remaining text
    if current_texts:
        merged_text = " ".join(current_texts)
        merged_text = re.sub(r'\s+', ' ', merged_text).strip()
        if merged_text:
            chunks.append({
                "start_time": round(current_start, 2),
                "end_time": round(current_end, 2),
                "text": merged_text
            })

    return chunks
