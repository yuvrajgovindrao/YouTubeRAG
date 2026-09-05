import re
import logging
from typing import List, Dict, Any, Optional, Callable
from urllib.parse import urlparse, parse_qs
import yt_dlp

logger = logging.getLogger(__name__)

# Regular expressions for YouTube video ID and URLs
YOUTUBE_VIDEO_ID_REGEX = re.compile(r'^[a-zA-Z0-9_-]{11}$')
YOUTUBE_PLAYLIST_REGEX = re.compile(r'[?&]list=([a-zA-Z0-9_-]+)')


def extract_video_id_from_token(token: str) -> Optional[str]:
    """
    Extracts YouTube video ID from a URL or raw ID string.
    Supports standard 11-char IDs, watch?v=..., youtu.be/..., shorts/..., embed/...
    """
    token = token.strip()
    if not token:
        return None
        
    # Check if raw token matches 11-char ID
    if YOUTUBE_VIDEO_ID_REGEX.match(token):
        return token

    # Check if token is a URL
    url_to_parse = token if (token.startswith("http://") or token.startswith("https://")) else f"https://{token}"
    try:
        parsed = urlparse(url_to_parse)
        netloc = parsed.netloc.lower()
        
        # youtu.be/<id>
        if "youtu.be" in netloc:
            path_clean = parsed.path.strip("/")
            if path_clean:
                vid = path_clean.split("/")[0].split("?")[0]
                if vid:
                    return vid

        # youtube.com
        if "youtube.com" in netloc or "youtube" in netloc:
            # Query param v=
            if parsed.query:
                qs = parse_qs(parsed.query)
                if "v" in qs and qs["v"]:
                    return qs["v"][0]

            # Path formats: /shorts/<id>, /embed/<id>, /v/<id>
            path_parts = [p for p in parsed.path.split("/") if p]
            if len(path_parts) >= 2 and path_parts[0] in ("shorts", "embed", "v"):
                return path_parts[1]
    except Exception:
        pass

    # Regex fallback for watch?v=<id> or youtu.be/<id> with variable length (e.g. mock test IDs)
    fallback_match = re.search(r'(?:v=|youtu\.be/|shorts/|embed/)([a-zA-Z0-9_-]+)', token)
    if fallback_match:
        return fallback_match.group(1)

    return None


def extract_playlist_id_from_token(token: str) -> Optional[str]:
    """Extracts YouTube playlist ID from a URL or token if present."""
    token = token.strip()
    match = YOUTUBE_PLAYLIST_REGEX.search(token)
    if match:
        return match.group(1)
    return None


def default_resolve_playlist(playlist_url_or_id: str) -> List[str]:
    """
    Uses yt-dlp in extract_flat mode (metadata only, no media download)
    to fetch video IDs belonging to a playlist.
    """
    url = playlist_url_or_id
    if not url.startswith("http"):
        url = f"https://www.youtube.com/playlist?list={playlist_url_or_id}"

    ydl_opts = {
        'extract_flat': True,
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
    }
    
    video_ids = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and 'entries' in info:
                for entry in info['entries']:
                    if entry and isinstance(entry, dict) and entry.get('id'):
                        video_ids.append(entry['id'])
    except Exception as e:
        logger.error(f"Failed to resolve playlist {playlist_url_or_id}: {e}")

    return video_ids


def parse_and_cap_urls(
    raw_text: str,
    max_videos: int = 5,
    playlist_resolver: Optional[Callable[[str], List[str]]] = None
) -> Dict[str, Any]:
    """
    Parses mixed raw text containing video URLs, shorts, embed URLs, or playlist URLs.
    
    Rules:
    1. Splits raw text on newlines, commas, or whitespace.
    2. Identifies explicit individual video IDs and playlist IDs.
    3. Resolves playlist IDs to video IDs in native order.
    4. Deduplicates all videos by video_id.
    5. Applies the max_videos cap:
       - Explicit individual links take priority first.
       - Then fills remaining slots from playlist(s) in native order.
    6. Returns accepted video IDs, truncation flag, and dropped counts.
    """
    resolver = playlist_resolver or default_resolve_playlist
    
    # Split tokens on comma, whitespace, or newlines
    tokens = [t.strip() for t in re.split(r'[\s,\n\r]+', raw_text) if t.strip()]

    individual_video_ids: List[str] = []
    playlist_urls: List[str] = []
    invalid_tokens: List[str] = []

    for token in tokens:
        # Check if it's explicitly a playlist URL (e.g. /playlist?list=... or list= without watch?v=)
        is_pure_playlist = "playlist?list=" in token or ("list=" in token and "watch?v=" not in token and "v=" not in token)
        
        if is_pure_playlist:
            pl_id = extract_playlist_id_from_token(token)
            if pl_id:
                if token not in playlist_urls:
                    playlist_urls.append(token)
            else:
                invalid_tokens.append(token)
            continue

        # Check for individual video URL or ID
        vid = extract_video_id_from_token(token)
        if vid:
            if vid not in individual_video_ids:
                individual_video_ids.append(vid)
        else:
            # Fallback: check if it's a playlist URL
            pl_id = extract_playlist_id_from_token(token)
            if pl_id:
                if token not in playlist_urls:
                    playlist_urls.append(token)
            else:
                invalid_tokens.append(token)

    # Resolve all playlist video IDs
    resolved_playlist_video_ids: List[str] = []
    for pl in playlist_urls:
        ids = resolver(pl)
        for vid in ids:
            if vid not in resolved_playlist_video_ids and vid not in individual_video_ids:
                resolved_playlist_video_ids.append(vid)

    total_detected = len(individual_video_ids) + len(resolved_playlist_video_ids)

    # Apply priority capping:
    # 1. Individual links take priority
    accepted_ids: List[str] = []
    
    if max_videos <= 0:
        accepted_ids = individual_video_ids + resolved_playlist_video_ids
    else:
        for vid in individual_video_ids:
            if len(accepted_ids) < max_videos:
                accepted_ids.append(vid)
            else:
                break
        
        # 2. Fill remaining slots from playlist(s)
        for vid in resolved_playlist_video_ids:
            if len(accepted_ids) < max_videos:
                accepted_ids.append(vid)
            else:
                break

    dropped_count = max(0, total_detected - len(accepted_ids))
    truncated = dropped_count > 0

    return {
        "video_ids": accepted_ids,
        "truncated": truncated,
        "dropped_count": dropped_count,
        "total_detected": total_detected,
        "individual_videos_count": len(individual_video_ids),
        "playlist_videos_count": len(resolved_playlist_video_ids),
        "invalid_tokens": invalid_tokens
    }
