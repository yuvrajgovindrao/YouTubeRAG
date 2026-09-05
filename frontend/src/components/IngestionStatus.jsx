import React from 'react';
import { CheckCircle2, Clock, AlertCircle, Loader2, Video, Trash2 } from 'lucide-react';

function formatDuration(seconds) {
  if (!seconds) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export default function IngestionStatus({ statusData, onClearCollection, isClearing }) {
  if (!statusData || !statusData.videos || statusData.videos.length === 0) {
    return null;
  }

  const { total_videos, ready_count, processing_count, failed_count, pending_count, is_complete, videos } = statusData;
  const progressPercent = total_videos > 0 ? Math.round((ready_count / total_videos) * 100) : 0;

  return (
    <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
      {/* Header with progress count & Clear button */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Video size={18} color="#ef4444" />
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc' }}>
              Collection Index Status ({ready_count}/{total_videos} Ready)
            </h3>
          </div>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            {is_complete
              ? 'All transcripts ingested and embedded for semantic retrieval.'
              : 'Processing video captions and computing embeddings in background...'}
          </p>
        </div>

        <button
          onClick={onClearCollection}
          disabled={isClearing}
          className="btn btn-danger"
          style={{ padding: '0.45rem 0.8rem', fontSize: '0.8rem' }}
          title="Clear collection and start over"
        >
          {isClearing ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
          <span>Clear Collection</span>
        </button>
      </div>

      {/* Progress Bar */}
      <div
        style={{
          width: '100%',
          height: '6px',
          background: 'rgba(255, 255, 255, 0.08)',
          borderRadius: '9999px',
          overflow: 'hidden',
          marginBottom: '1.25rem',
        }}
      >
        <div
          style={{
            width: `${progressPercent}%`,
            height: '100%',
            background: is_complete
              ? 'linear-gradient(90deg, #10b981 0%, #059669 100%)'
              : 'linear-gradient(90deg, #ef4444 0%, #f59e0b 100%)',
            transition: 'width 0.4s ease',
            borderRadius: '9999px',
          }}
        />
      </div>

      {/* Video Grid List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
        {videos.map((vid) => {
          let badgeClass = 'badge-pending';
          let StatusIcon = Clock;
          let statusLabel = 'Queued';

          if (vid.status === 'ready') {
            badgeClass = 'badge-ready';
            StatusIcon = CheckCircle2;
            statusLabel = 'Ready for Search';
          } else if (vid.status === 'processing') {
            badgeClass = 'badge-processing';
            StatusIcon = Loader2;
            statusLabel = 'Processing Captions...';
          } else if (vid.status === 'failed') {
            badgeClass = 'badge-failed';
            StatusIcon = AlertCircle;
            statusLabel = 'Failed';
          }

          return (
            <div
              key={vid.video_id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.85rem',
                padding: '0.6rem 0.85rem',
                background: 'rgba(11, 15, 25, 0.6)',
                borderRadius: '10px',
                border: '1px solid rgba(255, 255, 255, 0.05)',
              }}
            >
              <img
                src={vid.thumbnail_url || `https://img.youtube.com/vi/${vid.video_id}/hqdefault.jpg`}
                alt={vid.title || vid.video_id}
                style={{
                  width: '54px',
                  height: '36px',
                  borderRadius: '6px',
                  objectFit: 'cover',
                  flexShrink: 0,
                }}
              />

              <div style={{ flex: 1, minWidth: 0 }}>
                <p
                  style={{
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    color: '#f1f5f9',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                  title={vid.title || vid.video_id}
                >
                  {vid.title || `Video (${vid.video_id})`}
                </p>
                <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', marginTop: '0.15rem' }}>
                  {vid.duration_seconds > 0 && (
                    <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
                      {formatDuration(vid.duration_seconds)}
                    </span>
                  )}
                  {vid.error_message && (
                    <span style={{ fontSize: '0.72rem', color: '#f87171' }} title={vid.error_message}>
                      {vid.error_message}
                    </span>
                  )}
                </div>
              </div>

              <div className={`badge ${badgeClass}`} style={{ flexShrink: 0 }}>
                <StatusIcon size={12} className={vid.status === 'processing' ? 'animate-spin' : undefined} />
                <span>{statusLabel}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
