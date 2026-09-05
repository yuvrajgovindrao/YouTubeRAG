import React, { useState } from 'react';
import { Bot, Copy, Check, MessageSquare } from 'lucide-react';

export default function AnswerCard({ question, answer, sourcesCount }) {
  const [copied, setCopied] = useState(false);

  if (!answer) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className="glass-panel"
      style={{
        padding: '1.5rem',
        marginBottom: '1.5rem',
        borderLeft: '4px solid #ef4444',
      }}
    >
      {/* Question Header */}
      {question && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
          <MessageSquare size={16} color="#94a3b8" />
          <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#94a3b8' }}>
            {question}
          </h4>
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '6px',
              background: 'linear-gradient(135deg, #ef4444 0%, #8b5cf6 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Bot size={16} color="#fff" />
          </div>
          <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#f8fafc' }}>
            Grounded Transcript Synthesis
          </span>
          <span
            className="badge badge-ready"
            style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem' }}
          >
            {sourcesCount} Source{sourcesCount !== 1 ? 's' : ''} Retrieved
          </span>
        </div>

        <button
          onClick={handleCopy}
          className="btn btn-secondary"
          style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
          title="Copy answer"
        >
          {copied ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
          <span>{copied ? 'Copied!' : 'Copy'}</span>
        </button>
      </div>

      <div
        style={{
          fontSize: '0.95rem',
          lineHeight: 1.65,
          color: '#e2e8f0',
          whiteSpace: 'pre-wrap',
        }}
      >
        {answer}
      </div>
    </div>
  );
}
