"""Durable sinks for prompt-capture records."""

import json
from pathlib import Path
from typing import Protocol


class CaptureSink(Protocol):
    def write(self, record: dict) -> None:
        ...


class NDJSONCaptureSink:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True))
            handle.write("\n")
