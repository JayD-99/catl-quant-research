from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ResearchConfig:
    raw: dict[str, Any]
    path: Path

    @property
    def root(self) -> Path:
        return self.path.resolve().parent.parent

    @property
    def as_of(self) -> str:
        return str(self.raw["project"]["research_as_of"])


def load_config(path: str | Path) -> ResearchConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict) or "project" not in raw or "market" not in raw:
        raise ValueError(f"Invalid research configuration: {config_path}")
    return ResearchConfig(raw=raw, path=config_path)

