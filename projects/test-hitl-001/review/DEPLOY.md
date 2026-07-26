**Docker Configuration & Deployment Summary**

**docker-compose.yml**
```yaml
version: '3.8'
services:
  hello-app:
    build: .
    container_name: test-hitl-001-hello
    ports:
      - "8000:8000"   # Exposed port (optional; script is CLI-only)
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s
    restart: "no"
```

**Dockerfile**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY hello_function.py .
CMD ["python", "hello_function.py"]
```

**Deployment Steps**
1. Place `hello_function.py` (containing the `hello()` function and `if __name__ == "__main__"` block) in the same directory as the Dockerfile.
2. Run: `docker compose up --build`
3. The container executes the script once and exits (exit code 0 = healthy).
4. Port 8000 is mapped but unused (the script has no HTTP server). Remove the `ports` section if not needed.
5. Health check verifies successful execution; adjust `test` command if you wrap the function in a web server later.