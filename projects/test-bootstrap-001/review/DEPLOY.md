**Docker Configuration**

**Dockerfile**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY app.py .

EXPOSE 8000
CMD ["python", "app.py"]
```

**docker-compose.yml**
```yaml
version: "3.8"
services:
  api:
    build: .
    container_name: test-bootstrap-001
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 5s
```

**Deployment Steps**

```bash
# 1. Build and start
docker compose up -d --build

# 2. Verify health
docker compose ps          # should show "healthy"
curl http://localhost:8000 # returns "hello"

# 3. Logs / stop
docker compose logs -f
docker compose down
```

**Summary**
- **Service**: `api` (container: test-bootstrap-001)
- **Exposed port**: 8000 (host → container)
- **Health check**: HTTP GET `/` every 30s via curl; fails after 3 consecutive errors