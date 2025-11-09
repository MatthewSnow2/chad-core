# Chad-Core Queue Worker - Systemd Deployment

## Installation

### 1. Copy Service File

```bash
sudo cp chad-queue-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
```

### 2. Create Environment File (Optional)

Create `/etc/chad-core/queue-worker.env`:

```bash
# Redis
REDIS_URL=redis://localhost:6379/0
QUEUE_STREAM_NAME=chad:jobs
QUEUE_CONSUMER_GROUP=chad-workers
QUEUE_CONSUMER_NAME=worker-prod-1
QUEUE_MAX_RETRIES=3
QUEUE_RETRY_DELAY_SECONDS=60

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/chad_core

# Webhooks
WEBHOOK_TIMEOUT_SECONDS=10
WEBHOOK_MAX_RETRIES=3
WEBHOOK_RETRY_BACKOFF_BASE=2

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Environment
ENVIRONMENT=production
```

### 3. Enable and Start Service

```bash
sudo systemctl enable chad-queue-worker
sudo systemctl start chad-queue-worker
```

## Management

### Check Status

```bash
sudo systemctl status chad-queue-worker
```

### View Logs

```bash
# Real-time logs
sudo journalctl -u chad-queue-worker -f

# Last 100 lines
sudo journalctl -u chad-queue-worker -n 100

# Logs from today
sudo journalctl -u chad-queue-worker --since today
```

### Restart Worker

```bash
sudo systemctl restart chad-queue-worker
```

### Stop Worker

```bash
sudo systemctl stop chad-queue-worker
```

## Scaling

To run multiple workers:

1. Copy service file with unique name:
```bash
sudo cp /etc/systemd/system/chad-queue-worker.service /etc/systemd/system/chad-queue-worker@.service
```

2. Modify service to use instance name:
```ini
[Service]
Environment="QUEUE_CONSUMER_NAME=worker-%i"
```

3. Start multiple instances:
```bash
sudo systemctl start chad-queue-worker@1
sudo systemctl start chad-queue-worker@2
sudo systemctl start chad-queue-worker@3
```

## Monitoring

### Queue Depth

```bash
redis-cli XLEN chad:jobs
```

### Consumer Group Info

```bash
redis-cli XINFO GROUPS chad:jobs
```

### Pending Jobs

```bash
redis-cli XPENDING chad:jobs chad-workers
```

### Dead Letter Queue

```bash
redis-cli XLEN chad:jobs:dlq
```

## Troubleshooting

### Worker Not Starting

1. Check logs:
```bash
sudo journalctl -u chad-queue-worker -n 50
```

2. Verify dependencies:
```bash
systemctl status redis
systemctl status postgresql
```

3. Check permissions:
```bash
ls -la /opt/chad-core
```

### High Memory Usage

Increase memory limit in service file:
```ini
MemoryLimit=4G
```

### Jobs Stuck in Pending

1. Check for crashed workers:
```bash
redis-cli XPENDING chad:jobs chad-workers
```

2. Claim abandoned jobs:
```bash
# This is handled automatically by Redis Streams consumer groups
# But you can manually claim if needed
```

## Health Checks

Add a health check endpoint or use:

```bash
# Check if worker is consuming
redis-cli XINFO CONSUMERS chad:jobs chad-workers
```

## Backup & Recovery

### Backup Dead Letter Queue

```bash
redis-cli XRANGE chad:jobs:dlq - + > dlq-backup.txt
```

### Replay Failed Jobs

```bash
# Read DLQ and re-add to main queue (implement as needed)
```
