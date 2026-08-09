'use client';

interface ErrorCardProps {
  question: string;
  error: string;
}

const escHtml = (s: string) =>
  String(s)
    .replace(/&/g, '&')
    .replace(/</g, '<')
    .replace(/>/g, '>')
    .replace(/"/g, '"')
    .replace(/'/g, ''');

export default function ErrorCard({ question, error }: ErrorCardProps) {
  return (
    <div className="result-card animate-slide-in">
      <div className="result-header">
        <div className="result-question">💬 {escHtml(question)}</div>
        <div className="result-meta">
          <span className="badge badge-rose">Error</span>
        </div>
      </div>
      <div className="result-body">
        <div className="error-card">
          <div className="error-title">⚠ Error</div>
          <div className="error-msg">{escHtml(error)}</div>
        </div>
      </div>
    </div>
  );
}