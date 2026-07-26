# ADE v4 — Сводка проекта

**Дата:** 13 июля 2026  
**Публичный URL:** https://ade.kider.at  
**Версия harness:** 0.1.0

---

## 1. Идея проекта

**ADE v4 (Autonomous Development Environment)** — автономная harness-среда (оболочка), которая управляет полным циклом создания **ADI** (Autonomous Development Instance — изолированный экземпляр разработки).

Пользователь через браузер:

1. Формулирует идею продукта (с опциональным Human-in-the-Loop).
2. Получает ТЗ и техническую спецификацию от агентов.
3. Запускает генерацию кода, ревью и сборку артефактов.
4. Видит **очевидный результат** — превью, симулятор или работающее приложение по ссылке.
5. Принимает результат или запрашивает доработку (revision flow).
6. При сбоях harness **сам пытается восстановиться** (Tester + recovery loop), без участия пользователя в отладке кода.

Ключевые принципы:

- **Модель-независимость** — OpenRouter и xAI Grok, модель настраивается per-role.
- **Multi-agent workflow** — LangGraph, роли Supervisor, Architect, Coder, Reviewer, Tester, Deployer.
- **Изоляция** — каждый ADI в `projects/{id}/`, опционально Docker network.
- **Портативность** — Docker Compose, `.env`, один сервер Ubuntu.
- **Institutional Memory** — Qdrant (векторы) + PostgreSQL (события).

Пользователь **не должен чинить баги вручную** — это задача агентов и harness.

---

## 2. Этапы реализации

### Официальные этапы (Step 01 — Step 07)

| Этап | Содержание | Статус |
|------|------------|--------|
| Etap 0 | Структура репозитория, `setup.sh`, `PROJECT_RULES.md` | ✅ |
| Step 01 | Core Harness, `AgentTeam`, LLM provider | ✅ |
| Step 02 | FastAPI, WebSocket, docker-compose | ✅ |
| Step 03 | Config, Docker tool, Nginx | ✅ |
| Step 04 | Browser UI (HTMX + Tailwind), Dev Cycle workflow | ✅ |
| Step 05 | Dashboard, отображение команды агентов | ✅ |
| Step 06 | ADI bootstrap, изоляция, HITL (ТЗ → Spec → Code) | ✅ |
| Step 06_1 | Сессионная авторизация | ✅ |
| Step 07 | Deployer, workspace-контейнер, PostgreSQL event store | ✅ |

**Step 08** на момент сводки **не оформлен** — развитие идёт итеративно поверх Step 07.

### Доработки после Step 07 (сессии разработки)

| Направление | Что сделано |
|-------------|-------------|
| **Deploy / Workspace** | Режимы `mobile_preview`, `web_static`, `python_app`, `python_script`, `simulator_preview`; публичный прокси `/run/{id}/`; исправлен баг пустого `docker-compose.yml` |
| **Revision flow** | Подтверждение доработки → `RevisionRebuildOrchestrator` (Coder → Reviewer → mockup → deploy); progress UI |
| **Удаление / дубликат проекта** | API и UI для удаления с подтверждением; `duplicate_project()` для версий V2, V3… |
| **Expo (мобильные ADI)** | Scaffold Expo SDK 54, ZIP по кнопке, `GET /api/projects/{id}/expo-download` |
| **Интерактивный симулятор** | `ensure_timer_simulator()` — браузерный симулятор таймера + scaffold `TimerSimulator` в Python; режим `simulator_preview` |
| **Recovery loop** | Tester анализирует падения deploy/rebuild; действия `retry_deploy` / `fix_code` / `escalate`; лимит `max_recovery_attempts` (по умолчанию 3) |
| **Промпты агентов в MD** | Все system prompts и workflow-инструкции в `governance/agents/`; UI `/team` для редактирования моделей и промптов; сброс к defaults |

---

## 3. Структура проекта

