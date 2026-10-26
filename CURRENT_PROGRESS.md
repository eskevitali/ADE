# ADE 0.2.0 — подготовка тестовой версии (26 октября 2026)

Product Vision зафиксирован в `PRODUCT_VISION.md`.
Первый этап реализации и оставшаяся работа: `docs/IMPLEMENTATION_PLAN.md`.
Обновление и совместные серверные проверки: `docs/SERVER_TEST_0_2_0.md`.
Рабочий адрес владельца: https://ade.vor-ort-service-rusz.at/dashboard.

Добавлены безопасные артефакты, хешированные снимки релизов, quality gate,
Docker-песочница тестов, проверки готовности и откат, утверждаемые инженерные уроки.
Прокси перестал передавать административные cookie приложениям, генерируемые страницы
получили ограниченную browser sandbox-политику. Секреты из текущих файлов удалены;
история Git не переписывалась, старые опубликованные значения нужно заменить.

Локальные результаты: **82 passed, 4 skipped**. Четыре пропуска — реальные Docker
интеграции; Docker здесь не установлен. Ruff, компиляция Python и синтаксис shell
проверены. LLM и рабочий сервер не использовались тестами. Пример GitHub Actions сохранён
в `docs/ci/github-actions.example.yml`; CI ещё не активирован: токен публикации
не имеет права workflow. Docker-проверки нужно запустить на сервере.

Следующая проверка: обновить сервер из тестовой ветки, сменить старые секреты в `.env`,
проверить `/health` (0.2.0), существующие проекты, Verify/Deploy и rollback.
Эта версия не завершает весь Product Vision: долговечная очередь SDLC,
независимый Tester, сборка зависимостей, удалённые цели и эксплуатация ещё впереди.

Предпочтение владельца: при **3% оставшегося лимита** сохранить код и статус и сделать паузу.

---

## История прототипа до 0.2.0

# ADE v4 — Текущий прогресс

**Дата обновления:** 13 июля 2026 (пауза)  
**Статус:** Step 07 + расширения (recovery, симулятор, промпты в MD, команда агентов)  
**Публичный URL:** https://ade.kider.at  
**Сводка проекта:** [`SUMMARY.md`](SUMMARY.md)

---

## Где остановились (пауза)

Harness **работает**. Backend healthy. Основные пользовательские сценарии проверены.

| Что | Статус |
|-----|--------|
| Deploy + workspace | ✅ |
| Публичный прокси `/run/{id}/` | ✅ |
| Мобильные превью + Expo ZIP | ✅ |
| Симулятор таймера в браузере | ✅ `/preview/{id}/simulator` |
| Revision flow + progress UI | ✅ |
| Recovery loop (Tester) | ✅ в `revision_rebuild` |
| Дубликат / удаление проекта | ✅ |
| Промпты агентов в MD + UI `/team` | ✅ (после restart backend) |
| PostgreSQL event store | ✅ |

**Следующая сессия:** читать этот файл → `docker compose ps` → https://ade.kider.at/dashboard.  
**Step 08.md** по-прежнему нет — уточнить приоритет у пользователя.

---

## Сессия 13.07.2026 — что сделано

### 1. Expo (мобильные ADI)

- `ensure_expo_project()` — scaffold Expo SDK 54 в `projects/{id}/expo/`
- ZIP **только по кнопке** «Создать и скачать ZIP», не при каждой доработке
- `GET /api/projects/{id}/expo-download`
- Тест: `test_expo_scaffold.py`

### 2. Дубликат проекта

- `duplicate_project()` в `adi_manager.py` — имя `Name V2`, `V3`…
- `POST /api/projects/{id}/duplicate` — dashboard + страница проекта
- Тест: `test_duplicate_project.py`

### 3. Критический фикс deploy (compose)

- В `deployer._ensure_compose()` пустой `networks_decl` обнулял весь compose → **исправлено** (сборка `compose_body` отдельно от `networks`)

### 4. Recovery loop (Tester)

- `ade/workflows/recovery.py` — эвристики + LLM Tester
- Действия: `retry_deploy` | `fix_code` | `escalate`
- Лимит: `max_recovery_attempts=3` в `config.py`, счётчик в `manifest.json`
- Интеграция в `revision_rebuild.py`
- UI: статус «Tester восстанавливает… N/M», эскалация при исчерпании лимита
- Тест: `test_recovery_loop.py`

