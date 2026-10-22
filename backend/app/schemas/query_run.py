from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

QueryRunStatus = Literal[
    "idle",
    "submitting",
    "streaming",
    "awaiting_clarification",
    "awaiting_approval",
    "completed",
    "failed",
    "cancelled",
]


class QueryRunCreate(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None

    @field_validator("question")
    @classmethod
    def trim_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question must not be blank")
        return value


class SSEEventResponse(BaseModel):
    id: int
    type: str
    timestamp: datetime
    message: str
    data: dict[str, Any] | None = None


class ResultSchemaField(BaseModel):
    name: str
    type: str
    label: str


class ChartSpecResponse(BaseModel):
    type: Literal["line", "bar", "area"]
    title: str
    xField: str
    yField: str
    dataset: list[dict[str, str | int | float]]


class QueryResultResponse(BaseModel):
    rows: list[dict[str, Any]]
    model_config = {"populate_by_name": True}

    schema_: list[ResultSchemaField] = Field(alias="schema")
    total: int


class QueryRunResponse(BaseModel):
    id: UUID
    question: str
    status: QueryRunStatus
    events: list[SSEEventResponse]
    sql: str
    result: QueryResultResponse | None
    chartSpec: ChartSpecResponse | None
    insight: str
    error: str | None
    clarification: str | None
    approvalReason: str | None
    reconnectCount: int
    conversationId: UUID | None
    turnIndex: int
    startedAt: datetime | None
    completedAt: datetime | None


class QueryRunListResponse(BaseModel):
    items: list[QueryRunResponse]
    total: int
    limit: int
    offset: int


class PaginatedResultResponse(QueryResultResponse):
    limit: int
    offset: int


class FeedbackCreate(BaseModel):
    run_id: UUID
    rating: Literal["positive", "negative"]
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackResponse(BaseModel):
    id: UUID
    run_id: UUID
    rating: str
    comment: str | None
    created_at: datetime


class MetricResponse(BaseModel):
    name: str
    definition: str
    source: str
    updatedAt: datetime


class AuditLogResponse(BaseModel):
    id: UUID
    run_id: UUID | None
    action: str
    details: dict[str, Any]
    created_at: datetime
