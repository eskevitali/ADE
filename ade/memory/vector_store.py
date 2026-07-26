"""Qdrant vector store for institutional memory."""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

from ade.core.config import get_config

logger = logging.getLogger(__name__)

COLLECTION_NAME = "ade_knowledge"


class VectorStore:
    """Thin wrapper around Qdrant for workflow artifacts."""

    def __init__(self, url: str | None = None) -> None:
        config = get_config()
        self.url = url or config.qdrant_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(url=self.url)
        return self._client

    def is_available(self) -> bool:
        try:
            self._get_client().get_collections()
            return True
        except Exception as exc:
            logger.warning("Qdrant unavailable at %s: %s", self.url, exc)
            return False

    def ensure_collection(self, vector_size: int = 384) -> None:
        from qdrant_client.models import Distance, VectorParams

        client = self._get_client()
        names = {c.name for c in client.get_collections().collections}
        if COLLECTION_NAME not in names:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    def store_workflow_result(
        self,
        task: str,
        spec: str,
        code: str,
        review: str,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        if not self.is_available():
            return None

        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, task + spec[:64]))
        payload = {
            "task": task,
            "spec": spec,
            "code": code,
            "review": review,
            **(metadata or {}),
        }
        vector = self._hash_to_vector(task + spec + code + review)
        try:
            self.ensure_collection(len(vector))
            client = self._get_client()
            client.upsert(
                collection_name=COLLECTION_NAME,
                points=[{"id": point_id, "vector": vector, "payload": payload}],
            )
            logger.info("Stored workflow result %s in Qdrant", point_id)
            return point_id
        except Exception as exc:
            logger.warning("Failed to store in Qdrant: %s", exc)
            return None

    @staticmethod
    def _hash_to_vector(text: str, size: int = 384) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        values: list[float] = []
        while len(values) < size:
            for byte in digest:
                values.append(byte / 255.0)
                if len(values) >= size:
                    break
            digest = hashlib.sha256(digest).digest()
        return values
