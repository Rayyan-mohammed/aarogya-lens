'use client';

import { useEffect, useRef } from 'react';
import React from 'react';
import { QueryResponse } from '@/lib/api';

interface ResultCardProps {
  question: string;
  data: QueryResponse;
  latency: string;
}

const escHtml = (s: string) =>
  String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

// Escape the raw answer first — it's LLM output rendered via dangerouslySetInnerHTML,
// so anything not explicitly turned into one of our own tags below must stay inert text.
// (.replace() with a function that returns JSX doesn't work — String.replace always
// stringifies the return value, which silently corrupted the formatting before.)
const formatAnswer = (text: string) => {
  if (!text) return '';
  return escHtml(text)
    .replace(/```json\n?([\s\S]*?)```/g, (_, code) =>
      `<div style="background:rgba(99,102,241,0.05);border:1px solid rgba(99,102,241,0.15);border-radius:6px;padding:12px;margin:8px 0;font-family:'JetBrains Mono',monospace;font-size:0.78rem;color:var(--indigo-light);overflow-x:auto;white-space:pre;">${code}</div>`
    )
    .replace(/\*\*(.*?)\*\*/g, (_, bold) => `<strong style="color:var(--text-1)">${bold}</strong>`)
    .replace(/`([^`]+)`/g, (_, code) => `<code>${code}</code>`);
};

export default function ResultCard({ question, data, latency }: ResultCardProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartUrl = data.chart_url;

  useEffect(() => {
    if (chartUrl && chartRef.current) {
      // The chart is embedded via iframe in the backend response
    }
  }, [chartUrl]);

  const toolChainHtml = data.tool_call_sequence && data.tool_call_sequence.length > 0 ? (
    <div className="tool-chain">
      <span style={{ fontSize: '0.7rem', color: 'var(--text-3)' }}>Tools used:</span>
      {data.tool_call_sequence.map((t, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span className="tool-chain-arrow">→</span>}
          <span className="tool-chip">{t}</span>
        </React.Fragment>
      ))}
    </div>
  ) : null;

  return (
    <div className="result-card animate-slide-in">
      <div className="result-header">
        <div className="result-question">💬 {escHtml(question)}</div>
        <div className="result-meta">
          <span className="badge badge-indigo">{data.model_used}</span>
          <span className="badge badge-cyan">{latency}s</span>
        </div>
      </div>
      <div className="result-body">
        {toolChainHtml}
        <div className="answer-text" dangerouslySetInnerHTML={{ __html: formatAnswer(data.answer || '') }} />
        {chartUrl && (
          <div className="chart-embed">
            <iframe
              src={`${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'}${chartUrl}`}
              loading="lazy"
              style={{ width: '100%', height: '100%', border: 'none' }}
            />
          </div>
        )}
      </div>
    </div>
  );
}