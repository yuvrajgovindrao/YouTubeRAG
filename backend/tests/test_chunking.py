import pytest
from app.services.chunking import chunk_transcript


def test_chunk_preserves_initial_start_time():
    segments = [
        {"start": 12.5, "duration": 4.0, "text": "Welcome back to the channel."},
        {"start": 16.5, "duration": 5.0, "text": "Today we are discussing RAG systems."},
        {"start": 21.5, "duration": 5.0, "text": "Retrieval augmented generation connects models to external data."},
        {"start": 26.5, "duration": 5.0, "text": "This prevents hallucinations."}
    ]
    # Total duration = 31.5 - 12.5 = 19.0s (< 30.0s min_duration) -> flushes at end with start_time = 12.5
    chunks = chunk_transcript(segments, min_duration=30.0, max_duration=60.0)
    assert len(chunks) == 1
    assert chunks[0]["start_time"] == 12.5
    assert "Welcome back to the channel." in chunks[0]["text"]
    assert "This prevents hallucinations." in chunks[0]["text"]


def test_chunk_splits_at_sentence_boundary_after_min_duration():
    segments = [
        {"start": 0.0, "duration": 15.0, "text": "This is the first sentence."},
        {"start": 15.0, "duration": 16.0, "text": "This is the second sentence."},
        {"start": 31.0, "duration": 10.0, "text": "This starts the next topic."},
        {"start": 41.0, "duration": 10.0, "text": "And finishes the topic."}
    ]
    chunks = chunk_transcript(segments, min_duration=30.0, max_duration=60.0)
    assert len(chunks) == 2
    assert chunks[0]["start_time"] == 0.0
    assert chunks[0]["text"] == "This is the first sentence. This is the second sentence."
    assert chunks[1]["start_time"] == 31.0
    assert chunks[1]["text"] == "This starts the next topic. And finishes the topic."


def test_chunk_splits_at_max_duration_without_punctuation():
    # Simulate speech with no punctuation (e.g. raw auto-generated captions)
    segments = [
        {"start": 0.0, "duration": 25.0, "text": "hello and welcome to our show today"},
        {"start": 25.0, "duration": 30.0, "text": "we are going to cover many interesting topics"},
        {"start": 55.0, "duration": 25.0, "text": "like artificial intelligence and machine learning"}
    ]
    # At segment 2 (55s..80s), 80s - 0s = 80s > 60s max_duration.
    # It flushes the first two segments (0..55s) and begins a new chunk.
    chunks = chunk_transcript(segments, min_duration=30.0, max_duration=60.0)
    assert len(chunks) == 2
    assert chunks[0]["start_time"] == 0.0
    assert chunks[0]["text"] == "hello and welcome to our show today we are going to cover many interesting topics"
    assert chunks[1]["start_time"] == 55.0
    assert chunks[1]["text"] == "like artificial intelligence and machine learning"
