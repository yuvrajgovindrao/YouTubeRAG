import pytest
from app.services.url_parser import (
    extract_video_id_from_token,
    extract_playlist_id_from_token,
    parse_and_cap_urls
)


def test_extract_video_id_from_various_formats():
    assert extract_video_id_from_token("dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id_from_token("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id_from_token("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id_from_token("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id_from_token("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id_from_token("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s") == "dQw4w9WgXcQ"


def test_extract_playlist_id():
    assert extract_playlist_id_from_token("https://www.youtube.com/playlist?list=PL1234567890ABCDEF") == "PL1234567890ABCDEF"


def test_mixed_input_deduplication():
    raw_text = """
    https://www.youtube.com/watch?v=video111111
    https://youtu.be/video222222, https://youtu.be/video111111
    video333333
    """
    res = parse_and_cap_urls(raw_text, max_videos=5)
    assert res["video_ids"] == ["video111111", "video222222", "video333333"]
    assert res["total_detected"] == 3
    assert not res["truncated"]
    assert res["dropped_count"] == 0


def test_priority_capping_with_playlists():
    # Mock playlist resolver returning 5 videos: p1, p2, p3, p4, p5
    def mock_playlist_resolver(pl_url):
        return ["pl_vid_0001", "pl_vid_0002", "pl_vid_0003", "pl_vid_0004", "pl_vid_0005"]

    raw_text = """
    https://www.youtube.com/watch?v=indiv_vid_01
    https://www.youtube.com/watch?v=indiv_vid_02
    https://www.youtube.com/watch?v=indiv_vid_03
    https://www.youtube.com/playlist?list=PL_SOME_PLAYLIST
    """
    # Max videos = 5: individual links (3) take slots 1..3, playlist fills remaining 2 (pl_vid_0001, pl_vid_0002)
    res = parse_and_cap_urls(raw_text, max_videos=5, playlist_resolver=mock_playlist_resolver)
    assert res["video_ids"] == [
        "indiv_vid_01",
        "indiv_vid_02",
        "indiv_vid_03",
        "pl_vid_0001",
        "pl_vid_0002"
    ]
    assert res["truncated"] is True
    assert res["dropped_count"] == 3  # total was 3 + 5 = 8; accepted 5; dropped 3
    assert res["total_detected"] == 8


def test_duplicate_between_individual_and_playlist():
    # If a video is in individual links and playlist, individual takes priority and is not duplicated
    def mock_playlist_resolver(pl_url):
        return ["dup_video_01", "pl_only_0002"]

    raw_text = """
    https://www.youtube.com/watch?v=dup_video_01
    https://www.youtube.com/playlist?list=PL_TEST
    """
    res = parse_and_cap_urls(raw_text, max_videos=5, playlist_resolver=mock_playlist_resolver)
    assert res["video_ids"] == ["dup_video_01", "pl_only_0002"]
    assert res["total_detected"] == 2
