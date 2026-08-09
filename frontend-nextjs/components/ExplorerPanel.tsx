'use client';

import { useState, useEffect } from 'react';
import { getNationalSummary, NationalSummaryResponse } from '@/lib/api';

const CLUSTER_ICONS: Record<string, string> = {
  child_nutrition: '🍎',
  anaemia: '🩸',
  maternal_health: '🤱',
  vaccination: '💉',
  sanitation: '🚿',
  ncd: '❤️',
  women_empowerment: '👩',
  family_planning: '🏠',
  lifestyle: '🚬',
};

const getCluster = (col: string): string => {
  if (col.includes('anaemia')) return 'anaemia';
  if (col.includes('stunt') || col.includes('wast') || col.includes('underweight')) return 'child_nutrition';
  if (col.includes('delivery') || col.includes('anc') || col.includes('postnatal')) return 'maternal_health';
  if (col.includes('vaccin')) return 'vaccination';
  if (col.includes('sanit') || col.includes('water') || col.includes('cook')) return 'sanitation';
  if (col.includes('sugar') || col.includes('hypert') || col.includes('overweight')) return 'ncd';
  return 'other';
};

const CLUSTER_LABELS: Record<string, string> = {
  child_nutrition: 'Child Nutrition',
  anaemia: 'Anaemia',
  maternal_health: 'Maternal Health',
  vaccination: 'Vaccination',
  sanitation: 'Sanitation',
  ncd: 'NCD',
  women_empowerment: 'Women Empowerment',
  family_planning: 'Family Planning',
  lifestyle: 'Lifestyle',
};

export default function ExplorerPanel() {
  const [data, setData] = useState<NationalSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const result = await getNationalSummary();
        if (result) {
          setData(result);
        } else {
          setError('Could not load data — make sure backend is running.');
        }
      } catch {
        setError('Could not load data — make sure backend is running.');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return (
      <div className="explorer-panel">
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '1rem' }}>National Indicator Overview</h2>
        <div className="explorer-grid">
          <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--text-3)', padding: '2rem' }}>
            Loading indicators…
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="explorer-panel">
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '1rem' }}>National Indicator Overview</h2>
        <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--rose)', padding: '2rem' }}>
          {error}
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const indicators = data.indicators;
  const entries = Object.entries(indicators);

  return (
    <div className="explorer-panel">
      <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '1rem' }}>National Indicator Overview</h2>
      <div className="explorer-grid">
        {entries.map(([col, info]) => {
          const cluster = getCluster(col);
          const icon = CLUSTER_ICONS[cluster] || '📊';
          const clusterLabel = CLUSTER_LABELS[cluster] || cluster;
          const val = info.national_mean !== null ? `${info.national_mean}%` : 'N/A';
          const range = info.min !== null ? `${info.min}% – ${info.max}%` : '';

          return (
            <div
              key={col}
              className="indicator-card"
              onClick={() => {
                window.dispatchEvent(new CustomEvent('set-query', { detail: `Analyse ${info.description} across all districts` }));
                window.dispatchEvent(new CustomEvent('switch-tab', { detail: 'chat' }));
              }}
            >
              <div className={`cluster-badge cluster-${cluster}`}>
                {icon} {clusterLabel}
              </div>
              <h4>{info.description}</h4>
              <div className="ind-val">{val}</div>
              <div className="ind-label">National avg · Range: {range}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}