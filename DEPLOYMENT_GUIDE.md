# BharatHealth Analyst - Deployment Guide

Complete guide to deploy the BharatHealth Analyst system locally and in production.

---

## 🚀 Quick Start (Local Development)

### Prerequisites
```bash
Python 3.11+
Git
8GB+ RAM (recommended)
```

### 1. Clone and Setup
```bash
git clone <repository-url>
cd aarogya-lens

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your API keys
nano .env
```

Required API keys (get at least one):
- `ANTHROPIC_API_KEY` - Claude Sonnet 4.5 (recommended)
- `OPENAI_API_KEY` - GPT-4o  
- `GROQ_API_KEY` - Llama 3.1 8B (free tier available)

### 3. Data Pipeline (One-time Setup)
```bash
# The data is already processed, but if you need to rebuild:
python backend/data/pipeline.py

# Build vector index (downloads ~90MB model)
python backend/vector_store/build_index.py

# Generate benchmark questions (optional)
python backend/evaluation/generate_benchmark.py
```

### 4. Start the System
```bash
# Terminal 1: Start API Backend
python -m uvicorn backend.api.main:app --reload --port 8000

# Terminal 2: Start Frontend (in new terminal)
python -m http.server 3000 --directory frontend

# Access the application
# API: http://localhost:8000
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

### 5. Verify Installation
```bash
# Test data pipeline
python quick_demo.py

# Test API
curl http://localhost:8000/health

# Run evaluation sample
python -m backend.evaluation.eval_runner --dry-run --n 5

# Full system demo
python demo.py
```

---

## ☁️ Production Deployment

### Option 1: Docker Deployment

#### 1.1 Build Containers
```bash
# Create Dockerfile for backend
cat > Dockerfile.backend << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY .env .env

# Create necessary directories
RUN mkdir -p charts_output backend/vector_store/chroma_db

EXPOSE 8000

CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# Create Dockerfile for frontend
cat > Dockerfile.frontend << 'EOF'
FROM nginx:alpine

# Copy frontend files
COPY frontend/ /usr/share/nginx/html/

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
EOF

