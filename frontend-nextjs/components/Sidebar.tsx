'use client';

import { StateInfo } from '@/lib/api';

interface SidebarProps {
  states: StateInfo[];
  apiStatus: 'checking' | 'online' | 'offline';
  apiData: { districts: number; states: number; columns: number } | null;
  activeTab: 'chat' | 'explorer' | 'correlate';
  onTabChange: (tab: 'chat' | 'explorer' | 'correlate') => void;
  model: string;
  onModelChange: (model: string) => void;
  stateFilter: string;
  onStateFilterChange: (state: string) => void;
}

const MODEL_OPTIONS = [
  { value: 'groq', label: 'Groq (Llama 3.3 70B)' },
  { value: 'openrouter', label: 'OpenRouter (Gemini 2.5 Flash)' },
];

const EXAMPLE_QUERIES = [
  'Which 10 districts have the worst stunting rate nationally?',
  'Compare institutional delivery rates across Bihar, UP, and Kerala',
  'Is there a correlation between open defecation and child stunting?',
  'Which districts in Rajasthan have the highest anaemia in women?',
  'Show me the districts with best full vaccination coverage',
  'What is the child marriage rate in Uttar Pradesh districts?',
  'Which states have the highest caesarean section rates?',
];

export default function Sidebar({
  states,
  apiStatus,
  apiData,
  activeTab,
  onTabChange,
  model,
  onModelChange,
  stateFilter,
  onStateFilterChange,
}: SidebarProps) {
  const handleTabClick = (tab: 'chat' | 'explorer' | 'correlate') => {
    onTabChange(tab);
  };

  const setQuery = (text: string) => {
    // This will be handled by the parent via a context or callback
    // For now, we'll use a custom event
    window.dispatchEvent(new CustomEvent('set-query', { detail: text }));
    handleTabClick('chat');
  };

  return (
    <aside className="sidebar">
      {/* Model selector */}
      <div className="sidebar-section">
        <h3>LLM Model</h3>
        <select
          className="select-input"
          value={model}
          onChange={(e) => onModelChange(e.target.value)}
        >
          {MODEL_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* State filter */}
      <div className="sidebar-section">
        <h3>State Filter (optional)</h3>
        <select
          className="select-input state-select"
          value={stateFilter}
          onChange={(e) => onStateFilterChange(e.target.value)}
        >
          <option value="">All India</option>
          {states.map((s) => (
            <option key={s.state} value={s.state}>
              {s.state} ({s.districts})
            </option>
          ))}
        </select>
      </div>

      {/* Example queries */}
      <div className="sidebar-section">
        <h3>Example Queries</h3>
        <div className="example-queries">
          {EXAMPLE_QUERIES.map((query, i) => (
            <button
              key={i}
              className="example-query"
              onClick={() => setQuery(query)}
            >
              {query}
            </button>
          ))}
        </div>
      </div>

      {/* Dataset stats */}
      <div className="sidebar-section">
        <h3>Dataset Stats</h3>
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-value">{apiData?.districts ?? 706}</div>
            <div className="stat-label">Districts</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{apiData?.states ?? 36}</div>
            <div className="stat-label">States/UTs</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{apiData?.columns ?? 448}</div>
            <div className="stat-label">Columns</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">19–21</div>
            <div className="stat-label">Survey Yr</div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="sidebar-section">
        <h3>Views</h3>
        <div className="tab-nav">
          <button
            className={`tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => handleTabClick('chat')}
          >
            Chat
          </button>
          <button
            className={`tab-btn ${activeTab === 'explorer' ? 'active' : ''}`}
            onClick={() => handleTabClick('explorer')}
          >
            Explorer
          </button>
          <button
            className={`tab-btn ${activeTab === 'correlate' ? 'active' : ''}`}
            onClick={() => handleTabClick('correlate')}
          >
            Correlate
          </button>
        </div>
      </div>
    </aside>
  );
}