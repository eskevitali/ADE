# Step 06 — Bootstrapping ADI

**Цель:** полная изоляция ADI, генерация проектов в `projects/`, human-in-the-loop.

## Что реализовано

### 1. ADI Manager (`ade/core/adi_manager.py`)
- Bootstrap проекта в `projects/{project_id}/`
- Структура: `src/`, `spec/`, `review/`, `data/`
- `manifest.json`, `README.md`, `docker-compose.yml`
- Docker network на проект (`ade-adi-{id}`) через `DockerTool`
- Запись артефактов: Spec, Code (с парсингом code blocks), Review

### 2. Human-in-the-loop (`ade/core/approval_gate.py`)
- Пауза после Architect (gate: `spec`)
- Пауза после Coder (gate: `code`)
- API: `POST /api/tasks/{id}/approve`, `POST /api/tasks/{id}/reject`

### 3. Bootstrap Workflow (`ade/workflows/bootstrap_cycle.py`)
- Architect → [approve] → Coder → [approve] → Reviewer
- Интеграция с ADI Manager (запись в `projects/`)

### 4. UI
- **New Project:** название, чекбокс Human-in-the-loop
- **Workflow:** панель одобрения Spec/Code
- **Dashboard:** блок ADI проектов, счётчик

### 5. Docker
- Socket mount: `/var/run/docker.sock` в backend
- `docker.io` CLI в Dockerfile

## API

| Endpoint | Описание |
|----------|----------|
| `GET /api/projects` | Список ADI проектов |
| `GET /api/projects/{id}` | Детали проекта |
| `POST /api/tasks/{id}/approve` | Одобрить gate (`spec` / `code`) |
| `POST /api/tasks/{id}/reject` | Отклонить gate |

## Проверка

```bash
./script/start.sh
curl http://127.0.0.1:8000/api/projects
uv run python test_bootstrap.py
./scripts/run_full_test.sh
```

## Следующий шаг (Step 07)
- Deployer agent + запуск ADI workspace container
- PostgreSQL event store
- Улучшенный парсинг кода (multi-file projects)