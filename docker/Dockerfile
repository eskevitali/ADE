FROM python:3.12-slim

WORKDIR /app

RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends curl ca-certificates docker-cli \
    && mkdir -p /usr/local/lib/docker/cli-plugins \
    && curl -fsSL "https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-linux-x86_64" \
       -o /usr/local/lib/docker/cli-plugins/docker-compose \
    && chmod +x /usr/local/lib/docker/cli-plugins/docker-compose \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./
COPY ade ./ade
COPY frontend ./frontend
COPY docker/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh && uv sync --no-dev

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]