import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Youtube, RefreshCw, Sparkles, Layers, AlertCircle } from 'lucide-react';
import LinkInput from './components/LinkInput';
import IngestionStatus from './components/IngestionStatus';
import QueryBox from './components/QueryBox';
import AnswerCard from './components/AnswerCard';
import SourceCard from './components/SourceCard';
import Player from './components/Player';
import {
  getOrCreateCollection,
  submitVideos,
  getCollectionStatus,
  askQuestion,
  deleteCollection,
  clearSession,
  getStoredSessionId,
} from './services/api';

export default function App() {
  const [collectionId, setCollectionId] = useState(null);
  const [sessionId, setSessionId] = useState(getStoredSessionId());
  const [statusData, setStatusData] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [isAsking, setIsAsking] = useState(false);
  const [truncationNotice, setTruncationNotice] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  // Q&A State
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [currentAnswer, setCurrentAnswer] = useState(null);
  const [sources, setSources] = useState([]);

  // Video Player state
  const [activeTarget, setActiveTarget] = useState(null);

  const pollIntervalRef = useRef(null);

  // 1. Initialize Collection on Load
  const initCollection = useCallback(async () => {
    try {
      const col = await getOrCreateCollection();
      setCollectionId(col.collection_id);
      setSessionId(getStoredSessionId());

      // Fetch current status
      const st = await getCollectionStatus(col.collection_id);
      setStatusData(st);
      if (st.videos && st.videos.length > 0) {
        const firstReady = st.videos.find((v) => v.status === 'ready');
        if (firstReady && !activeTarget) {
          setActiveTarget({
            videoId: firstReady.video_id,
            startSeconds: 0,
            title: firstReady.title,
          });
        }
      }
    } catch (err) {
      console.error('Initialization failed:', err);
      setErrorMessage(err.message || 'Failed to connect to backend.');
    }
  }, [activeTarget]);

  useEffect(() => {
    initCollection();
  }, [initCollection]);

  // 2. Status Polling while processing
  useEffect(() => {
    if (!collectionId) return;

    const shouldPoll =
      statusData &&
      statusData.videos &&
      statusData.videos.some((v) => v.status === 'processing' || v.status === 'pending');

    if (shouldPoll) {
      pollIntervalRef.current = setInterval(async () => {
        try {
          const fresh = await getCollectionStatus(collectionId);
          setStatusData(fresh);
        } catch (e) {
          console.error('Status poll error:', e);
        }
      }, 2500);
    } else {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [collectionId, statusData]);

  // 3. Handle Ingestion Submission
  const handleIngest = async (rawLinks) => {
    if (!collectionId) return;
    setIsSubmitting(true);
    setTruncationNotice(null);
    setErrorMessage(null);

    try {
      const res = await submitVideos(collectionId, rawLinks);
      if (res.truncated) {
        setTruncationNotice(res.message);
      }

      // Immediately refresh status
      const fresh = await getCollectionStatus(collectionId);
      setStatusData(fresh);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to ingest videos.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // 4. Handle Asking Questions
  const handleAsk = async (question) => {
    if (!collectionId) return;
    setIsAsking(true);
    setCurrentQuestion(question);
    setErrorMessage(null);

    try {
      const res = await askQuestion(collectionId, question);
      setCurrentAnswer(res.answer);
      setSources(res.sources || []);

      // If sources returned, automatically focus the first source in the player
      if (res.sources && res.sources.length > 0) {
        const top = res.sources[0];
        setActiveTarget({
          videoId: top.video_id,
          startSeconds: top.start_time,
          title: top.title,
        });
      }
    } catch (err) {
      setErrorMessage(err.message || 'Failed to generate answer.');
    } finally {
      setIsAsking(false);
    }
  };

  // 5. Handle Clearing Collection
  const handleClearCollection = async () => {
    if (!collectionId) return;
    setIsClearing(true);
    try {
      await deleteCollection(collectionId);
      setStatusData(null);
      setCurrentAnswer(null);
      setCurrentQuestion(null);
      setSources([]);
      setActiveTarget(null);
      setTruncationNotice(null);
      // Re-create a fresh collection
      await initCollection();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to clear collection.');
    } finally {
      setIsClearing(false);
    }
  };

  // 6. Handle Full Session Reset
  const handleResetSession = () => {
    clearSession();
    window.location.reload();
  };

  const hasReadyVideos = statusData?.ready_count > 0;

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="brand-logo">
          <div className="logo-icon-wrapper">
            <Youtube size={26} color="#fff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <h1 className="brand-title">YouTube RAG Assistant</h1>
              <span className="brand-badge">pgvector + gemini</span>
            </div>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
              Ingest playlists &bull; Grounded transcript RAG &bull; Precise timestamp navigation
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {sessionId && (
            <div
              className="badge badge-pending"
              style={{ fontSize: '0.72rem', padding: '0.3rem 0.6rem' }}
              title={`Session ID: ${sessionId}`}
            >
              <Layers size={12} />
              <span>Session: {sessionId.slice(0, 8)}...</span>
            </div>
          )}

          <button
            onClick={handleResetSession}
            className="btn btn-secondary"
            style={{ padding: '0.45rem 0.8rem', fontSize: '0.8rem' }}
            title="Start fresh with a new session"
          >
            <RefreshCw size={13} />
            <span>New Session</span>
          </button>
        </div>
      </header>

      {/* Global Error Banner */}
      {errorMessage && (
        <div
          style={{
            marginBottom: '1.5rem',
            padding: '0.85rem 1.25rem',
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: '0.65rem',
            color: '#f87171',
            fontSize: '0.9rem',
          }}
        >
          <AlertCircle size={18} style={{ flexShrink: 0 }} />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Primary 2-Column Dashboard Grid */}
      <div className="dashboard-grid">
        {/* Left Column: Link Ingestion, Status, and Q&A */}
        <div>
          {/* Link Ingestion Box */}
          <LinkInput
            onIngest={handleIngest}
            isSubmitting={isSubmitting}
            truncationNotice={truncationNotice}
          />

          {/* Collection Status Grid */}
          <IngestionStatus
            statusData={statusData}
            onClearCollection={handleClearCollection}
            isClearing={isClearing}
          />

          {/* Query Box */}
          <QueryBox
            onAsk={handleAsk}
            isAsking={isAsking}
            hasReadyVideos={hasReadyVideos}
          />

          {/* Synthesized Answer */}
          <AnswerCard
            question={currentQuestion}
            answer={currentAnswer}
            sourcesCount={sources.length}
          />
        </div>

        {/* Right Column: Sticky Embedded Player + Ranked Source Cards */}
        <div className="player-sticky-wrapper">
          {/* Single Embedded YouTube Player */}
          <Player activeTarget={activeTarget} />

          {/* Ranked Source Cards List */}
          {sources.length > 0 && (
            <div className="glass-panel" style={{ padding: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                <Sparkles size={18} color="#ef4444" />
                <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc' }}>
                  Ranked Transcript Sources ({sources.length})
                </h3>
              </div>
              <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '1rem' }}>
                Click any source card to jump the player directly to the exact discussion timestamp.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                {sources.map((src, idx) => (
                  <SourceCard
                    key={`${src.video_id}-${src.start_time}-${idx}`}
                    source={src}
                    index={idx}
                    onSelectSource={setActiveTarget}
                    isActive={
                      activeTarget?.videoId === src.video_id &&
                      Math.abs((activeTarget?.startSeconds || 0) - src.start_time) < 1
                    }
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
