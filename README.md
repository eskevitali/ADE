# ADE 0.2.0 — инженерная организация на сервере владельца

[Product Vision](PRODUCT_VISION.md) · [Обновление и серверные тесты](docs/SERVER_TEST_0_2_0.md) · [Состояние реализации](docs/IMPLEMENTATION_PLAN.md)

Версия 0.2.0 добавляет безопасное сохранение исходников, проверяемые релизы,
Docker-песочницу тестов, проверки готовности, откат и утверждаемую инженерную память.
Ниже сохранена документация предыдущего прототипа; при обновлении используйте инструкцию выше.

# 🚀 ADE v4 — Autonomous Development Environment

Автономная harness-система следующего поколения для создания и управления **Autonomous Development Instances (ADI)**.

## 🎯 Основная цель

ADE v4 позволяет через браузерный интерфейс и Grok CLI:
- Генерировать полноценные ADI-проекты
- Управлять полным циклом разработки (Idea → Spec → Code → Deploy)
- Работать с несколькими моделями одновременно (OpenRouter + Grok)
- Поддерживать высокую изоляцию и портативность

## ✨ Ключевые возможности

- Модель-независимый оркестратор на **LangGraph**
- Browser UI: Dashboard, New Project, Live Workflow (HTMX + Tailwind)
- Dev Cycle workflow: Architect → Coder → Reviewer
- **ADI Bootstrap**: изолированные проекты в `projects/`, Docker network на ADI
- **Deployer (Step 07)**: docker compose workspace, Deployer agent, PostgreSQL event store
- **Human-in-the-loop**: подтверждение Spec и Code перед продолжением
- Institutional Memory (Qdrant)
- Nginx Proxy Manager: `ade.kider.at` → `127.0.0.1:8000`

## 📋 Быстрый старт

### 1. Установка

```bash
cd ADE-V4
sudo ./setup.sh
cp .env.example .env   # заполнить API-ключи
uv sync
```

### 2. Запуск через Docker Compose (рекомендуется)

```bash
./script/start.sh
```

Или вручную:

```bash
docker compose up -d --build
```

- **Backend**: `http://127.0.0.1:8000` (локально), контейнер `ade-v4-backend-1` в сети `web_network`
- **Qdrant**: `http://127.0.0.1:6333`
- **PostgreSQL**: `127.0.0.1:5432` (user `ade`, db `ade`) — event store

Nginx Proxy Manager: `ade.kider.at` → `ade-v4-backend-1:8000` (не `127.0.0.1` — NPM работает в Docker).

Проверка:
```bash
curl http://127.0.0.1:8000/health
# → {"status":"ok","version":"0.1.0"}
```

### 3. Локальный запуск (разработка)

```bash
uv run uvicorn ade.ui.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Вход в систему

Все страницы и API (кроме `/health` и `/docs`) защищены сессионной авторизацией.

| Поле | Значение |
|------|----------|
| URL входа | https://ade.kider.at/login |
| Логин | `eskevitali@gmail.com` |
| Пароль | `(задаётся в ADMIN_PASSWORD; опубликованный пароль необходимо заменить)` |

Переменные в `.env` (опционально): `SESSION_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`.

### 5. Browser UI

| Страница | URL |
|----------|-----|
| Login | https://ade.kider.at/login |
| Dashboard | https://ade.kider.at/dashboard |
| New Project | https://ade.kider.at/projects/new |
| Live Workflow | https://ade.kider.at/workflow/{task_id} |
| API Docs | https://ade.kider.at/docs (без авторизации) |
| WebSocket | `wss://ade.kider.at/ws` (требует сессию) |

### 6. Полный тест

```bash
./scripts/run_full_test.sh
```

Или по отдельности:
```bash
uv run python test_orchestrator.py
uv run python test_workflow_e2e.py
```

### 7. Деплой ADI workspace (Step 07)

После завершения workflow откройте страницу проекта и нажмите **Deploy**, или:

```bash
curl -X POST -b cookies.txt https://ade.kider.at/api/projects/{project_id}/deploy
curl https://ade.kider.at/api/projects/{project_id}/status
```

Deployer:
- создаёт/обновляет `docker-compose.yml` в `projects/{id}/`
- поднимает workspace-контейнер в изолированной сети `ade-adi-{id}`
- для веб-проектов с `src/index.html` — `python -m http.server` на выделенном порту
- пишет события в PostgreSQL (`events`: `spec_approved`, `deployed`, …)

### 8. SSL (если не через NPM)

```bash
sudo certbot --nginx -d ade.kider.at
```

## 📈 Текущий прогресс

| Компонент | Статус |
|-----------|--------|
| Структура + `setup.sh` | ✅ |
| AgentTeam + LangGraph orchestrator | ✅ |
| `ade/core/config.py` + LLM fallback | ✅ |
| `ade/tools/docker_tool.py` | ✅ |
| **Dev Cycle workflow** (`dev_cycle.py`) | ✅ |
| **Browser UI** (Dashboard, New Project, Live Workflow) | ✅ |
| **Qdrant integration** (`vector_store.py`) | ✅ |
| **ADI Bootstrap** (`adi_manager.py`, `bootstrap_cycle.py`) | ✅ |
| **Human-in-the-loop** (approval gates) | ✅ |
| **Session auth** (login, защита маршрутов) | ✅ |
| **Deployer + workspace + PostgreSQL events** | ✅ |
| `docker-compose.yml` + Docker socket | ✅ |
| Nginx Proxy Manager (`ade.kider.at`) | ✅ |
| Frontend Next.js | ⏳ Планируется |

## 🛠 Структура проекта

```
ADE-V4/
├── ade/
│   ├── core/          # config, agent_team, llm_provider
│   ├── workflows/     # orchestrator, dev_cycle
│   ├── memory/        # vector_store (Qdrant)
│   ├── tools/         # docker_tool
│   └── ui/main.py     # FastAPI + WebSocket + UI
├── frontend/templates/  # HTMX + Tailwind pages
├── docker-compose.yml
├── nginx/ade.conf
├── test_orchestrator.py
├── test_workflow_e2e.py
└── scripts/run_full_test.sh
```

## 📌 Этапы разработки

- [x] Etap 0: Структура и setup
- [x] Etap 1: Core Harness + AgentTeam
- [x] Etap 2: FastAPI + WebSocket + docker-compose
- [x] Step 03: Config + Docker tool + Nginx
- [x] Step 04: Browser UI + Dev Cycle workflow
- [x] Step 05: Dashboard — команда агентов
- [x] Step 06: Bootstrapping ADI + изоляция + HITL
- [x] Step 06_1: Базовая авторизация (session login)
- [x] Step 07: Deployer agent + workspace container + PostgreSQL event store

## 🧩 Технологический стек

- **Backend**: FastAPI + LangGraph + HTMX
- **Models**: OpenRouter + xAI Grok
- **Infrastructure**: Docker (host network), uv, Python 3.12
- **DB**: Qdrant + PostgreSQL (event store)
- **Proxy**: Nginx Proxy Manager

## 📜 Правила проекта

[`PROJECT_RULES.md`](PROJECT_RULES.md)

---