Browser UI + первый реальный workflow.

Сделай акцент на: - Простую, но красивую страницу Dashboard (HTMX + Tailwind) - Страницу New Project (форма для идеи) - Live Workflow view с WebSocket обновлениями

После этого подготовь команду для запуска полного теста.

У нас настроен Nginx Proxy Manager на ade.kider.at → 127.0.0.1:8000

Создай / обнови docker-compose.yml с правильными настройками:

- Backend на порту 8000 - Qdrant на 6333/6334 - Используй network_mode: host (чтобы было проще с Nginx Proxy Manager) - Добавь volumes для persistence - Добавь depends_on и restart policy

Также обнови README.md с актуальными инструкциями по запуску через docker compose.

После этого покажи содержимое docker-compose.yml и как запускать.