```
ADE-V4/
├── ade/                          # Ядро harness (Python)
│   ├── core/                     # Конфигурация, агенты, ADI, деплой, артефакты
│   ├── workflows/                # LangGraph / оркестраторы пайплайнов
│   ├── ui/                       # FastAPI приложение (Browser UI + API)
│   ├── memory/                   # Qdrant, PostgreSQL event store
│   └── tools/                    # Docker, compose runner, пути bind-mount
│
├── frontend/
│   ├── templates/                # HTML (Jinja2): dashboard, проект, workflow, команда агентов…
│   └── static/                   # JS (pipeline-progress и др.)
│
├── governance/
│   └── agents/                   # ★ Инструкции для ИИ-агентов (см. раздел 4)
│
├── projects/                     # ADI-проекты (manifest, spec, src, preview, expo…)
├── knowledge/                    # База знаний (зарезервировано)
├── reviews/                      # Обзоры (зарезервировано)
├── docker/                       # Dockerfile backend
├── nginx/                        # Конфиги прокси
├── scripts/                      # run_full_test.sh, start.sh
│
├── Step 01.md … Step 07.md       # Пошаговая документация этапов
├── Etap 0.md                     # Начальная архитектура
├── PROJECT_RULES.md              # Правила проекта (упоминаются Reviewer в промпте)
├── CURRENT_PROGRESS.md           # Снимок прогресса на паузу
├── README.md                     # Быстрый старт
├── SUMMARY.md                    # Этот файл
│
├── docker-compose.yml            # backend, postgres, qdrant
├── pyproject.toml / uv.lock      # Зависимости Python
├── .env / .env.example           # Секреты и настройки
│
└── test_*.py                     # Интеграционные и модульные тесты
```

---

## 4. Модули ядра (`ade/`)

### `ade/core/`

| Файл | Назначение |
|------|------------|
| `agent_team.py` | Роли агентов (`AgentRole`), модели по умолчанию, встроенные fallback-промпты, сборка `AgentTeam` |
| `team_config.py` | ★ Загрузка/сохранение MD-промптов и `team_config.json`; сброс к defaults; `get_workflow_prompt()` |
| `config.py` | Настройки из `.env` (пути, LLM, Docker, `max_recovery_attempts`) |
| `llm_provider.py` | Вызов LLM (OpenRouter / xAI) |
| `model_registry.py` | Отображение моделей и цветов в UI |
| `adi_manager.py` | CRUD ADI-проектов, manifest, revisions, rebuild/deploy статусы, recovery counters |
| `deployer.py` | Deployer agent, docker compose, режимы workspace, прокси-статус |
| `deliverable.py` | Тип проекта (web/mobile/simulator), mockup, Expo, симулятор таймера |
| `auth.py` | Сессионная авторизация |
| `approval_gate.py` | HITL gates (подтверждение Spec/Code) |
| `spec_parser.py` | Парсинг секций ТЗ/Spec для точечных правок |
| `revision_diff.py` | Diff секций при доработке |

### `ade/workflows/`

| Файл | Назначение | Связь с агентами |
|------|------------|------------------|
| `dev_cycle.py` | Линейный цикл: Architect → Coder → Reviewer | Использует workflow-промпты `architect-spec-task`, `coder-implement`, `reviewer-review` |
| `bootstrap_cycle.py` | HITL: идея → ТЗ → Spec → Code → deliverable | Architect + Coder + Reviewer; симулятор/mobile mockup |
| `hitl_helpers.py` | Обсуждение идеи, генерация ТЗ/Spec, revision по feedback | Architect + workflow-промпты `architect-*` |
| `revision_rebuild.py` | После confirm revision: пересборка и deploy | Coder, Reviewer, recovery loop |
| `recovery.py` | ★ Tester: анализ ошибок, `retry_deploy` / `fix_code` / `escalate` | Tester + `tester-recovery-extra` |
| `orchestrator.py` | Supervisor LangGraph (свободная маршрутизация) | Supervisor + `supervisor-route` |

### `ade/ui/`

| Файл | Назначение |
|------|------------|
| `main.py` | FastAPI: страницы, API, WebSocket, `/team`, reload команды агентов |

### `ade/memory/`

| Файл | Назначение |
|------|------------|
| `event_store.py` | События проекта в PostgreSQL |
| `vector_store.py` | Qdrant (institutional memory) |

### `ade/tools/`

| Файл | Назначение |
|------|------------|
| `docker_tool.py` | Сети Docker для изоляции ADI |
| `compose_runner.py` | Безопасный `docker compose` |
| `docker_paths.py` | Абсолютные пути bind-mount на хост |

---

## 5. Инструкции для ИИ-агентов

Вся настраиваемая «архитектура поведения» агентов хранится в **`governance/agents/`**.

### 5.1. Структура каталога агентов

