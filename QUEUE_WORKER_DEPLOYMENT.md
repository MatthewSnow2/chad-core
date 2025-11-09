# Queue Worker Deployment Guide

Quick guide to deploy the chad-core queue worker in production.

## Prerequisites

- Redis 6.0+ running and accessible
- PostgreSQL 12+ with chad_core database
- Python 3.11+ with dependencies installed
- systemd (Linux) or equivalent process manager

## Quick Start (Local Development)

### 1. Start Redis

```bash
# Using Docker
docker run -d --name redis -p 6379:6379 redis:latest

# Or using local Redis
redis-server
```

### 2. Set Environment Variables

Create `.env` file in project root:

```bash
# Redis
REDIS_URL=redis://localhost:6379/0
QUEUE_STREAM_NAME=chad:jobs
QUEUE_CONSUMER_GROUP=chad-workers
QUEUE_CONSUMER_NAME=worker-dev-1
QUEUE_MAX_RETRIES=3
QUEUE_RETRY_DELAY_SECONDS=60

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/chad_core

# Webhooks
WEBHOOK_TIMEOUT_SECONDS=10
WEBHOOK_MAX_RETRIES=3
WEBHOOK_RETRY_BACKOFF_BASE=2

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### 3. Run Worker

```bash
# Development mode
python -m apps.queue_worker.main

# Or with environment file
python -m apps.queue_worker.main
```

### 4. Test the Queue

```bash
# Start API server (in another terminal)
uvicorn apps.core_api.main:app --reload --port 8000

# Make a background request
curl -X POST http://localhost:8000/act?background=true \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "actor": "test-user",
    "goal": "Test background job",
    "context": {}
  }'

# Poll status
curl http://localhost:8000/runs/{RUN_ID}/status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Production Deployment

### 1. Create Dedicated User

```bash
sudo useradd -r -s /bin/false chad
sudo mkdir -p /opt/chad-core
sudo chown chad:chad /opt/chad-core
```

### 2. Install Application

```bash
# Clone repository
cd /opt/chad-core
git clone https://github.com/your-org/chad-core.git .
git checkout agent/queue-worker

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
# or with Poetry
poetry install --only main
```

### 3. Configure Environment

```bash
# Create environment file
sudo mkdir -p /etc/chad-core
sudo vim /etc/chad-core/queue-worker.env
```

Add production configuration:

```bash
# Redis (production)
REDIS_URL=redis://redis.internal:6379/0
QUEUE_STREAM_NAME=chad:jobs
QUEUE_CONSUMER_GROUP=chad-workers
QUEUE_CONSUMER_NAME=worker-prod-${HOSTNAME}
QUEUE_MAX_RETRIES=3
QUEUE_RETRY_DELAY_SECONDS=60
QUEUE_DEAD_LETTER_STREAM=chad:jobs:dlq
QUEUE_POLL_INTERVAL_MS=1000
QUEUE_BLOCK_MS=5000

# Database (production)
DATABASE_URL=postgresql+asyncpg://chad_user:SECURE_PASSWORD@postgres.internal:5432/chad_core

# Webhooks
WEBHOOK_TIMEOUT_SECONDS=10
WEBHOOK_MAX_RETRIES=3
WEBHOOK_RETRY_BACKOFF_BASE=2

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
ENVIRONMENT=production
```

### 4. Install systemd Service

```bash
# Copy service file
sudo cp infra/deployment/systemd/chad-queue-worker.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable chad-queue-worker

# Start service
sudo systemctl start chad-queue-worker

# Check status
sudo systemctl status chad-queue-worker
```

### 5. Verify Deployment

```bash
# Check service is running
sudo systemctl status chad-queue-worker

# View logs
sudo journalctl -u chad-queue-worker -f

# Check Redis consumer group
redis-cli XINFO GROUPS chad:jobs

# Check for consumers
redis-cli XINFO CONSUMERS chad:jobs chad-workers
```

## Horizontal Scaling

### Method 1: Systemd Instance Template

Edit service file to use instance template:

```bash
# Copy to instance template
sudo cp /etc/systemd/system/chad-queue-worker.service \
        /etc/systemd/system/chad-queue-worker@.service

# Edit to use instance name
sudo vim /etc/systemd/system/chad-queue-worker@.service
```

