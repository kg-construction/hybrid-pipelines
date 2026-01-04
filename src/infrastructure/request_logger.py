from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RequestLogger:
    """
    Simple JSONL logger to group Ollama and Neo4j calls by idempotence key.
    """

    def __init__(self, log_path: Path | None):
        self.log_path = log_path

    def log(self, idempotence_key: str, event: str, payload: dict[str, Any]) -> None:
        if not self.log_path:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "idempotence_key": idempotence_key,
            "event": event,
            "payload": payload,
        }
        with self.log_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
