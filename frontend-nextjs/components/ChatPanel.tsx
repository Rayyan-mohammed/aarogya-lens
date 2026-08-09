'use client';

import { useState, useEffect, useRef, FormEvent } from 'react';
import { runQuery, QueryRequest, QueryResponse } from '@/lib/api';
import ResultCard from './ResultCard';
import LoadingCard from './LoadingCard';
import ErrorCard from './ErrorCard';
import WelcomeScreen from './WelcomeScreen';

interface ChatPanelProps {
  model: string;
  apiKey: string;
  stateFilter: string;
}

export default function ChatPanel({ model, apiKey, stateFilter }: ChatPanelProps) {
  const [question, setQuestion] = useState('');
  const [results, setResults] = useState<Array<{
    id: string;
    type: 'result' | 'error' | 'loading';
    question: string;
    data?: QueryResponse;
    error?: string;
    latency?: string;
  }>>([]);
  const [isLoading, setIsLoading] = useState(false);
  const resultsListRef = useRef<HTMLDivElement>(null);
  const queryInputRef = useRef<HTMLTextAreaElement>(null);

  // Listen for set-query events from sidebar
  useEffect(() => {
    const handler = (e: CustomEvent<string>) => {
      setQuestion(e.detail);
      queryInputRef.current?.focus();
    };
    window.addEventListener('set-query', handler as EventListener);
    return () => window.removeEventListener('set-query', handler as EventListener);
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isLoading) return;

    const currentQuestion = question.trim();
    const loadingId = `loading-${Date.now()}`;

    setIsLoading(true);
    setResults((prev) => [
      { id: loadingId, type: 'loading', question: currentQuestion },
      ...prev,
    ]);
    setQuestion('');

    const startTime = Date.now();

    try {
      const request: QueryRequest = {
        question: currentQuestion,
        model,
        api_key: apiKey || undefined,
        state_filter: stateFilter || undefined,
      };

      const data = await runQuery(request);
      const latency = ((Date.now() - startTime) / 1000).toFixed(1);

      setResults((prev) =>
        prev.map((r) =>
          r.id === loadingId
            ? { ...r, type: data.status === 'success' ? 'result' : 'error', data, error: data.error, latency }
            : r
        )
      );
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setResults((prev) =>
        prev.map((r) =>
          r.id === loadingId
            ? { ...r, type: 'error', error: errorMsg }
            : r
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="content">
      {/* Query bar */}
      <div className="query-bar">
        <form className="query-form" onSubmit={handleSubmit}>
          <textarea
            ref={queryInputRef}
            className="query-input"
            id="query-input"
            placeholder="Ask anything about India's district health data… e.g. Which districts in Bihar have the highest stunting rates?"
            rows={2}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          ></textarea>
          <button
            className="send-btn"
            type="submit"
            disabled={isLoading || !question.trim()}
          >
            {isLoading ? (
              <>
                <div className="spinner" />
                <span id="send-label">Thinking…</span>
              </>
            ) : (
              <>
                <span id="send-icon">
                  <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </span>
                <span id="send-label">Analyse</span>
              </>
            )}
          </button>
        </form>
      </div>

      {/* Results */}
      <div className="results-panel" id="results-panel">
        {results.length === 0 && <WelcomeScreen onSetQuery={(q) => setQuestion(q)} />}
        <div ref={resultsListRef} id="results-list">
          {results.map((result) => (
            <div key={result.id}>
              {result.type === 'loading' && <LoadingCard />}
              {result.type === 'result' && result.data && (
                <ResultCard
                  question={result.question}
                  data={result.data}
                  latency={result.latency || '0'}
                />
              )}
              {result.type === 'error' && (
                <ErrorCard question={result.question} error={result.error || 'Unknown error'} />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}