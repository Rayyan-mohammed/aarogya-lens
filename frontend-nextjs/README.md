# BharatHealth Analyst - Next.js Frontend

Modern React frontend for the BharatHealth Analyst AI-powered health data analysis system.

## Features

- **Chat Interface** - Natural language queries over 706 districts of NFHS-5 data
- **Indicator Explorer** - Browse all 448 health indicators with national statistics
- **Correlation Explorer** - Statistical correlation analysis between any two indicators
- **Real-time Charts** - Interactive Plotly visualizations
- **Multi-LLM Support** - Groq, Claude, GPT-4o model selection
- **Dark Theme** - Professional dark UI with indigo/cyan accents

## Quick Start

### Prerequisites

- Node.js 18+
- Backend API running on `http://localhost:8000`

### Installation

```bash
cd frontend-nextjs
npm install
```

### Development

```bash
# Copy environment variables
cp .env.example .env.local

# Start development server
npm run dev
```

Frontend will be available at `http://localhost:3000`

### Production Build

```bash
npm run build
npm start
```

## Project Structure

```
frontend-nextjs/
├── app/
│   ├── globals.css       # Tailwind + custom styles
│   ├── layout.tsx        # Root layout
│   └── page.tsx          # Main page component
├── components/
│   ├── Sidebar.tsx       # Model selector, API key, examples, tabs
│   ├── ChatPanel.tsx     # Query interface & results
│   ├── ExplorerPanel.tsx # Indicator browser
│   ├── CorrelatePanel.tsx# Correlation tool
│   ├── ResultCard.tsx    # Individual result display
│   ├── LoadingCard.tsx   # Loading state
│   ├── ErrorCard.tsx     # Error display
│   └── WelcomeScreen.tsx # Landing screen
├── lib/
│   └── api.ts            # Backend API client
├── public/               # Static assets
├── .env.example          # Environment template
├── next.config.js        # Next.js config
├── tailwind.config.js    # Tailwind CSS config
├── tsconfig.json         # TypeScript config
└── package.json
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_BASE` | Backend API URL | `http://localhost:8000` |

## API Integration

The frontend communicates with the FastAPI backend via these endpoints:

- `GET /health` - Health check & dataset stats
- `GET /states` - List of states with district counts
- `GET /national-summary` - All indicators with national statistics
- `POST /query` - Main AI agent query endpoint
- `POST /query/direct` - Direct tool execution (correlation_finder)

## Components Overview

### Sidebar
- LLM model selection (Groq/Claude/GPT-4o)
- API key input (stored in memory only)
- State filter dropdown
- Example query buttons
- Dataset stats cards
- Tab navigation (Chat/Explorer/Correlate)

### ChatPanel
- Query input with Enter-to-submit
- Loading animation with step indicators
- Result history with newest-first
- Tool chain visualization
- Chart embedding via iframe

### ExplorerPanel
- Grid of all 448 indicators
- Cluster badges (nutrition, anaemia, maternal, etc.)
- National mean, min/max values
- Click to auto-populate query

### CorrelatePanel
- Two indicator dropdowns
- Pearson & Spearman correlation
- Scatter plot with Plotly
- Statistical interpretation

## Styling

Uses Tailwind CSS with custom design tokens matching the original vanilla JS frontend:

- Dark background (`#060b18`)
- Card background (`#111d35`)
- Indigo primary (`#6366f1`)
- Cyan accent (`#22d3ee`)
- Inter font for UI, JetBrains Mono for code/numbers

## Deployment

### Docker (Standalone)

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
```

Add `output: 'standalone'` to `next.config.js` (already configured).

### Vercel

1. Connect repository to Vercel
2. Set `NEXT_PUBLIC_API_BASE` environment variable
3. Deploy

## Development Notes

- Uses React 18 with Next.js 14 App Router
- Client components marked with `'use client'`
- Plotly.js for charts (SSR-compatible via dynamic import)
- Custom event system for cross-component communication
- All API calls use fetch with proper TypeScript types