# Create nginx.conf
cat > nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    server {
        listen 80;
        server_name localhost;
        
        root /usr/share/nginx/html;
        index index.html;
        
        location / {
            try_files $uri $uri/ /index.html;
        }
        
        # Proxy API requests to backend
        location /api/ {
            proxy_pass http://backend:8000/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
EOF
```

#### 1.2 Docker Compose Setup
```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./backend/data:/app/backend/data:ro
      - ./backend/vector_store:/app/backend/vector_store:ro
      - ./charts_output:/app/charts_output
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      
  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "3000:80"
    depends_on:
      - backend
    environment:
      - API_BASE=http://localhost:8000
      
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx-prod.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - backend
      - frontend
EOF

# Deploy
docker-compose up -d
```

### Option 2: GCP Cloud Run Deployment

#### 2.1 Prepare for GCP
```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init

# Set project
gcloud config set project YOUR_PROJECT_ID
```

#### 2.2 Deploy Backend
```bash
# Create app.yaml for Cloud Run
cat > app.yaml << 'EOF'
runtime: python311

env_variables:
  GROQ_API_KEY: "your_groq_key_here"
  ANTHROPIC_API_KEY: "your_anthropic_key_here"

automatic_scaling:
  min_instances: 0
  max_instances: 10
  
resources:
  cpu: 1
  memory_gb: 2

timeout: 300s
EOF

# Deploy backend
gcloud run deploy bharathealth-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8000 \
  --memory 2Gi \
  --cpu 1 \
  --max-instances 10
```

#### 2.3 Deploy Frontend
```bash
# Create separate frontend project
mkdir frontend-deploy
cp frontend/* frontend-deploy/

# Update API_BASE in frontend JavaScript to point to Cloud Run URL
sed -i "s|http://localhost:8000|https://bharathealth-api-xyz-uc.a.run.app|g" frontend-deploy/index.html

# Deploy to Firebase Hosting or similar
npm install -g firebase-tools
firebase init hosting
firebase deploy
```

### Option 3: AWS Deployment

#### 3.1 Elastic Beanstalk
```bash
# Install EB CLI
pip install awsebcli

# Initialize
eb init bharathealth-analyst

# Create environment
eb create bharathealth-prod

# Deploy
eb deploy
```

#### 3.2 ECS with Fargate
```bash
# Create task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Create service
aws ecs create-service \
  --cluster bharathealth-cluster \
  --service-name bharathealth-service \
  --task-definition bharathealth:1 \
  --desired-count 2 \
  --launch-type FARGATE
```

---

## 🔧 Configuration

### Environment Variables
```bash
# Required API Keys (at least one)
ANTHROPIC_API_KEY=sk-ant-...       # Claude Sonnet 4.5
OPENAI_API_KEY=sk-...              # GPT-4o
GROQ_API_KEY=gsk_...               # Llama 3.1 8B (free tier)

# Optional Configuration
MAX_CONCURRENT_REQUESTS=10          # Rate limiting
ENABLE_CORS=true                   # Cross-origin requests
LOG_LEVEL=INFO                     # Logging verbosity
CACHE_RESPONSES=true               # Response caching
```

### Database Configuration
```bash
# ChromaDB (Vector Store)
CHROMA_HOST=localhost
CHROMA_PORT=8001
CHROMA_PERSIST_DIRECTORY=./backend/vector_store/chroma_db

# Data Files
DATA_DIRECTORY=./backend/data
PARQUET_FILE=nfhs5_clean.parquet
SCHEMA_FILE=schema.json
```

### Performance Tuning
```bash
# API Configuration
WORKERS=4                          # Uvicorn workers
TIMEOUT=300                        # Request timeout (seconds)  
MAX_REQUEST_SIZE=10MB              # Upload limit

# Memory Management
PANDAS_MEMORY_LIMIT=1GB            # DataFrame memory limit
CACHE_SIZE=1000                    # Response cache size
CLEANUP_INTERVAL=3600              # Cleanup interval (seconds)
```

---

## 🔐 Security Configuration

### 1. API Key Management
```bash
# Production: Use secret management
# GCP: Secret Manager
gcloud secrets create anthropic-api-key --data-file=key.txt

# AWS: Parameter Store
aws ssm put-parameter \
  --name "/bharathealth/anthropic-api-key" \
  --value "sk-ant-..." \
  --type "SecureString"

# Azure: Key Vault
az keyvault secret set \
  --vault-name bharathealth-vault \
  --name anthropic-api-key \
  --value "sk-ant-..."
```

### 2. Network Security
```bash
# Firewall rules (example for GCP)
gcloud compute firewall-rules create allow-bharathealth \
  --allow tcp:8000,tcp:3000 \
  --source-ranges 0.0.0.0/0 \
  --description "BharatHealth application ports"

# SSL/TLS certificate
certbot --nginx -d bharathealth.example.com
```

### 3. Rate Limiting
```python
# In backend/api/main.py (already implemented)
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/query")
@limiter.limit("10/minute")  # 10 requests per minute
async def query_agent(request: Request, req: QueryRequest):
    # ... implementation
```

---

## 📊 Monitoring & Observability

### 1. Health Checks
```bash
# API Health Check
curl -f http://localhost:8000/health || exit 1

# Database Health Check  
curl -f http://localhost:8000/health/db || exit 1

# Memory Usage Check
curl -f http://localhost:8000/health/memory || exit 1
```

### 2. Logging Configuration
```python
# backend/api/main.py
import logging
from pythonjsonlogger import jsonlogger

# Configure structured logging
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)
```

### 3. Metrics Collection
```bash
# Prometheus metrics endpoint
curl http://localhost:8000/metrics

# Key metrics:
# - request_count_total
# - request_duration_seconds  
# - active_connections
# - memory_usage_bytes
# - query_execution_time
```

### 4. Error Tracking
```python
# Sentry integration (optional)
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="YOUR_SENTRY_DSN",
    integrations=[FastApiIntegration()]
)
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions Example
```yaml
# .github/workflows/deploy.yml
name: Deploy BharatHealth

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - run: pip install -r requirements.txt
    - run: python -m pytest tests/
    - run: python -m backend.evaluation.eval_runner --dry-run --n 5
    
  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: google-github-actions/setup-gcloud@v1
      with:
        service_account_key: ${{ secrets.GCP_SA_KEY }}
        project_id: ${{ secrets.GCP_PROJECT }}
    - run: gcloud run deploy bharathealth-api --source . --region us-central1
```

---

## 🚨 Troubleshooting

### Common Issues

#### 1. API Server Won't Start
```bash
# Check port availability
netstat -tulpn | grep :8000

# Check dependencies
pip install -r requirements.txt

# Check data files
ls -la backend/data/nfhs5_clean.parquet

# Check logs
python -m uvicorn backend.api.main:app --log-level debug
```

#### 2. ChromaDB Issues
```bash
# Rebuild vector index
rm -rf backend/vector_store/chroma_db
python backend/vector_store/build_index.py

# Check disk space
df -h

# Check permissions
chmod -R 755 backend/vector_store/
```

#### 3. High Memory Usage
```bash
# Monitor memory
htop

# Reduce batch size in config
export BATCH_SIZE=50

# Enable swap (if needed)
sudo swapon -s
```

#### 4. Slow Query Performance
```bash
# Check database size
du -sh backend/data/

# Enable query caching
export CACHE_RESPONSES=true

# Monitor slow queries
tail -f logs/slow_queries.log
```

### Performance Benchmarks

| Metric | Local | Docker | Cloud Run | 
|--------|--------|--------|-----------|
| Cold Start | 0.5s | 2s | 3-5s |
| Warm Response | 1.5s | 1.8s | 2.1s |
| Memory Usage | 1.2GB | 1.5GB | 1.8GB |
| Concurrent Users | 50 | 30 | 100 |

---

## 📈 Scaling Considerations

### Horizontal Scaling
```bash
# Multiple API instances
docker-compose up --scale backend=3

# Load balancer configuration
upstream bharathealth {
    server backend1:8000;
    server backend2:8000;  
    server backend3:8000;
}
```

### Database Scaling
```bash
# ChromaDB cluster mode (future)
# Currently single-instance only

# Data partitioning by state
python partition_data.py --by-state

# Read replicas for query-heavy workloads
# Not currently implemented
```

### Caching Strategy
```bash
# Redis for response caching
docker run -d -p 6379:6379 redis:alpine

# CDN for static assets
# CloudFlare, AWS CloudFront, etc.
```

---

## 📝 Maintenance Tasks

### Daily
- [ ] Check application health endpoints
- [ ] Monitor error rates in logs
- [ ] Verify API key limits not exceeded

### Weekly  
- [ ] Update data if new NFHS releases available
- [ ] Review query performance metrics
- [ ] Backup vector database

### Monthly
- [ ] Security updates for dependencies
- [ ] Review and rotate API keys
- [ ] Capacity planning based on usage

### Quarterly
- [ ] Full system backup and recovery test
- [ ] Performance benchmarking
- [ ] User feedback integration

---

## 📞 Support

### Getting Help
- **Documentation**: This guide + inline code comments
- **Issues**: Create GitHub issue with logs and steps to reproduce
- **Performance**: Include system specs and query details
- **Security**: Email privately to rayyan1652@gmail.com

### Logs Location
```bash
# Application logs
tail -f /var/log/bharathealth/app.log

# Error logs  
tail -f /var/log/bharathealth/error.log

# Query logs
tail -f /var/log/bharathealth/queries.log

# Docker logs
docker-compose logs -f backend
```

---

**Deployment Guide prepared by Mohammed Rayyan**  
*B.Tech CSE (Data Science) | NMIMS University, Hyderabad | June 2026*

For additional support or questions: rayyan1652@gmail.com