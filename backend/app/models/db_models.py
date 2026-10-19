from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SourceModel(Base):
    __tablename__ = "sources"

    source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reference: Mapped[str | None] = mapped_column(Text)
    reliability: Mapped[str] = mapped_column(
        String(40), nullable=False, default="unknown"
    )
    authorized_for_use: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    authorization_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_sources_name", "name"),)


class EntityModel(Base):
    __tablename__ = "entities"

    entity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    canonical_value: Mapped[str] = mapped_column(String(2048), nullable=False)
    display_value: Mapped[str] = mapped_column(String(2048), nullable=False)
    first_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "length(trim(canonical_value)) > 0",
            name="ck_entities_canonical_value_nonblank",
        ),
        CheckConstraint(
            "length(trim(display_value)) > 0",
            name="ck_entities_display_value_nonblank",
        ),
        CheckConstraint(
            "last_observed_at IS NULL OR first_observed_at IS NULL "
            "OR last_observed_at >= first_observed_at",
            name="ck_entities_observation_chronology",
        ),
        Index("ix_entities_canonical_value", "canonical_value"),
        Index("ix_entities_entity_type", "entity_type"),
    )


class ObservationModel(Base):
    __tablename__ = "observations"

    observation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sources.source_id", ondelete="RESTRICT"),
        nullable=False,
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ingested"
    )
    processing_version: Mapped[str] = mapped_column(
        String(100), nullable=False, default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_observations_sha256_format",
        ),
        Index("ix_observations_source_id", "source_id"),
        Index("ix_observations_collected_at", "collected_at"),
    )


class RelationshipModel(Base):
    __tablename__ = "relationships"

    relationship_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    source_entity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("entities.entity_id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_entity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("entities.entity_id", ondelete="RESTRICT"),
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text)
    first_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "source_entity_id <> target_entity_id",
            name="ck_relationships_distinct_endpoints",
        ),
        CheckConstraint(
            "last_observed_at IS NULL OR first_observed_at IS NULL "
            "OR last_observed_at >= first_observed_at",
            name="ck_relationships_observation_chronology",
        ),
        Index("ix_relationships_source_entity", "source_entity_id"),
        Index("ix_relationships_target_entity", "target_entity_id"),
    )


class EvidenceModel(Base):
    __tablename__ = "evidence"

    evidence_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    relationship_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("relationships.relationship_id", ondelete="RESTRICT"),
        nullable=False,
    )
    observation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("observations.observation_id", ondelete="RESTRICT"),
        nullable=False,
    )
    polarity: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_description: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "polarity IN ('supports', 'contradicts', 'neutral')",
            name="ck_evidence_polarity",
        ),
        CheckConstraint(
            "length(trim(evidence_description)) > 0",
            name="ck_evidence_description_nonblank",
        ),
        Index("ix_evidence_relationship_id", "relationship_id"),
        Index("ix_evidence_observation_id", "observation_id"),
    )