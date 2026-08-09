'use client';

import { useState } from 'react';
import { runCorrelation, CorrelationResponse } from '@/lib/api';
import Plot from 'react-plotly.js';

const INDICATOR_OPTIONS = [
  { value: 'stępu', label: 'Stunting (%)' },
  { value: 'wasting_pct', label: 'Wasting (%)' },
  { value: 'anaemia_children_pct', label: 'Anaemia in Children (%)' },
  { value: 'anaemia_all_women_pct', label: 'Anaemia in Women (%)' },
  { value: 'institutional_delivery_pct', label: 'Institutional Delivery (%)' },
  { value: 'fully_vaccinated_recall_pct', label: 'Full Vaccination (%)' },
  { value: 'improved_sanitation_pct', label: 'Improved Sanitation (%)' },
  { value: 'women_literacy_pct', label: 'Women Literacy (%)' },
  { value: 'child_marriage_pct', label: 'Child Marriage (%)' },
  { value: 'anc_4plus_visits_pct', label: 'ANC 4+ Visits (%)' },
  { value: 'clean_cooking_fuel_pct', label: 'Clean Cooking Fuel (%)' },
];

export default function CorrelatePanel() {
  const [indicatorA, setIndicatorA] = useState('stunting_pct');
  const [indicatorB, setIndicatorB] = useState('improved_sanitation_pct');
  const [result, setResult] = useState<CorrelationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCorrelation = async () => {
    if (indicatorA === indicatorB) {
      setError('Please select two different indicators');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await runCorrelation({ indicator_a: indicatorA, indicator_b: indicatorB });
      if (data.status === 'success') {
        setResult(data);
      } else {
        setError(data.error || 'Correlation failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error running correlation');
    } finally {
      setLoading(false);
    }
  };

  const getIndicatorLabel = (value: string) => {
    return INDICATOR_OPTIONS.find(opt => opt.value === value)?.label || value;
  };

  return (
    <div className="explorer-panel">
      <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '1.5rem' }}>Correlation Explorer</h2>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '1.5rem' }}>
        <div>
          <label style={{ fontSize: '0.75rem', color: 'var(--text-3)', display: 'block', marginBottom: '4px' }}>Indicator A</label>
          <select
            className="select-input state-select"
            value={indicatorA}
            onChange={(e) => setIndicatorA(e.target.value)}
          >
            {INDICATOR_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={{ fontSize: '0.75rem', color: 'var(--text-3)', display: 'block', marginBottom: '4px' }}>Indicator B</label>
          <select
            className="select-input state-select"
            value={indicatorB}
            onChange={(e) => setIndicatorB(e.target.value)}
          >
            {INDICATOR_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        <div style={{ display: 'flex', alignItems: 'flexEnd' }}>
          <button
            className="send-btn"
            style={{ width: '100%', height: '38px', padding: 0 }}
            onClick={handleCorrelation}
            disabled={loading}
          >
            {loading ? 'Running…' : 'Run Correlation'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ color: 'var(--rose)', padding: '1rem' }}>
          {error}
        </div>
      )}

      {result && (
        <div style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
          padding: '1.25rem',
          marginBottom: '1rem'
        }}>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: '12px',
            marginBottom: '1rem'
          }}>
            <div className="stat-card">
              <div className="stat-value" style={{
                fontSize: '1.6rem',
                color: Math.abs(result.pearson_r) > 0.5 ? 'var(--emerald)' : 'var(--amber)'
              }}>
                {result.pearson_r}
              </div>
              <div className="stat-label">Pearson r</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ fontSize: '1.6rem', color: 'var(--cyan)' }}>
                {result.spearman_r}
              </div>
              <div className="stat-label">Spearman ρ</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ fontSize: '1.1rem', color: 'var(--text-2)' }}>
                {result.pearson_p_value < 0.001 ? '<0.001' : result.pearson_p_value}
              </div>
              <div className="stat-label">p-value</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ fontSize: '1.1rem', color: 'var(--text-2)' }}>
                {result.n_districts}
              </div>
              <div className="stat-label">Districts</div>
            </div>
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-2)', marginBottom: '1rem' }}>
            {result.interpretation}
          </p>
          <div id="corr-chart" style={{ height: '380px' }}>
            {result.scatter_data && result.scatter_data.length > 0 && (
              <Plot
                data={[
                  {
                    x: result.scatter_data.map(d => d.x_value),
                    y: result.scatter_data.map(d => d.y_value),
                    text: result.scatter_data.map(d => `${d.district}, ${d.state}`),
                    mode: 'markers',
                    marker: { color: '#6366f1', size: 6, opacity: 0.7 },
                    type: 'scatter',
                    hovertemplate: '<b>%{text}</b><br>X: %{x:.1f}%<br>Y: %{y:.1f}%<extra></extra>',
                  },
                ]}
                layout={{
                  paper_bgcolor: '#111d35',
                  plot_bgcolor: '#0d1526',
                  font: { family: 'Inter', color: '#e2e8f0' },
                  title: {
                    text: `${result.indicator_a_description} vs ${result.indicator_b_description}`,
                    font: { size: 14 },
                  },
                  xaxis: {
                    title: result.indicator_a_description,
                    gridcolor: 'rgba(99,102,241,0.1)',
                  },
                  yaxis: {
                    title: result.indicator_b_description,
                    gridcolor: 'rgba(99,102,241,0.1)',
                  },
                  margin: { l: 60, r: 20, t: 50, b: 60 },
                  showlegend: false,
                }}
                config={{ responsive: true, displayModeBar: false }}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}