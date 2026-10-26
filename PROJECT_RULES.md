# Правила инженерной организации ADE

[PRODUCT_VISION.md](PRODUCT_VISION.md) — основной источник целей.
При расхождении старых рекомендаций ниже с Product Vision приоритет имеет Product Vision.
Результат выпуска подтверждается проверками и артефактами; макет не заменяет готовый продукт.
Опубликованные ранее секреты должны быть заменены владельцем; значения секретов не хранятся в Git.





**Версия:** 4.0  
**Дата создания:** 11 июля 2026  
**Цель:** Создать мощную, модель-независимую, автономную harness-систему для генерации и управления Autonomous Development Instances (ADI).

## 1. Общая цель проекта

ADE v4 — это **автономная harness-среда** (оболочка), которая:
- Через Grok CLI / Grok API + OpenRouter создаёт полноценные ADI (автономные экземпляры разработки)
- Управляет полным циклом разработки: Idea → Specification → Planning → Coding + Review → Testing → Product → Docker Deploy
- Имеет удобный браузерный UI как главную точку контроля
- Работает с максимальной изоляцией и портативностью

## 2. Ключевые принципы

1. **Модель-независимость**
   - Основной доступ через OpenRouter
   - Возможность использовать любую модель (Grok 4, Claude 4, GPT-4.1, Llama 4, DeepSeek и др.)
   - Динамический выбор лучшей модели для каждой роли/задачи

2. **Максимальная изоляция**
   - Каждый проект/ADI работает в своём Docker network + volume
   - Поддержка Docker-in-Docker или Podman
   - Возможность использования gVisor / Firecracker для повышенной безопасности

3. **Портативность**
   - Проект должен легко разворачиваться на любом Ubuntu-сервере одной-двумя командами
   - Всё конфигурируется через `.env` и `docker-compose`

4. **Stateful Multi-Agent Workflow**
   - Основной оркестратор — **LangGraph** (LangChain)
   - Supervisor Agent + специализированные роли (Architect, Coder, Reviewer, Tester, Deployer)

5. **Institutional Memory**
   - Сохранение знаний, решений и уроков в vector DB + event store
   - Автоматическое обновление digital twin проекта

## 3. Рекомендуемый технологический стек (2026)

- **Backend**: FastAPI + WebSocket
- **Frontend**: Next.js 15 (App Router) + shadcn/ui + Tailwind (или сначала HTMX)
- **Orchestrator**: LangGraph
- **Models**: OpenRouter (fallback — xAI Grok API)
- **Vector DB**: Qdrant
- **Event Store**: PostgreSQL + Redis
- **Infrastructure**: Docker + Docker Compose
- **Auth**: NextAuth.js / Clerk

## 4. Структура проекта

```
ADE-V4/
├── ade/                  # Основной Python-код harness
│   ├── core/             # Агенты, orchestrator
│   ├── workflows/        # LangGraph графы
│   ├── memory/           # Vector + event memory
│   ├── ui/               # FastAPI endpoints
│   └── tools/            # Docker, git, browser tools
├── frontend/             # Next.js UI
├── projects/             # Сгенерированные ADI (gitignored)
├── knowledge/            # Institutional knowledge
├── reviews/              # История ревью
├── governance/           # Правила и решения
├── docker/               # Dockerfiles и compose
├── scripts/              # Утилиты и setup
├── .env.example
├── PROJECT_RULES.md
├── README.md
└── docker-compose.yml
```

## 5. Правила разработки

- Все новые ADI должны соответствовать этим PROJECT_RULES
- Код должен быть чистым, модульным и хорошо задокументированным
- Каждый значимый workflow должен иметь возможность human-in-the-loop
- Приоритет — стабильность и воспроизводимость
