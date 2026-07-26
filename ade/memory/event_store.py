"""PostgreSQL event store for ADE workflow audit trail."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from ade.core.config import get_config

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    project_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'system',
    data JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);
"""


class EventStore:
    """Persist workflow and deploy events to PostgreSQL."""

    def __init__(self, dsn: str | None = None) -> None:
        config = get_config()
        self.dsn = dsn or config.postgres_url
        self._available: bool | None = None

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import psycopg

            with psycopg.connect(self.dsn, connect_timeout=3) as conn:
                conn.execute("SELECT 1")
            self._available = True
        except Exception as exc:
            logger.warning("PostgreSQL event store unavailable: %s", exc)
            self._available = False
        return self._available

    def ensure_schema(self) -> None:
        if not self.is_available():
            return
        import psycopg

        with psycopg.connect(self.dsn) as conn:
            conn.execute(SCHEMA_SQL)
            conn.commit()
        logger.info("Event store schema ready")

    def record(
        self,
        project_id: str,
        event_type: str,
        *,
        data: dict[str, Any] | None = None,
        actor: str = "system",
    ) -> int | None:
        if not self.is_available():
            return None
        import psycopg

        payload = json.dumps(data or {}, ensure_ascii=False)
        try:
            with psycopg.connect(self.dsn) as conn:
                row = conn.execute(
                    """
                    INSERT INTO events (project_id, event_type, actor, data, ts)
                    VALUES (%s, %s, %s, %s::jsonb, %s)
                    RETURNING id
                    """,
                    (
                        project_id,
                        event_type,
                        actor,
                        payload,
                        datetime.now(UTC),
                    ),
                ).fetchone()
                conn.commit()
                return int(row[0]) if row else None
        except Exception as exc:
            logger.warning("Failed to record event %s: %s", event_type, exc)
            return None

    def list_events(
        self,
        project_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if not self.is_available():
            return []
        import psycopg

        with psycopg.connect(self.dsn) as conn:
            rows = conn.execute(
                """
                SELECT id, ts, project_id, event_type, actor, data
                FROM events
                WHERE project_id = %s
                ORDER BY ts DESC
                LIMIT %s
                """,
                (project_id, limit),
            ).fetchall()
        return [
            {
                "id": r[0],
                "ts": r[1].isoformat() if r[1] else "",
                "project_id": r[2],
                "event_type": r[3],
                "actor": r[4],
                "data": r[5] if isinstance(r[5], dict) else json.loads(r[5] or "{}"),
            }
            for r in rows
        ]