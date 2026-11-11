# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Share model and its versioned JSON serialization."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

SCHEMA_VERSION = 1


@dataclass
class Share:
    """One named share: a stable id, a free-form label and its settings."""

    id: str
    name: str
    values: dict[str, object] = field(default_factory=dict)

    def to_json(self) -> dict[str, object]:
        return {"id": self.id, "name": self.name, "values": dict(self.values)}

    @classmethod
    def from_json(cls, data: object) -> Share:
        if not isinstance(data, dict):
            raise ValueError("share must be a JSON object")
        values: dict[str, object] = {}
        raw_values = data.get("values", {})
        if isinstance(raw_values, dict):
            for key, value in raw_values.items():
                if isinstance(key, str) and isinstance(value, (str, bool, int, float, type(None))):
                    values[key] = value
        return cls(id=str(data.get("id", "")), name=str(data.get("name", "")), values=values)


@dataclass
class ShareBook:
    """The persisted collection of shares plus the active id."""

    version: int = SCHEMA_VERSION
    active: str = ""
    shares: list[Share] = field(default_factory=list)

    def to_json_text(self) -> str:
        return json.dumps(
            {
                "version": self.version,
                "active": self.active,
                "shares": [share.to_json() for share in self.shares],
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json_text(cls, text: str) -> ShareBook:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("share book must be a JSON object")
        version = int(data.get("version", 0) or 0)
        if version != SCHEMA_VERSION:
            raise ValueError(f"unsupported share-book version: {version!r}")
        raw_shares = data.get("shares", [])
        shares = (
            [Share.from_json(item) for item in raw_shares] if isinstance(raw_shares, list) else []
        )
        return cls(version=version, active=str(data.get("active", "")), shares=shares)
