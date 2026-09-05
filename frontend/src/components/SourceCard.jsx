import React from 'react';
import { Play, Clock, Sparkles } from 'lucide-react';

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

export default function SourceCard({ source, index, onSelectSource, isActive }) {
  const { video_id, title, thumbnail, start_time, excerpt, similarity } = source;
  const matchPercent = Math.round(similarity * 100);

  return (
    <div
      onClick={() => onSelectSource({ videoId: video_id, startSeconds: start_time, title })}
      className="glass-panel glass-panel-interactive"
      style={{
        padding: '1rem',
        cursor: 'pointer',
        borderColor: isActive ? '#ef4444' : 'rgba(255, 255, 255, 0.08)',
        background: isActive ? 'rgba(30, 41, 59, 0.95)' : 'rgba(15, 23, 42, 0.75)',
        boxShadow: isActive ? '0 0 20px rgba(239, 68, 68, 0.25)' : undefined,
        display: 'flex',
        gap: '1rem',
        alignItems: 'flex-start',
      }}
      id={`source-card-${video_id}`}
    >
      {/* Thumbnail with overlay Play icon */}
      <div
        style={{
          position: 'relative',
          width: '120px',
          height: '68px',
          flexShrink: 0,
          borderRadius: '8px',
          overflow: 'hidden',
          backgroundColor: '#000',
        }}
      >
        <img
          src={thumbnail}
          alt={title}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            opacity: 0.85,
          }}
          loading="lazy"
        />
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.35)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background 0.2s',
          }}
        >
          <div
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '50%',
              backgroundColor: 'rgba(239, 68, 68, 0.9)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 8px rgba(0,0,0,0.5)',
            }}
          >
            <Play size={13} color="#fff" style={{ marginLeft: '2px' }} />
          </div>
        </div>
        <div
          style={{
            position: 'absolute',
            bottom: '4px',
            right: '4px',
            background: 'rgba(0, 0, 0, 0.8)',
            padding: '1px 5px',
            borderRadius: '4px',
            fontSize: '0.68rem',
            fontWeight: 600,
            color: '#f8fafc',
          }}
        >
          {formatTimestamp(start_time)}
        </div>
      </div>

      {/* Content Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
          <span
            style={{
              fontSize: '0.72rem',
              fontWeight: 700,
              color: '#f87171',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}
          >
            Source #{index + 1}
          </span>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.25rem',
              fontSize: '0.72rem',
              color: '#34d399',
              fontWeight: 600,
            }}
          >
            <Sparkles size={11} />
            <span>{matchPercent}% Match</span>
          </div>
        </div>

        <h4
          style={{
            fontSize: '0.88rem',
            fontWeight: 600,
            color: '#f1f5f9',
            marginBottom: '0.4rem',
            lineHeight: 1.3,
            overflow: 'hidden',
            display: '-webkit-box',
            WebkitLineClamp: 1,
            WebkitBoxOrient: 'vertical',
          }}
          title={title}
        >
          {title}
        </h4>

        <p
          style={{
            fontSize: '0.8rem',
            color: '#94a3b8',
            lineHeight: 1.4,
            overflow: 'hidden',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            fontStyle: 'italic',
          }}
        >
          "{excerpt}"
        </p>

        <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <span style={{ fontSize: '0.72rem', color: '#ef4444', fontWeight: 600 }}>
            Click card to jump player to {formatTimestamp(start_time)} &rarr;
          </span>
        </div>
      </div>
    </div>
  );
}
