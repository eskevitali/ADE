"""Human-in-the-loop approval gates for workflow checkpoints."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class GateStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


@dataclass
class GateState:
    gate: str
    status: GateStatus = GateStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    resolved_at: str | None = None
    comment: str = ""


class ApprovalGate:
    """Thread-safe approval mechanism for pausing workflows."""

    def __init__(self) -> None:
        self._events: dict[str, threading.Event] = {}
        self._states: dict[str, GateState] = {}
        self._lock = threading.Lock()

    def _key(self, task_id: str, gate: str) -> str:
        return f"{task_id}:{gate}"

    def open(self, task_id: str, gate: str) -> GateState:
        key = self._key(task_id, gate)
        with self._lock:
            state = GateState(gate=gate)
            self._states[key] = state
            self._events[key] = threading.Event()
            return state

    def wait(self, task_id: str, gate: str, timeout: float | None = None) -> GateStatus:
        key = self._key(task_id, gate)
        event = self._events.get(key)
        if not event:
            return GateStatus.TIMEOUT
        signaled = event.wait(timeout=timeout)
        with self._lock:
            state = self._states.get(key)
            if state and state.status != GateStatus.PENDING:
                return state.status
        return GateStatus.APPROVED if signaled else GateStatus.TIMEOUT

    def approve(self, task_id: str, gate: str, comment: str = "") -> bool:
        return self._resolve(task_id, gate, GateStatus.APPROVED, comment)

    def reject(self, task_id: str, gate: str, comment: str = "") -> bool:
        return self._resolve(task_id, gate, GateStatus.REJECTED, comment)

    def _resolve(self, task_id: str, gate: str, status: GateStatus, comment: str) -> bool:
        key = self._key(task_id, gate)
        with self._lock:
            state = self._states.get(key)
            event = self._events.get(key)
            if not state or not event:
                return False
            state.status = status
            state.comment = comment
            state.resolved_at = datetime.now(UTC).isoformat()
            event.set()
            return True

    def get_state(self, task_id: str, gate: str) -> GateState | None:
        return self._states.get(self._key(task_id, gate))

    def pending_gates(self, task_id: str) -> list[GateState]:
        prefix = f"{task_id}:"
        with self._lock:
            return [
                state
                for key, state in self._states.items()
                if key.startswith(prefix) and state.status == GateStatus.PENDING
            ]

    def clear_task(self, task_id: str) -> None:
        prefix = f"{task_id}:"
        with self._lock:
            for key in [k for k in self._events if k.startswith(prefix)]:
                self._events.pop(key, None)
                self._states.pop(key, None)


approval_gate = ApprovalGate()