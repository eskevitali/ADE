"""Local engineering memory: candidates need explicit approval before reuse."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from ade.core.config import get_config


class LessonStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_config().root_dir / 'data' / 'engineering.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
                evidence TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'candidate',
                created_at TEXT NOT NULL, approved_by TEXT, approved_at TEXT)''')

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def propose(self, title: str, body: str, evidence: dict) -> int:
        if not title.strip() or not body.strip() or not evidence:
            raise ValueError('A lesson needs a title, body, and evidence')
        if len(title) > 200 or len(body) > 4000:
            raise ValueError('Lesson exceeds size limit')
        with self._connect() as db:
            cursor = db.execute(
                'INSERT INTO lessons(title, body, evidence, created_at) VALUES (?, ?, ?, ?)',
                (title, body, json.dumps(evidence, ensure_ascii=False), datetime.now(UTC).isoformat()),
            )
            return cursor.lastrowid

    def list(self, approved_only: bool = False) -> list[dict]:
        with self._connect() as db:
            where = "WHERE status = 'approved'" if approved_only else ''
            rows = db.execute(f'SELECT * FROM lessons {where} ORDER BY id DESC LIMIT 200').fetchall()
        return [{**dict(row), 'evidence': json.loads(row['evidence'])} for row in rows]

    def approve(self, lesson_id: int, actor: str) -> bool:
        if not actor.strip():
            raise ValueError('Approval actor is required')
        with self._connect() as db:
            result = db.execute(
                "UPDATE lessons SET status='approved', approved_by=?, approved_at=? "
                "WHERE id=? AND status='candidate'",
                (actor, datetime.now(UTC).isoformat(), lesson_id),
            )
            return result.rowcount == 1

    def relevant(self, task: str, limit: int = 3) -> list[dict]:
        words = set(re.findall(r'\w{3,}', task.lower()))
        ranked = []
        for lesson in self.list(approved_only=True):
            tokens = set(re.findall(r'\w{3,}', (lesson['title'] + ' ' + lesson['body']).lower()))
            score = len(words & tokens)
            if score:
                ranked.append((score, lesson['id'], lesson))
        return [row[2] for row in sorted(ranked, key=lambda row: row[:2], reverse=True)[:limit]]
