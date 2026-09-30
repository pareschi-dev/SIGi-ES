"""Relational development schema; business facts remain unverified until reviewed."""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Uuid


def utc_now() -> datetime:
    """Return an aware UTC timestamp for persistence."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for SIG-ES relational models."""


class Organization(Base):
    """Organization catalog; names and acronyms require administrative validation."""

    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    acronym: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Service(Base):
    """Service catalog independent of unconfirmed folder naming rules."""

    __tablename__ = "services"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SourceDocument(Base):
    """Metadata about a discovered document; never stores or mutates absolute paths."""

    __tablename__ = "source_documents"
    __table_args__ = (
        UniqueConstraint("source_key", "relative_path", "sha256", name="uq_document_source_path_hash"),
        CheckConstraint("byte_size >= 0", name="ck_document_nonnegative_size"),
        CheckConstraint(
            "processing_state IN ('discovered','queued','processing','review','complete','error','ignored')",
            name="ck_document_processing_state",
        ),
        CheckConstraint(
            "invoice_workflow_state IN ('quarantined','invoices')",
            name="ck_document_invoice_workflow_state",
        ),
        Index("ix_documents_hash", "sha256"),
        Index("ix_documents_state_seen", "processing_state", "first_seen_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_key: Mapped[str] = mapped_column(String(128), nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(128))
    processing_state: Mapped[str] = mapped_column(String(16), default="discovered", nullable=False)
    invoice_workflow_state: Mapped[str] = mapped_column(String(16), default="quarantined", nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SeiProcess(Base):
    """A process identifier recorded in SIG-ES; existence is not externally verified."""

    __tablename__ = "sei_processes"
    __table_args__ = (
        CheckConstraint(
            "verification_state IN ('unverified','verified','invalid','unavailable')",
            name="ck_process_verification_state",
        ),
        Index("ix_process_number", "process_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    process_number: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_state: Mapped[str] = mapped_column(String(16), default="unverified", nullable=False)
    object_description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Invoice(Base):
    """Invoice record separating review workflow from payment confirmation."""

    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("amount IS NULL OR amount > 0", name="ck_invoice_positive_amount"),
        CheckConstraint("currency = 'BRL'", name="ck_invoice_currency_brl_initial"),
        CheckConstraint(
            "review_state IN ('pending_review','confirmed','rejected','archived')",
            name="ck_invoice_review_state",
        ),
        CheckConstraint(
            "payment_state IN ('unknown','unpaid','paid','cancelled')",
            name="ck_invoice_payment_state",
        ),
        Index("ix_invoice_due_review", "due_date", "review_state"),
        Index("ix_invoice_org_due", "organization_id", "due_date"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    invoice_number: Mapped[str | None] = mapped_column(String(128))
    organization_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    service_id: Mapped[UUID | None] = mapped_column(ForeignKey("services.id", ondelete="RESTRICT"))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    currency: Mapped[str] = mapped_column(String(3), default="BRL", nullable=False)
    issue_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    review_state: Mapped[str] = mapped_column(String(20), default="pending_review", nullable=False)
    payment_state: Mapped[str] = mapped_column(String(12), default="unknown", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class InvoiceProcessLink(Base):
    """Many-to-many relation; source and verification state remain explicit."""

    __tablename__ = "invoice_process_links"
    __table_args__ = (
        UniqueConstraint("invoice_id", "process_id", name="uq_invoice_process_link"),
        CheckConstraint(
            "link_state IN ('suggested','confirmed','rejected')",
            name="ck_invoice_process_link_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    process_id: Mapped[UUID] = mapped_column(ForeignKey("sei_processes.id", ondelete="RESTRICT"), nullable=False)
    link_state: Mapped[str] = mapped_column(String(12), default="suggested", nullable=False)
    evidence_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_documents.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class InvoiceDocumentLink(Base):
    """Associates a source file to an invoice without exposing a public filesystem path."""

    __tablename__ = "invoice_document_links"
    __table_args__ = (
        UniqueConstraint("invoice_id", "document_id", "document_role", name="uq_invoice_document_role"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("source_documents.id", ondelete="RESTRICT"), nullable=False)
    document_role: Mapped[str] = mapped_column(String(32), default="unspecified", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ExtractionCandidate(Base):
    """Unconfirmed extracted value with method and location provenance."""

    __tablename__ = "extraction_candidates"
    __table_args__ = (
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 100)", name="ck_candidate_confidence"),
        CheckConstraint(
            "review_state IN ('candidate','accepted','rejected')",
            name="ck_candidate_review_state",
        ),
        CheckConstraint(
            "amount_basis IS NULL OR amount_basis IN ('gross','net','unspecified')",
            name="ck_candidate_amount_basis",
        ),
        CheckConstraint(
            "amount_role IS NULL OR amount_role IN ('unspecified','total_amount','installment_amount','percentage','interest','penalty','fine','discount','tax','fee','unit_price','quantity','other_numeric')",
            name="ck_candidate_amount_role",
        ),
        Index("ix_candidates_document_field", "document_id", "field_name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(Text)
    amount_basis: Mapped[str | None] = mapped_column(String(16))
    amount_role: Mapped[str | None] = mapped_column(String(24))
    extraction_method: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_location: Mapped[str | None] = mapped_column(String(128))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    review_state: Mapped[str] = mapped_column(String(12), default="candidate", nullable=False)
    reviewed_by: Mapped[UUID | None] = mapped_column(Uuid)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Alert(Base):
    """Deduplicated alert with explicit lifecycle and no inferred external truth."""

    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_alert_fingerprint"),
        CheckConstraint("severity IN ('info','warning','high','critical')", name="ck_alert_severity"),
        CheckConstraint("status IN ('new','acknowledged','resolved','dismissed')", name="ck_alert_status"),
        Index("ix_alert_status_severity", "status", "severity"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(12), default="info", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="new", nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[UUID | None] = mapped_column(Uuid)
    summary: Mapped[str] = mapped_column(String(512), nullable=False)
    context: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    """Append-oriented event record; database-level immutable controls are a later task."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_entity_occurred", "entity_type", "entity_id", "occurred_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(Uuid)
    before_state: Mapped[dict[str, object] | None] = mapped_column(JSON)
    after_state: Mapped[dict[str, object] | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AdministrativeRuleDraft(Base):
    """Versioned draft rules keyed to user-provided supplier/material catalogs."""

    __tablename__ = "administrative_rule_drafts"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", name="uq_admin_rule_scope"),
        CheckConstraint("scope_type IN ('supplier','material')", name="ck_admin_rule_scope_type"),
        CheckConstraint("scope_id > 0", name="ck_admin_rule_positive_scope_id"),
        CheckConstraint("version > 0", name="ck_admin_rule_positive_version"),
        Index("ix_admin_rule_scope", "scope_type", "scope_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    rule_data: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
