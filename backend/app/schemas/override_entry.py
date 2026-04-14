from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.doctrine import SourceClass


class OverrideEntry(BaseModel):
    key: str
    value: Any
    source_url: str | None = None
    source_class: SourceClass
    entered_at: datetime
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    note: str | None = None