```
governance/agents/
├── team_config.json              # Модели LLM по ролям (редактируется через UI / API)
│
├── defaults/                     # Эталон — источник для «Сбросить по умолчанию»
│   ├── supervisor.md
│   ├── architect.md
│   ├── coder.md
│   ├── reviewer.md
│   ├── tester.md
│   ├── deployer.md
│   └── workflows/
│       ├── architect-discuss-idea.md
│       ├── architect-generate-tz.md
│       ├── architect-generate-spec.md
│       ├── architect-revise-section.md
│       ├── architect-revise-tz.md
│       ├── architect-revise-spec.md
│       ├── architect-spec-task.md
│       ├── coder-implement.md
│       ├── reviewer-review.md
│       ├── deployer-summarize.md
│       ├── tester-recovery-extra.md
│       └── supervisor-route.md
│
└── prompts/                      # Рабочие копии (harness читает отсюда)
    ├── supervisor.md … deployer.md
    └── workflows/                # Те же 12 файлов
```

### 5.2. System prompts ролей (`prompts/{role}.md`)

| Файл | Роль | Назначение инструкции |
|------|------|------------------------|
| `supervisor.md` | Supervisor | Маршрутизация между специалистами, движение к deployable результату |
| `architect.md` | Architect | Спецификации, дизайн системы, планы реализации |
| `coder.md` | Coder | Чистый модульный код по правилам проекта |
| `reviewer.md` | Reviewer | Ревью кода, безопасность, соответствие PROJECT_RULES |
| `tester.md` | Tester | Тесты, диагностика deploy/runtime, recovery без участия пользователя |
| `deployer.md` | Deployer | Docker и шаги деплоя |

### 5.3. Workflow-инструкции (`prompts/workflows/*.md`)

Дополняют system prompt роли в конкретном сценарии. Поддерживают плейсхолдеры `{spec}`, `{code}`, `{idea}`, `{doc_type}`.

