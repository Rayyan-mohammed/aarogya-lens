FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/

EXPOSE 8000

# Render (and similar PaaS hosts) inject $PORT at runtime instead of using a fixed
# port, so this needs shell form to substitute it; falls back to 8000 locally.
CMD uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