Change:
```ini
[Service]
Environment="QUEUE_CONSUMER_NAME=worker-%i"
```

Start multiple instances:
```bash
sudo systemctl start chad-queue-worker@1
sudo systemctl start chad-queue-worker@2
sudo systemctl start chad-queue-worker@3

sudo systemctl enable chad-queue-worker@1
sudo systemctl enable chad-queue-worker@2
sudo systemctl enable chad-queue-worker@3
```

### Method 2: Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  worker-1:
    image: chad-core:latest
    command: python -m apps.queue_worker.main
    environment:
      - QUEUE_CONSUMER_NAME=worker-1
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=postgresql+asyncpg://...
    depends_on:
      - redis
      - postgres
    restart: always

  worker-2:
    image: chad-core:latest
    command: python -m apps.queue_worker.main
    environment:
      - QUEUE_CONSUMER_NAME=worker-2
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=postgresql+asyncpg://...
    depends_on:
      - redis
      - postgres
    restart: always

  worker-3:
    image: chad-core:latest
    command: python -m apps.queue_worker.main
    environment:
      - QUEUE_CONSUMER_NAME=worker-3
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=postgresql+asyncpg://...
    depends_on:
      - redis
      - postgres
    restart: always
```

### Method 3: Kubernetes

Create deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: chad-queue-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: chad-queue-worker
  template:
    metadata:
      labels:
        app: chad-queue-worker
    spec:
      containers:
      - name: worker
        image: chad-core:latest
        command: ["python", "-m", "apps.queue_worker.main"]
        env:
        - name: QUEUE_CONSUMER_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: chad-secrets
              key: redis-url
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: chad-secrets
              key: database-url
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

## Monitoring Setup

### 1. Prometheus Metrics

Add metrics endpoint to worker (future enhancement):

```python
from prometheus_client import Counter, Gauge, Histogram

jobs_processed = Counter('queue_jobs_processed_total', 'Total jobs processed')
jobs_failed = Counter('queue_jobs_failed_total', 'Total jobs failed')
queue_depth = Gauge('queue_depth', 'Current queue depth')
processing_time = Histogram('job_processing_seconds', 'Job processing time')
```

### 2. Log Aggregation

Configure log shipping to centralized system:

```bash
# Filebeat (ELK Stack)
sudo apt install filebeat
sudo vim /etc/filebeat/filebeat.yml
```

```yaml
filebeat.inputs:
- type: journald
  id: chad-queue-worker
  include_matches:
    - systemd.unit: chad-queue-worker.service

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
```

### 3. Alerting

Create alerts for:
- Queue depth exceeds threshold
- Worker crashes
- DLQ has items
- High error rate

Example (Prometheus AlertManager):

```yaml
groups:
- name: queue_worker
  rules:
  - alert: HighQueueDepth
    expr: queue_depth > 1000
    for: 5m
    annotations:
      summary: "Queue depth is high"

  - alert: WorkerDown
    expr: up{job="chad-queue-worker"} == 0
    for: 1m
    annotations:
      summary: "Queue worker is down"

  - alert: HighErrorRate
    expr: rate(queue_jobs_failed_total[5m]) > 0.1
    for: 5m
    annotations:
      summary: "High job failure rate"
```

## Operational Procedures

### Graceful Shutdown

```bash
# Send SIGTERM (graceful shutdown)
sudo systemctl stop chad-queue-worker

# Worker will:
# 1. Stop accepting new jobs
# 2. Finish current job
# 3. Exit cleanly
```

### Draining a Worker

```bash
# Stop worker without processing pending jobs
sudo systemctl stop chad-queue-worker

# Pending jobs will be claimed by other workers
```

### Clearing Queue

```bash
# Delete stream (WARNING: loses all queued jobs)
redis-cli DEL chad:jobs

# Or trim to specific length
redis-cli XTRIM chad:jobs MAXLEN 0
```

### Replaying DLQ

```bash
# Read failed jobs from DLQ
redis-cli XRANGE chad:jobs:dlq - +

# Manually re-add to main queue (custom script)
python scripts/replay_dlq.py
```

## Troubleshooting

### Check Worker Status

```bash
# Service status
sudo systemctl status chad-queue-worker