| Файл | Где используется | Назначение |
|------|------------------|------------|
| `architect-discuss-idea.md` | `hitl_helpers.discuss_idea` | Фаза обсуждения идеи с пользователем (без полного ТЗ) |
| `architect-generate-tz.md` | `hitl_helpers.generate_tz` | Генерация ТЗ на русском (## секции) |
| `architect-generate-spec.md` | `hitl_helpers.generate_spec_from_tz` | Полная Spec по утверждённому ТЗ |
| `architect-revise-section.md` | `hitl_helpers.revise_document_section` | Правка одной секции ТЗ/Spec |
| `architect-revise-tz.md` | `hitl_helpers.revise_tz_and_spec_from_feedback` | ТЗ после reflection пользователя |
| `architect-revise-spec.md` | то же | Spec после reflection |
| `architect-spec-task.md` | `dev_cycle` Architect node | Краткая техспецификация по задаче |
| `coder-implement.md` | `dev_cycle` / `revision_rebuild` | Реализация по spec |
| `reviewer-review.md` | `dev_cycle` / `revision_rebuild` | Ревью spec + code |
| `deployer-summarize.md` | `deployer._invoke_deployer_agent` | Сводка шагов deploy (compose, port, health) |
| `tester-recovery-extra.md` | `recovery.analyze_failure_with_tester` | Выбор retry_deploy / fix_code / escalate |
| `supervisor-route.md` | `orchestrator` Supervisor node | Ответ одним именем воркера или `finish` |

### 5.4. Модели по умолчанию (`team_config.json` + `agent_team.py`)

| Роль | Модель по умолчанию |
|------|---------------------|
| Supervisor | `openrouter/anthropic/claude-sonnet-4` |
| Architect | `openrouter/anthropic/claude-sonnet-4` |
| Coder | `openrouter/x-ai/grok-3` |
| Reviewer | `openrouter/anthropic/claude-sonnet-4` |
| Tester | `openrouter/openai/gpt-4.1` |
| Deployer | `openrouter/x-ai/grok-3` |

Переопределение: UI **Команда агентов** (`/team`), API `PUT /api/team/agents/{role}`, файл `team_config.json`.

### 5.5. Управление промптами в UI

| URL / API | Действие |
|-----------|----------|
| `/team` | Страница: модель + markdown-редактор на роль; workflow-инструкции; сброс |
| `GET /api/team/config` | Полная конфигурация с текстами промптов |
| `PUT /api/team/agents/{role}` | Сохранить модель и/или prompt |
| `PUT /api/team/workflows/{name}` | Сохранить workflow-инструкцию |
| `POST /api/team/reset` | Сброс всех промптов из `defaults/` и моделей к заводским |

После сохранения harness перезагружает `AgentTeam` без рестарта сервера.

### 5.6. Связанные настройки вне MD

| Параметр | Где | Смысл для агентов |
|----------|-----|-------------------|
| `max_recovery_attempts` | `ade/core/config.py` (.env) | Лимит автопочинки Tester перед эскалацией к человеку |
| `PROJECT_RULES.md` | корень репо | Упоминается в промпте Reviewer; файл **не подгружается** автоматически в system message |

---

## 6. Browser UI (страницы)

| Страница | URL | Назначение |
|----------|-----|------------|
| Login | `/login` | Вход |
| Dashboard | `/dashboard` | Проекты, задачи; ссылка на команду агентов |
| Команда агентов | `/team` | ★ Модели и MD-промпты |
| New Project | `/projects/new` | Создание ADI, HITL toggle |
| Проект | `/projects/{id}` | ТЗ, Spec, код, deploy, acceptance, reflection |
| Revision review | `/projects/{id}/revision/{n}` | Diff доработки |
| Live Workflow | `/workflow/{task_id}` | WebSocket прогресс |
| Превью веб | `/preview/{id}` | Статика из `src/` |
| Симулятор | `/preview/{id}/simulator` | Интерактивный таймер |
| Мобильный макет | `/preview/{id}/mobile` | Phone-frame mockup |
| Running app | `/run/{id}/` | Прокси в workspace-контейнер |

---

## 7. ADI-проект (`projects/{id}/`)

Типичная структура одного экземпляра:

```
projects/{project_id}/
├── manifest.json           # Статус, deploy, rebuild, recovery, workspace_mode
├── deliverable.json        # Тип артефакта, preview_url, инструкции
├── docker-compose.yml      # Генерируется Deployer
├── spec/                   # TZ.md, SPEC.md
├── src/                    # Сгенерированный код
├── review/                 # REVIEW.md, DEPLOY.md
├── revisions/              # rev-N.json (feedback, diff metadata)
├── preview/                # mobile-mockup.html, timer-simulator.html
└── expo/                   # Scaffold мобильного приложения (при type=mobile)
```

---

## 8. Пайплайны (кратко)

```
Новый проект (HITL):
  Идея ⇄ Architect → ТЗ → Spec → [gate] → Coder → Reviewer → Deliverable → Deploy

Доработка (revision):
  Reflection → новое ТЗ/Spec → confirm → RevisionRebuild (+ Recovery loop) → Deploy

Падение deploy/rebuild:
  Tester → retry_deploy | fix_code → (до N попыток) → escalate → пользователь (доработка/дубликат)

Свободный режим:
  Supervisor ⇄ Architect | Coder | Reviewer | Tester | Deployer
```

---

## 9. Тесты

| Файл | Проверяет |
|------|-----------|
| `test_orchestrator.py` | Supervisor LangGraph |
| `test_workflow_e2e.py` | Dev Cycle end-to-end |
| `test_bootstrap.py` | ADI bootstrap |
| `test_auth.py` | Авторизация |
| `test_revision_flow.py` | Revision confirm → rebuild |
| `test_step07.py` | Deployer, workspace |
| `test_delete_project.py` | Удаление проекта |
| `test_duplicate_project.py` | Дубликат проекта |
| `test_expo_scaffold.py` | Expo SDK 54 |
| `test_timer_simulator.py` | Симулятор таймера |
| `test_recovery_loop.py` | Recovery loop Tester |
| `test_team_config.py` | MD-промпты и сброс конфигурации |

---

## 10. Инфраструктура

- **Backend:** `ade-v4-backend-1` → `127.0.0.1:8000`
- **PostgreSQL:** события проектов
- **Qdrant:** векторная память
- **NPM:** `ade.kider.at` → backend
- **Workspace-контейнеры:** `ade-adi-{project_id}-workspace` в сети `ade-v4_default`

---

## 11. Что дальше (не реализовано)

- Оформленный **Step 08** (следующий официальный этап)
- Автоподгрузка полного текста `PROJECT_RULES.md` в контекст Reviewer
- Recovery loop при ручном Deploy (сейчас — в основном в revision rebuild)
- Полноценный frontend на Next.js (в правилах — опционально; сейчас HTMX)

---

*Документ описывает состояние проекта на момент создания. Детальный оперативный снимок — в `CURRENT_PROGRESS.md`.*