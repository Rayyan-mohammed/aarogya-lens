const BUILD_API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

// The live API is a Cloudflare tunnel whose address changes every time it restarts, so an
// address baked in at build time goes stale. On the deployed site the watchdog publishes the
// current address as api.json beside the main site; read it at runtime, falling back to the
// build-time value (also used for local dev). ?api=<url> overrides both.
let apiBasePromise: Promise<string> | null = null;

export function getApiBase(): Promise<string> {
  if (!apiBasePromise) apiBasePromise = resolveApiBase();
  return apiBasePromise;
}

async function resolveApiBase(): Promise<string> {
  if (typeof window === 'undefined') return BUILD_API_BASE;
  const override = new URLSearchParams(window.location.search).get('api');
  if (override) return override.replace(/\/+$/, '');
  if (['localhost', '127.0.0.1'].includes(window.location.hostname)) return BUILD_API_BASE;
  // basePath is e.g. /aarogya-lens/next; api.json lives one level up, beside the main site
  const siteRoot = (process.env.NEXT_PUBLIC_BASE_PATH || '').replace(/\/[^/]*$/, '');
  try {
    const res = await fetch(`${siteRoot}/api.json`, { cache: 'no-store' });
    if (res.ok) {
      const cfg = await res.json();
      if (typeof cfg.api === 'string' && /^https?:\/\//.test(cfg.api)) return cfg.api.replace(/\/+$/, '');
    }
  } catch {
    // fall through to the build-time address
  }
  return BUILD_API_BASE;
}

export interface HealthResponse {
  status: string;
  districts: number;
  states: number;
  columns: number;
}

export interface StateInfo {
  state: string;
  districts: number;
}

export interface StatesResponse {
  states: StateInfo[];
}

export interface QueryRequest {
  question: string;
  model: string;
  api_key?: string;
  state_filter?: string;
}

export interface QueryResponse {
  status: string;
  answer: string;
  tool_call_sequence: string[];
  chart_url?: string;
  model_used: string;
  error?: string;
}

export interface NationalSummaryResponse {
  indicators: Record<string, {
    description: string;
    national_mean: number | null;
    min: number | null;
    max: number | null;
  }>;
}

export interface CorrelationRequest {
  tool: 'correlation_finder';
  params: {
    indicator_a: string;
    indicator_b: string;
  };
}

export interface CorrelationResponse {
  status: string;
  pearson_r: number;
  spearman_r: number;
  pearson_p_value: number;
  n_districts: number;
  interpretation: string;
  indicator_a_description: string;
  indicator_b_description: string;
  scatter_data: Array<{
    district: string;
    state: string;
    x_value: number;
    y_value: number;
  }>;
  error?: string;
}

export async function checkApiHealth(): Promise<HealthResponse | null> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);
    const res = await fetch(`${await getApiBase()}/health`, { signal: controller.signal });
    clearTimeout(timeoutId);
    if (res.ok) {
      return await res.json();
    }
    return null;
  } catch {
    return null;
  }
}

export async function getStates(): Promise<StatesResponse | null> {
  try {
    const res = await fetch(`${await getApiBase()}/states`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function runQuery(request: QueryRequest): Promise<QueryResponse> {
  const res = await fetch(`${await getApiBase()}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return await res.json();
}

export async function getNationalSummary(): Promise<NationalSummaryResponse | null> {
  try {
    const res = await fetch(`${await getApiBase()}/national-summary`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function runCorrelation(params: CorrelationRequest['params']): Promise<CorrelationResponse> {
  const res = await fetch(`${await getApiBase()}/query/direct`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool: 'correlation_finder', params }),
  });
  return await res.json();
}