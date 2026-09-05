import React, { useState } from 'react';
import { PlusCircle, Link as LinkIcon, AlertTriangle, Loader2 } from 'lucide-react';

export default function LinkInput({ onIngest, isSubmitting, truncationNotice }) {
  const [inputText, setInputText] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!inputText.trim() || isSubmitting) return;
    onIngest(inputText.trim());
  };

  const handlePasteSample = (sample) => {
    setInputText(sample);
  };

  return (
    <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.85rem' }}>
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            background: 'rgba(239, 68, 68, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <LinkIcon size={16} color="#ef4444" />
        </div>
        <div>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#f8fafc' }}>
            Ingest YouTube Videos or Playlists
          </h3>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
            Paste single video URLs, multiple URLs (space/comma/newline), or a playlist link.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <textarea
          className="input-textarea"
          id="links-input"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder={`e.g. https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://youtu.be/jNQXAC9IVRw
or https://www.youtube.com/playlist?list=PL...`}
          disabled={isSubmitting}
        />

        {truncationNotice && (
          <div
            style={{
              marginTop: '0.75rem',
              padding: '0.65rem 0.9rem',
              background: 'rgba(245, 158, 11, 0.12)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              color: '#fbbf24',
              fontSize: '0.82rem',
            }}
          >
            <AlertTriangle size={16} style={{ flexShrink: 0 }} />
            <span>{truncationNotice}</span>
          </div>
        )}

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginTop: '1rem',
            flexWrap: 'wrap',
            gap: '0.75rem',
          }}
        >
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Quick try:</span>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
              onClick={() => handlePasteSample('https://www.youtube.com/watch?v=aircAruvnKk\nhttps://www.youtube.com/watch?v=9bZkp7q19f0')}
            >
              2 Sample Videos
            </button>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            id="ingest-submit-button"
            disabled={isSubmitting || !inputText.trim()}
          >
            {isSubmitting ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Ingesting Content...</span>
              </>
            ) : (
              <>
                <PlusCircle size={16} />
                <span>Index Videos</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
