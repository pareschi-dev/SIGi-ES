"""API contracts for read-only domain listing endpoints."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PageInfo(BaseModel):
    """Server-side pagination metadata."""

    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)


class InvoiceRead(BaseModel):
    """Invoice data persisted in SIG-ES; source verification is not implied."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_number: str | None
    organization_id: UUID | None
    service_id: UUID | None
    amount: Decimal | None
    currency: str
    issue_date: date | None
    due_date: date | None
    review_state: str
    payment_state: str
    created_at: datetime


class InvoicePage(BaseModel):
    """Paginated invoice response."""

    items: list[InvoiceRead]
    page: PageInfo


class ProcessRead(BaseModel):
    """Process number with an explicit external verification state."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    process_number: str
    verification_state: str
    object_description: str | None
    created_at: datetime


class ProcessPage(BaseModel):
    """Paginated process response."""

    items: list[ProcessRead]
    page: PageInfo


class AlertRead(BaseModel):
    """Alert response without internal filesystem or integration credentials."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    alert_type: str
    severity: str
    status: str
    entity_type: str | None
    entity_id: UUID | None
    summary: str
    created_at: datetime


class AlertPage(BaseModel):
    """Paginated alert response."""

    items: list[AlertRead]
    page: PageInfo


class SourceDocumentRead(BaseModel):
    """Imported local document metadata; original contents are not served here."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    relative_path: str
    original_filename: str
    sha256: str
    byte_size: int
    media_type: str | None
    processing_state: str
    first_seen_at: datetime


class SourceDocumentPage(BaseModel):
    """Page of imported source file metadata."""

    items: list[SourceDocumentRead]
    page: PageInfo


class ExtractionCandidateRead(BaseModel):
    """Unconfirmed extracted value with its document and source location."""

    id: UUID
    document_id: UUID
    relative_path: str
    field_name: str
    raw_value: str
    normalized_value: str | None
    amount_basis: Literal["gross", "net", "unspecified"] | None
    amount_role: Literal[
        "unspecified", "total_amount", "installment_amount", "percentage", "interest",
        "penalty", "fine", "discount", "tax", "fee", "unit_price", "quantity", "other_numeric",
    ] | None
    extraction_method: str
    evidence_location: str | None
    confidence: Decimal | None
    review_state: str
    created_at: datetime


class ExtractionCandidatePage(BaseModel):
    """Page of unconfirmed extraction candidates for human review."""

    items: list[ExtractionCandidateRead]
    page: PageInfo


class CandidateCorrectionProposal(BaseModel):
    """Append-only proposed correction; it does not accept/confirm a candidate."""

    corrected_value: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=5, max_length=1000)
    amount_basis: Literal["gross", "net", "unspecified"] | None = None
    amount_role: Literal[
        "unspecified", "total_amount", "installment_amount", "percentage", "interest",
        "penalty", "fine", "discount", "tax", "fee", "unit_price", "quantity", "other_numeric",
    ] | None = None


class InvoiceWorkflowTransition(BaseModel):
    """Human-proposed workflow transition with an auditable reason."""

    reason: str = Field(min_length=5, max_length=1000)


class ManualCandidateProposal(CandidateCorrectionProposal):
    """Propose a field not present in the document's extraction candidates."""

    field_name: str = Field(min_length=1, max_length=64)


class CandidateReviewField(BaseModel):
    """One standard field reviewed in a multi-field invoice correction form."""

    field_name: str = Field(min_length=1, max_length=64)
    corrected_value: str | None = Field(default=None, min_length=1, max_length=2000)
    source_candidate_ids: list[UUID] = Field(default_factory=list, max_length=1000)
    amount_basis: Literal["gross", "net", "unspecified"] | None = None
    amount_role: Literal[
        "unspecified", "total_amount", "installment_amount", "percentage", "interest",
        "penalty", "fine", "discount", "tax", "fee", "unit_price", "quantity", "other_numeric",
    ] | None = None
    replace_all: bool = False


class CandidateReviewBatch(BaseModel):
    """Append a reviewed set of field proposals without mutating source candidates."""

    fields: list[CandidateReviewField] = Field(min_length=1, max_length=20)
    reason: str = Field(min_length=5, max_length=1000)


class AdministrativeRuleProposal(BaseModel):
    """A draft rule; it never changes extraction or confirms financial values."""

    billing_mode: Literal["unclassified", "exclusive", "rateio"]
    rateio_method: Literal[
        "not_defined", "equal_shares", "contractual_percentages", "consumption", "manual"
    ]
    invoice_amount_basis: Literal["unspecified", "gross", "net"]
    term_amount_basis: Literal["unspecified", "gross", "net"]
    reason: str = Field(min_length=5, max_length=1000)


class CatalogOrganization(BaseModel):
    """Organization row exposed by the read-only catalog summary."""

    id: int
    sigla: str
    nome: str


class CatalogMaterial(BaseModel):
    """Material row exposed by the read-only catalog summary."""

    id: int
    nome: str
    categoria: str


class CatalogService(BaseModel):
    """Service row exposed by the read-only catalog summary."""

    id: int
    nome: str


class CatalogSupplier(BaseModel):
    """Supplier row exposed by the read-only catalog summary."""

    id: int
    nome: str
    servico_associado: str


class CatalogSummary(BaseModel):
    """Counts and user-provided reference catalog; not independently verified."""

    organization_count: int
    material_count: int
    service_count: int
    supplier_count: int
    organizations: list[CatalogOrganization]
    materials: list[CatalogMaterial]
    services: list[CatalogService]
    fornecedores: list[CatalogSupplier]
    catalog_source: str
    catalog_verified: bool
