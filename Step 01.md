**✅ Отлично!** `setup.sh` настроен хорошо.

Теперь создаём **README.md** — главный документ проекта.

### Выполни эту команду на сервере:

```bash
cat > README.md << 'EOF'
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
- Браузерный UI (FastAPI + WebSocket)
- Автоматическое создание Docker-окружений
- Institutional Memory (Qdrant)
- Полная портативность между серверами

## 📋 Быстрый старт

### 1. Клонирование / настройка на новом сервере

```bash
cd /root
git clone <ваш-репозиторий> ADE-V4   # или просто скопируйте папку
cd ADE-V4
```

### 2. Запуск установки

```bash
sudo ./setup.sh
```

### 3. Проверка настройки переменных окружения

```bash
cp .env.example .env
nano .env
```

Должны быть заполнены:
- `OPENROUTER_API_KEY`
- `XAI_API_KEY`

### 4. Установка зависимостей

```bash
uv sync
```

### 5. Запуск разработки

```bash
# Запуск FastAPI backend
uv run uvicorn ade.ui.main:app --reload --port 8000

# Или через docker-compose (позже)
```

## 🛠 Структура проекта

- `ade/` — основной Python-код (core, workflows, tools)
- `frontend/` — браузерный интерфейс (Next.js / HTMX)
- `projects/` — сгенерированные ADI
- `knowledge/` — база знаний
- `docker/` — Dockerfiles и compose-файлы
- `scripts/` — утилиты
- `setup.sh` — скрипт первоначальной настройки

## 📌 Текущий этап разработки

- [x] Etap 0: Подготовка структуры и setup
- [ ] Etap 1: Core Harness + AgentTeam
- [ ] Etap 2: Browser UI + WebSocket
- [ ] Etap 3: Bootstrapping ADI

## 🧩 Технологический стек

- **Backend**: FastAPI + LangGraph
- **Models**: OpenRouter + xAI Grok
- **Infrastructure**: Docker, uv, Python 3.12
- **DB**: Qdrant, PostgreSQL (планируется)

## 📜 Правила проекта

Подробно описаны в файле [`PROJECT_RULES.md`](PROJECT_RULES.md)

---

**Теперь выполни команду выше**, чтобы создать/обновить `README.md`.

После этого напиши мне **«Готово»**, и мы перейдём к **пункту A** — созданию ядра (`ade/core/agent_team.py` и базового оркестратора).

