'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import dynamic from 'next/dynamic';
import Sidebar from '@/components/Sidebar';
import ChatPanel from '@/components/ChatPanel';
import ExplorerPanel from '@/components/ExplorerPanel';
import CorrelatePanel from '@/components/CorrelatePanel';
import { checkApiHealth, getStates, HealthResponse, StateInfo } from '@/lib/api';

const Plot = dynamic(() => import('react-plotly.js').then(mod => mod.default), { ssr: false });

export default function HomePage() {
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [apiData, setApiData] = useState<HealthResponse | null>(null);
  const [states, setStates] = useState<StateInfo[]>([]);
  const [activeTab, setActiveTab] = useState<'chat' | 'explorer' | 'correlate'>('chat');
  const [model, setModel] = useState('groq');
  const [apiKey, setApiKey] = useState('');
  const [stateFilter, setStateFilter] = useState('');

  useEffect(() => {
    const init = async () => {
      const health = await checkApiHealth();
      if (health) {
        setApiStatus('online');
        setApiData(health);
      } else {
        setApiStatus('offline');
      }
      const statesData = await getStates();
      if (statesData) {
        setStates(statesData.states);
      }
    };
    init();

    // ExplorerPanel dispatches this when you click an indicator card, to jump to Chat
    const handleSwitchTab = (e: CustomEvent<'chat' | 'explorer' | 'correlate'>) => setActiveTab(e.detail);
    window.addEventListener('switch-tab', handleSwitchTab as EventListener);
    return () => window.removeEventListener('switch-tab', handleSwitchTab as EventListener);
  }, []);

  return (
    <div className="app-layout">
      <header className="header">
        <a className="logo" href="#">
          <div className="logo-icon">B</div>
          <div>
            <div className="logo-text">BharatHealth Analyst</div>
            <div className="logo-sub">NFHS-5 · 706 Districts · AI-Powered</div>
          </div>
        </a>
        <div className="header-badges flex gap-2">
          <span className="badge badge-indigo">NFHS-5 (2019–21)</span>
          <span className="badge badge-cyan">706 Districts</span>
          <span className={`badge ${apiStatus === 'online' ? 'badge-emerald' : 'badge-indigo'}`} id="api-status">
            {apiStatus === 'checking' ? 'Connecting…' : apiStatus === 'online' ? `API Online · ${apiData?.districts} Districts` : 'API Offline (start backend)'}
          </span>
        </div>
      </header>

      <main className="main-layout">
        <Sidebar
          states={states}
          apiStatus={apiStatus}
          apiData={apiData}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          model={model}
          onModelChange={setModel}
          apiKey={apiKey}
          onApiKeyChange={setApiKey}
          stateFilter={stateFilter}
          onStateFilterChange={setStateFilter}
        />
        <div className="content">
          {activeTab === 'chat' && <ChatPanel model={model} apiKey={apiKey} stateFilter={stateFilter} />}
          {activeTab === 'explorer' && <ExplorerPanel />}
          {activeTab === 'correlate' && <CorrelatePanel />}
        </div>
      </main>
    </div>
  );
}