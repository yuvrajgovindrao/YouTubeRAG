import React, { useState } from 'react';
import { Search, Sparkles, Loader2 } from 'lucide-react';

export default function QueryBox({ onAsk, isAsking, hasReadyVideos }) {
  const [question, setQuestion] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!question.trim() || isAsking || !hasReadyVideos) return;
    onAsk(question.trim());
  };

  const handleSuggestion = (prompt) => {
    setQuestion(prompt);
  };

  return (
    <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.85rem' }}>
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            background: 'rgba(139, 92, 246, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Sparkles size={16} color="#8b5cf6" />
        </div>
        <div>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#f8fafc' }}>
            Ask a Question Across Ingested Transcripts
          </h3>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
            Answers are strictly synthesized from retrieved transcript chunks with clickable video timestamps.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <input
              type="text"
              className="input-text"
              id="question-input"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={
                hasReadyVideos
                  ? "What key insights or concepts were explained in these videos?"
                  : "Ingest videos above to enable natural language questioning..."
              }
              disabled={!hasReadyVideos || isAsking}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            id="ask-submit-button"
            style={{
              background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
              boxShadow: '0 4px 14px rgba(139, 92, 246, 0.4)',
            }}
            disabled={!hasReadyVideos || isAsking || !question.trim()}
          >
            {isAsking ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Searching...</span>
              </>
            ) : (
              <>
                <Search size={16} />
                <span>Ask RAG</span>
              </>
            )}
          </button>
        </div>

        {hasReadyVideos && (
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginTop: '0.85rem', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Suggestions:</span>
            {[
              "What is the main summary?",
              "What steps or recommendations were mentioned?",
              "What are the pros and cons discussed?",
            ].map((s) => (
              <button
                key={s}
                type="button"
                className="btn btn-secondary"
                style={{ padding: '0.2rem 0.55rem', fontSize: '0.72rem' }}
                onClick={() => handleSuggestion(s)}
                disabled={isAsking}
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </form>
    </div>
  );
}
