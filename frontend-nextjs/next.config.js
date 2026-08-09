/** @type {import('next').NextConfig} */
// Static export for GitHub Pages — the app is pure client-side (fetches the FastAPI
// backend directly), so no Next.js server is actually needed. GH_PAGES_BASE_PATH is
// only set by the deploy script, so `npm run dev`/`build` locally stay at root.
const basePath = process.env.GH_PAGES_BASE_PATH || '';

const nextConfig = {
  output: 'export',
  basePath,
  images: { unoptimized: true },
  experimental: { cpus: 1, workerThreads: false },
};

module.exports = nextConfig;