# Recent logs
sudo journalctl -u chad-queue-worker -n 100

# Follow logs
sudo journalctl -u chad-queue-worker -f
```

### Check Queue Status

```bash
# Stream info
redis-cli XINFO STREAM chad:jobs

# Consumer group info
redis-cli XINFO GROUPS chad:jobs

# Pending messages
redis-cli XPENDING chad:jobs chad-workers

# Consumer details
redis-cli XINFO CONSUMERS chad:jobs chad-workers
```

### Common Issues

**Issue**: Worker not consuming jobs

**Solution**:
```bash
# Check consumer group exists
redis-cli XINFO GROUPS chad:jobs

# Recreate if missing
redis-cli XGROUP CREATE chad:jobs chad-workers 0 MKSTREAM

# Check worker logs
sudo journalctl -u chad-queue-worker -n 50
```

**Issue**: Jobs stuck in pending

**Solution**:
```bash
# Check for idle consumers
redis-cli XINFO CONSUMERS chad:jobs chad-workers

# Pending messages with details
redis-cli XPENDING chad:jobs chad-workers - + 10

# Claim abandoned messages (if worker crashed)
# This is handled automatically by Redis Streams
```

## Backup & Recovery

### Backup Queue Data

```bash
# Export queue to file
redis-cli --rdb /backup/redis-dump.rdb

# Or use RDB persistence
redis-cli BGSAVE
```

### Backup Database

```bash
# Postgres backup
pg_dump -h localhost -U postgres chad_core > chad_core_backup.sql
```

### Recovery

```bash
# Restore Redis
redis-cli --rdb /backup/redis-dump.rdb

# Restore Postgres
psql -h localhost -U postgres chad_core < chad_core_backup.sql
```

## Security Checklist

- [ ] Redis password authentication enabled
- [ ] Database connection uses SSL
- [ ] Webhook endpoints use HTTPS
- [ ] Environment files have restricted permissions (600)
- [ ] Service runs as non-root user
- [ ] Resource limits configured in systemd
- [ ] Log files rotated and archived
- [ ] Secrets stored in secure vault (not .env files)
- [ ] Network firewalls configured
- [ ] Rate limiting enabled on API

## Performance Tuning

### Redis Optimization

```bash
# Increase max memory
redis-cli CONFIG SET maxmemory 2gb

# Set eviction policy
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Enable persistence
redis-cli CONFIG SET save "900 1 300 10 60 10000"
```

### Worker Optimization

Adjust settings based on workload:

```bash
# High throughput (more frequent polling)
QUEUE_POLL_INTERVAL_MS=500
QUEUE_BLOCK_MS=2000

# Low latency (immediate processing)
QUEUE_POLL_INTERVAL_MS=100
QUEUE_BLOCK_MS=1000

# Resource constrained (less aggressive)
QUEUE_POLL_INTERVAL_MS=2000
QUEUE_BLOCK_MS=10000
```

### Postgres Optimization

```sql
-- Increase connection pool
ALTER SYSTEM SET max_connections = 200;

-- Tune work memory
ALTER SYSTEM SET work_mem = '16MB';

-- Enable parallel queries
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;
```

## Upgrade Procedure

1. Deploy new code to staging
2. Run tests
3. Deploy to production (blue-green or rolling update)
4. Monitor metrics and logs
5. Rollback if issues detected

```bash
# Blue-green deployment
# 1. Deploy new version as worker-v2
sudo systemctl start chad-queue-worker-v2

# 2. Monitor for issues
sudo journalctl -u chad-queue-worker-v2 -f

# 3. Stop old version
sudo systemctl stop chad-queue-worker

# 4. Switch service name (optional)
sudo systemctl disable chad-queue-worker
sudo systemctl enable chad-queue-worker-v2
```

## Additional Resources

- Redis Streams Documentation: https://redis.io/docs/data-types/streams/
- systemd Service Documentation: https://www.freedesktop.org/software/systemd/man/systemd.service.html
- FastAPI Background Tasks: https://fastapi.tiangolo.com/tutorial/background-tasks/
- Webhook Best Practices: https://webhook.site/docs

---

For questions or issues, contact the chad-core team or create an issue on GitHub.
