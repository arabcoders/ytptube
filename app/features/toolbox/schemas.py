from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["queued", "running", "succeeded", "skipped", "failed", "cancelled", "interrupted"]
TERMINAL = frozenset({"succeeded", "skipped", "failed", "cancelled", "interrupted"})


class RemuxOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Extra(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    overwrite_source: bool = True
    options: dict[str, Any] = Field(default_factory=dict)


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tool: str
    file: str = Field(min_length=1, max_length=4096)
    extra: Extra = Field(default_factory=Extra)


class Result(BaseModel):
    outputs: list[str] = Field(default_factory=list)


class Job(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tool: str
    file: str
    extra: Extra = Field(default_factory=Extra)
    status: Status
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: float | None = None
    message: str | None = None
    result: Result | None = None
    error: str | None = None
    error_code: str | None = None
    log: str = ""
