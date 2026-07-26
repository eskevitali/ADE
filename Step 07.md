 — Deployer Agent + Workspace Container + PostgreSQL Event Store.

Цель: После одобрения кода (Human-in-the-loop) у пользователя должна появиться возможность развернуть ADI как реальное рабочее приложение в изолированном окружении.

Реализуй следующее:

1. **Deployer Agent** (новая роль в AgentTeam)
   - Умеет запускать docker compose внутри папки проекта
   - Создаёт отдельный Docker network `ade-adi-{project_id}`
   - Запускает приложение и возвращает URL / статус / логи

2. **Workspace Container**
   - Каждый ADI запускается в своём workspace (docker compose up -d)
   - Примонтируй docker socket, чтобы внутри можно было запускать подконтейнеры

3. **PostgreSQL Event Store**
   - Добавь PostgreSQL в docker-compose.yml
   - Создай простую таблицу events (timestamp, project_id, event_type, data, actor)
   - Сохраняй все ключевые события workflow (spec_approved, code_generated, deployed и т.д.)

4. **API и UI**
   - POST /api/projects/{id}/deploy
   - GET /api/projects/{id}/status
   - На странице проекта добавить кнопку "Deploy" и блок "Running Workspace"

5. Обнови:
   - CURRENT_PROGRESS.md
   - README.md (инструкция по деплою)

После реализации запусти полный тест и покажи пример деплоя проекта.