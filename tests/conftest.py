"""Shared fixtures for talon-sandbox SDK tests."""
from __future__ import annotations

SANDBOX_DATA: dict[str, object] = {
    "id": "sbx_test123",
    "state": "running",
    "image_id": "node:20-bookworm",
    "cpu_millis": 2000,
    "memory_bytes": 4294967296,
    "created_at": 1716556800,
    "profile": "default",
    "network_policy": "allowlist",
    "labels": {"project": "test"},
}

PROCESS_DATA: dict[str, object] = {
    "id": "proc_abc123",
    "sandbox_id": "sbx_test123",
    "command": ["npm", "run", "dev"],
    "pid": 42,
    "state": "running",
    "exit_code": 0,
    "started_at": 1716556800,
    "exited_at": 0,
}