### 5. Интерактивный симулятор (очевидный результат)

- `ensure_timer_simulator()` — `preview/timer-simulator.html` + scaffold `TimerSimulator` в `main.py`
- Режим deploy: `simulator_preview` → ссылка «Открыть симулятор»
- Проект **HITL Test V2** (`d671383f-ceee-4ac3-ac4f-b4ed605acd3b`) исправлен и задеплоен
- Тест: `test_timer_simulator.py`

### 6. Промпты агентов в markdown

- `governance/agents/` — `defaults/`, `prompts/`, `team_config.json`
- `ade/core/team_config.py` — загрузка, сохранение, сброс
- Workflow-инструкции (12 файлов) в `prompts/workflows/`
- Страница **`/team`** — редактирование моделей и промптов, сброс к defaults
- API: `GET /api/team/config`, `PUT /api/team/agents/{role}`, `PUT /api/team/workflows/{name}`, `POST /api/team/reset`
- Dashboard: только ссылка на `/team` (блок карточек убран)
- Тест: `test_team_config.py`
- Документ: `SUMMARY.md`

### 7. Фикс пустой страницы «Команда агентов»

- **Причина:** backend работал со старым кодом (не было `/api/team/config` до `docker compose restart`)
- **Исправление:** серверный рендер в `agent_team.html` (Jinja2), данные сразу в HTML
- **`governance` смонтирован** в `docker-compose.yml`: `./governance:/app/governance`

---

## Сессия 12.07.2026 (кратко)

- Deploy / Workspace, bind mounts, публичный прокси `/run/`
- Revision flow + `pipeline-progress.js`
- Удаление проектов с подтверждением

---

## Архитектура Deploy / Workspace

```
Пользователь → https://ade.kider.at/run/{project_id}/
                    ↓ (FastAPI proxy, session auth)
              ade-v4-backend-1
                    ↓ Docker DNS (сеть ade-v4_default)
              ade-adi-{project_id}-workspace:{port}
```

| Режим | Порт | Публичная ссылка |
|-------|------|------------------|
| `python_app` | 8000 | `/run/{id}/` |
| `web_static` | 8080 | `/run/{id}/` или `/preview/{id}` |
| `mobile_preview` | 8080 | `/preview/{id}/mobile` |
| `simulator_preview` | 8080 | `/preview/{id}/simulator` |
| `python_script` | — | только логи контейнера |
| `idle` | — | превью если есть mockup |

---

## Recovery loop (кратко)

```
Deploy/Rebuild fail → Tester → retry_deploy | fix_code → (до N раз) → escalate → HITL
```

- Поля manifest: `recovery_attempts`, `recovery_status`, `recovery_message`
- Ручной Deploy по кнопке **пока без** recovery (только revision rebuild)

---

## Промпты агентов

```
governance/agents/
├── team_config.json          # модели по ролям
├── defaults/                 # эталон для сброса
│   ├── {role}.md
│   └── workflows/*.md
└── prompts/                  # рабочие копии (harness читает отсюда)
    ├── {role}.md
    └── workflows/*.md
```

UI: https://ade.kider.at/team

---

## Ключевые проекты на диске

| Проект | ID | Заметки |
|--------|-----|---------|
| Я тут | `658fbae8-5606-42f6-858a-5b2cdd0d33be` | **Не удалять** |
| Я тут V2 | `203941da-7cd3-430d-b26a-f8bf9fe3b178` | **Не удалять** |
| Я ТУТ v3 | `ad41334b-fb5f-4a53-94b1-554a6ad808ee` | E2E, Expo, mobile_preview |
| Test Project | `test-bootstrap-001` | Hello API, deploy + proxy |
| test-hitl-001 | `test-hitl-001` | HITL тесты |
| HITL Test V2 | `d671383f-ceee-4ac3-ac4f-b4ed605acd3b` | Дубликат hitl; симулятор таймера, `simulator_preview` |

---

## Инфраструктура (на момент паузы)

