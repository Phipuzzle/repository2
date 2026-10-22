from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db.vector import VectorType


class Base(DeclarativeBase):
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("identity_issuer", "identity_subject", name="uq_users_oidc_identity"),
        CheckConstraint(
            "(identity_issuer IS NULL) = (identity_subject IS NULL)",
            name="ck_users_oidc_identity_pair",
        ),
        {"schema": "app"},
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    identity_issuer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    identity_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    role_links: Mapped[list[UserRole]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": "app"}

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = {"schema": "app"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.roles.id", ondelete="CASCADE"), primary_key=True
    )
    user: Mapped[User] = relationship(back_populates="role_links")


class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = {"schema": "app"}

    id: Mapped[uuid.UUID] = uuid_pk()
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.roles.id", ondelete="CASCADE"), index=True
    )
    resource: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(40), default="read")
    row_filter: Mapped[str | None] = mapped_column(Text, nullable=True)
    column_masks: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)


class QueryRun(Base):
    __tablename__ = "query_runs"
    __table_args__ = {"schema": "app"}

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app.users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="streaming", index=True)
    sql: Mapped[str] = mapped_column(Text, default="")
    result_rows: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    result_schema: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    result_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chart_spec: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    insight: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    clarification: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reconnect_count: Mapped[int] = mapped_column(Integer, default=0)
    cache_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    data_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cache_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    events: Mapped[list[QueryEvent]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="QueryEvent.sequence",
    )


class QueryEvent(Base):
    __tablename__ = "query_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_query_events_run_sequence"),
        {"schema": "app"},
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.query_runs.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(48))
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    run: Mapped[QueryRun] = relationship(back_populates="events")


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = {"schema": "app"}

    id: Mapped[uuid.UUID] = uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.query_runs.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.users.id", ondelete="SET NULL"), nullable=True
    )
    rating: Mapped[str] = mapped_column(String(16))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = {"schema": "metadata"}

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), unique=True)
    definition: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = {"schema": "audit"}

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app.users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app.query_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(80), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class TableMetadata(Base):
    __tablename__ = "tables"
    __table_args__ = {"schema": "metadata"}

    id: Mapped[uuid.UUID] = uuid_pk()
    schema_name: Mapped[str] = mapped_column(String(63))
    table_name: Mapped[str] = mapped_column(String(63))
    description: Mapped[str] = mapped_column(Text, default="")


class ColumnMetadata(Base):
    __tablename__ = "columns"
    __table_args__ = {"schema": "metadata"}

    id: Mapped[uuid.UUID] = uuid_pk()
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("metadata.tables.id", ondelete="CASCADE"), index=True
    )
    column_name: Mapped[str] = mapped_column(String(63))
    data_type: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")


class DemoRegion(Base):
    __tablename__ = "demo_regions"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)


class DemoProduct(Base):
    __tablename__ = "demo_products"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    category: Mapped[str] = mapped_column(String(80))


class DemoOrder(Base):
    __tablename__ = "demo_orders"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("analytics.demo_regions.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("analytics.demo_products.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    total_amount: Mapped[Any] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(32), default="paid")


class DemoOrderItem(Base):
    __tablename__ = "demo_order_items"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("analytics.demo_orders.id", ondelete="CASCADE"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Any] = mapped_column(Numeric(12, 2))


class MetadataEmbedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint("content_kind", "ref_id", "version", name="uq_metadata_embeddings_ref"),
        {"schema": "metadata"},
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    content_kind: Mapped[str] = mapped_column(String(24))
    ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    content_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(VectorType(512), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SemanticMetric(Base):
    __tablename__ = "semantic_metrics"
    __table_args__ = {"schema": "metadata"}

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), unique=True)
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    formula: Mapped[str] = mapped_column(Text)
    qualifier: Mapped[str] = mapped_column(Text, default="")
    default_grain: Mapped[str] = mapped_column(String(40), default="")
    chart_type: Mapped[str] = mapped_column(String(24), default="bar")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SemanticDimension(Base):
    __tablename__ = "semantic_dimensions"
    __table_args__ = {"schema": "metadata"}

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), unique=True)
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    table_name: Mapped[str] = mapped_column(String(63))
    column_name: Mapped[str] = mapped_column(String(63))
    dimension_type: Mapped[str] = mapped_column(String(24), default="categorical")
    time_grain: Mapped[str | None] = mapped_column(String(24), nullable=True)


class SemanticMapping(Base):
    __tablename__ = "semantic_mappings"
    __table_args__ = (
        UniqueConstraint("metric_id", "dimension_id", name="uq_semantic_mapping_ref"),
        {"schema": "metadata"},
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    metric_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.semantic_metrics.id", ondelete="CASCADE"),
        index=True,
    )
    dimension_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.semantic_dimensions.id", ondelete="CASCADE"),
        index=True,
    )
