'use client';

export default function LoadingCard() {
  return (
    <div className="loading-card animate-pulse">
      <div className="loading-spinner" />
      <div className="loading-text">Analysing your question…</div>
      <div className="loading-steps">
        <div className="loading-step active">
          <div className="loading-dot" />
          Parsing query
        </div>
        <div className="loading-step">
          <div className="loading-dot" />
          Running tools
        </div>
        <div className="loading-step">
          <div className="loading-dot" />
          Generating answer
        </div>
      </div>
    </div>
  );
}