```
ade-v4-backend-1          → 127.0.0.1:8000 (healthy)
ade-v4-postgres           → 127.0.0.1:5433
ade-v4-qdrant-1           → 6333/6334
ade-adi-*-workspace       → несколько Up (см. docker ps)
```

**Запуск после перезагрузки сервера:**
```bash
cd /root/ADE-V4
docker compose up -d
# или
./script/start.sh
```

**После изменений в Python/шаблонах:**
```bash
docker compose restart backend
# при изменении Dockerfile:
docker compose build backend && docker compose up -d backend
```

---

## API и URL (актуальные)

| Действие | Метод / URL |
|----------|-------------|
| Login | `POST /auth/login` |
| Dashboard | `/dashboard` |
| Команда агентов | `/team` |
| Конфиг агентов | `GET /api/team/config` |
| Сброс агентов | `POST /api/team/reset` |
| Deploy | `POST /api/projects/{id}/deploy` |
| Статус workspace | `GET /api/projects/{id}/status` |
| Дубликат | `POST /api/projects/{id}/duplicate` |
| Expo ZIP | `GET /api/projects/{id}/expo-download` |
| Симулятор | `GET /preview/{id}/simulator` |
| Приложение | `GET /run/{id}/` |
| Удалить проект | `DELETE /api/projects/{id}` |

**Auth:** `eskevitali@gmail.com` / `(задаётся в ADMIN_PASSWORD; опубликованный пароль необходимо заменить)`
**`.env`:** `POSTGRES_URL=postgresql://ade:ade@localhost:5433/ade`

---

## Ключевые файлы

| Файл | Назначение |
|------|------------|
| `ade/core/team_config.py` | MD-промпты, team_config.json |
| `ade/core/deployer.py` | Deploy, режимы workspace, compose |
| `ade/core/deliverable.py` | Mockup, Expo, timer simulator |
| `ade/workflows/recovery.py` | Tester recovery loop |
| `ade/workflows/revision_rebuild.py` | Пересборка + recovery |
| `ade/ui/main.py` | API, `/team`, `/run/` proxy |
| `frontend/templates/agent_team.html` | UI команды агентов (SSR) |
| `governance/agents/` | Промпты и модели |
| `docker-compose.yml` | + volume `./governance` |

---

## Тесты

```bash
cd /root/ADE-V4
.venv/bin/python test_team_config.py
.venv/bin/python test_recovery_loop.py
.venv/bin/python test_timer_simulator.py
.venv/bin/python test_expo_scaffold.py
.venv/bin/python test_duplicate_project.py
.venv/bin/python test_step07.py
.venv/bin/python test_revision_flow.py
.venv/bin/python test_delete_project.py
./scripts/run_full_test.sh
```

---

## Известные ограничения / на будущее

1. **Recovery** не подключён к ручному Deploy (только revision rebuild).
2. **`PROJECT_RULES.md`** упоминается в промпте Reviewer, но **не подгружается** в контекст автоматически.
3. **Прокси `/run/`** — буферизация целиком (не streaming/SSE).
4. **После правок `ade/` или `frontend/`** — нужен `docker compose restart backend` (uvicorn без `--reload` в prod).
5. **Step 08** не оформлен.

---

## Выполненные этапы (сводка)

| Этап / фича | Статус |
|-------------|--------|
| Etap 0 – Step 06_1 | ✅ |
| Step 07 Deployer + events | ✅ |
| Deploy fixes + public proxy | ✅ |
| Revision flow + progress | ✅ |
| Удаление / дубликат проекта | ✅ |
| Expo scaffold + ZIP on-demand | ✅ |
| Recovery loop (Tester) | ✅ |
| Timer simulator + simulator_preview | ✅ |
| Промпты в MD + `/team` | ✅ |

---

## Как продолжить после перерыва

1. Прочитать `CURRENT_PROGRESS.md` и при необходимости `SUMMARY.md`
2. `cd /root/ADE-V4 && docker compose ps` — backend должен быть **healthy**
3. Открыть https://ade.kider.at/dashboard
4. Проверить https://ade.kider.at/team — 6 агентов + workflow-инструкции
5. При пустой `/team` → `docker compose restart backend`
6. Спросить пользователя: Step 08, recovery на ручном Deploy, автоподгрузка PROJECT_RULES, или другой приоритет