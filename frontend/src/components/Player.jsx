import React, { useEffect, useRef, useState } from 'react';
import { Play, Tv, Clock, ExternalLink } from 'lucide-react';

function formatTimestamp(seconds) {
  if (typeof seconds !== 'number' || isNaN(seconds)) return '00:00';
  const total = Math.floor(seconds);
  const hrs = Math.floor(total / 3600);
  const mins = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hrs > 0) {
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

export default function Player({ activeTarget }) {
  const playerRef = useRef(null);
  const containerId = 'yt-embedded-player';
  const [playerReady, setPlayerReady] = useState(false);
  const [currentVideoId, setCurrentVideoId] = useState(null);

  useEffect(() => {
    let checkInterval = null;

    function initPlayer() {
      if (window.YT && window.YT.Player) {
        if (!playerRef.current) {
          playerRef.current = new window.YT.Player(containerId, {
            height: '100%',
            width: '100%',
            videoId: activeTarget?.videoId || '',
            playerVars: {
              playsinline: 1,
              autoplay: 1,
              modestbranding: 1,
              rel: 0,
            },
            events: {
              onReady: () => {
                setPlayerReady(true);
              },
            },
          });
        }
      } else {
        // Retry when script finishes loading
        checkInterval = setTimeout(initPlayer, 200);
      }
    }

    initPlayer();

    return () => {
      if (checkInterval) clearTimeout(checkInterval);
    };
  }, []);

  // Update video and seek time when activeTarget changes
  useEffect(() => {
    if (!activeTarget || !activeTarget.videoId) return;

    const { videoId, startSeconds = 0 } = activeTarget;

    if (playerReady && playerRef.current && typeof playerRef.current.loadVideoById === 'function') {
      if (currentVideoId === videoId) {
        playerRef.current.seekTo(startSeconds, true);
        playerRef.current.playVideo();
      } else {
        playerRef.current.loadVideoById({
          videoId,
          startSeconds: Math.floor(startSeconds),
        });
        setCurrentVideoId(videoId);
      }
    }
  }, [activeTarget, playerReady, currentVideoId]);

  return (
    <div className="glass-panel" style={{ padding: '1.25rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Tv size={18} color="#ef4444" />
          <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc' }}>
            Interactive Video Player
          </h3>
        </div>
        {activeTarget && activeTarget.videoId && (
          <a
            href={`https://www.youtube.com/watch?v=${activeTarget.videoId}&t=${Math.floor(activeTarget.startSeconds || 0)}s`}
            target="_blank"
            rel="noreferrer"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.25rem',
              color: '#94a3b8',
              fontSize: '0.8rem',
              textDecoration: 'none'
            }}
          >
            <span>Open on YouTube</span>
            <ExternalLink size={13} />
          </a>
        )}
      </div>

      <div className="video-frame-container">
        <div id={containerId}></div>
        {!activeTarget && (
          <div className="video-placeholder">
            <div
              style={{
                width: '56px',
                height: '56px',
                borderRadius: '50%',
                background: 'rgba(239, 68, 68, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: '1px solid rgba(239, 68, 68, 0.3)',
              }}
            >
              <Play size={24} color="#ef4444" />
            </div>
            <div>
              <p style={{ fontWeight: 600, color: '#e2e8f0', marginBottom: '0.25rem' }}>
                No Video Playing
              </p>
              <p style={{ fontSize: '0.85rem', color: '#64748b' }}>
                Ask a question and click any timestamp source card to seek directly to that discussion point.
              </p>
            </div>
          </div>
        )}
      </div>

      {activeTarget && (
        <div
          style={{
            marginTop: '1rem',
            padding: '0.75rem 1rem',
            background: 'rgba(15, 23, 42, 0.6)',
            borderRadius: '10px',
            border: '1px solid rgba(255, 255, 255, 0.05)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}
        >
          <div style={{ overflow: 'hidden', paddingRight: '1rem' }}>
            <p style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Currently Focused Source
            </p>
            <p style={{ fontWeight: 600, fontSize: '0.9rem', color: '#f8fafc', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
              {activeTarget.title || `Video (${activeTarget.videoId})`}
            </p>
          </div>
          <div
            className="badge badge-ready"
            style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexShrink: 0 }}
          >
            <Clock size={13} />
            <span>Seek: {formatTimestamp(activeTarget.startSeconds)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
