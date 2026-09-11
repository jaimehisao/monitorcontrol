"""User config: step, sync, autostart, keyboard shortcuts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_PATH = Path.home() / ".config" / "monitorcontrol" / "config.json"


@dataclass
class Config:
    step: int = 5
    sync: bool = False
    autostart: bool = False
    shortcuts: bool = False
    volume_keys: bool = False
    setup_complete: bool = False

    def clamp(self) -> Config:
        step = max(1, min(50, int(self.step)))
        return Config(
            step=step,
            sync=bool(self.sync),
            autostart=bool(self.autostart),
            shortcuts=bool(self.shortcuts),
            volume_keys=bool(self.volume_keys),
            setup_complete=bool(self.setup_complete),
        )


def load(path: Path = DEFAULT_PATH) -> Config:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Config()
    if not isinstance(data, dict):
        return Config()
    known = {field: data[field] for field in Config.__dataclass_fields__ if field in data}
    try:
        return Config(**known).clamp()
    except (TypeError, ValueError):
        return Config()


def save(config: Config, path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config.clamp()), indent=2) + "\n", encoding="utf-8")
