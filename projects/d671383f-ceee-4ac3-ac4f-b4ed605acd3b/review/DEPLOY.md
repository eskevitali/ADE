**Deployment Summary**

- **docker-compose service**: `hello-timer-app` (builds from local Dockerfile using `python:3.11-slim`, runs `python hello_timer_app.py`)
- **Exposed port**: none (pure CLI app; no ports mapping required)
- **Health check**: none (no HTTP endpoint; container health determined by exit code of the script)

**Quick start**:
```bash
docker compose up --build
```