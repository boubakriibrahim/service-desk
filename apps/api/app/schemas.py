from typing import Any
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class MessageRequest(BaseModel):
    content: str = Field(min_length=2, max_length=8000)


class CreateWorkRequest(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    customer_name: str = Field(min_length=2, max_length=160)
    asset_ref: str = Field(min_length=2, max_length=80)


class RejectActionRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=1000)


class EndpointUpdate(BaseModel):
    enabled: bool | None = None
    healthy: bool | None = None
    priority: int | None = Field(default=None, ge=1, le=1000)


class DemoRunRequest(BaseModel):
    task: str | None = None


class JsonArtifact(BaseModel):
    title: str
    summary: str
    sections: list[dict[str, Any]]
    next_steps: list[str]
    citations: list[str]
    action_proposal: dict[str, Any] | None = None
