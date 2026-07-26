#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "Настройка ADE v4..."

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Запустите скрипт от root: sudo ./setup.sh" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -y --no-install-recommends \
  ca-certificates curl wget unzip git

if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi

if ! docker compose version &>/dev/null; then
  apt-get install -y --no-install-recommends docker-compose-plugin || true
fi

if ! command -v uv &>/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

if [[ -f "${HOME}/.local/bin/env" ]]; then
  # shellcheck source=/dev/null
  source "${HOME}/.local/bin/env"
fi
export PATH="${HOME}/.local/bin:${PATH}"

uv python install 3.12

if [[ -f "${ROOT_DIR}/pyproject.toml" ]]; then
  uv sync
else
  echo "pyproject.toml не найден — пропуск uv sync"
fi

if [[ ! -f "${ROOT_DIR}/.env" && -f "${ROOT_DIR}/.env.example" ]]; then
  cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
  echo "Создан .env из .env.example — заполните API-ключи"
fi

echo "ADE-V4 успешно настроена!"
echo "Проверка: docker --version && docker compose version && uv --version && uv run python --version"
