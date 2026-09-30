"""Read-only paginated routes for persistent SIG-ES domain records."""

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from pathlib import PurePosixPath
from decimal import Decimal, InvalidOperation
from datetime import datetime
import hashlib
import re
import unicodedata
from pathlib import Path
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from typing import Literal

from app.db import get_session
from app.business_catalog import CATALOG_SOURCE, CATALOG_VERIFIED, MATERIALS, ORGANIZATIONS, SERVICES, SUPPLIERS
from app.models import (
    AdministrativeRuleDraft,
    Alert,
    AuditEvent,
    ExtractionCandidate,
    Invoice,
    SeiProcess,
    SourceDocument,
)
from app.schemas import (
    AlertPage,
    AdministrativeRuleProposal,
    CandidateCorrectionProposal,
    CatalogSummary,
    ExtractionCandidatePage,
    ExtractionCandidateRead,
    InvoicePage,
    InvoiceWorkflowTransition,
    ManualCandidateProposal,
    PageInfo,
    ProcessPage,
    SourceDocumentPage,
)

router = APIRouter(prefix="/api/v1", tags=["domain"])

def _default_administrative_rule() -> dict[str, str]:
    return {
        "billing_mode": "unclassified",
        "rateio_method": "not_defined",
        "invoice_amount_basis": "unspecified",
        "term_amount_basis": "unspecified",
        "difference_policy": "manual_review",
        "status": "draft",
    }


def _administrative_catalog(scope_type: str) -> list[dict[str, object]]:
    if scope_type == "supplier":
        return [
            {
                "scope_type": "supplier",
                "scope_id": int(item["id"]),
                "name": str(item["nome"]),
                "subtitle": str(item["servico_associado"]),
            }
            for item in SUPPLIERS
        ]
    return [
        {
            "scope_type": "material",
            "scope_id": int(item["id"]),
            "name": str(item["nome"]),
            "subtitle": str(item["categoria"]),
        }
        for item in MATERIALS
    ]


MONTHS_PT_ASCII = (
    "JANEIRO", "FEVEREIRO", "MARCO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
)
AMOUNT_FIELDS = {"amount_brl", "invoice_amount_brl", "reimbursement_term_amount_brl"}
AMOUNT_ROLES = {
    "unspecified", "total_amount", "installment_amount", "percentage", "interest",
    "penalty", "fine", "discount", "tax", "fee", "unit_price", "quantity", "other_numeric",
}
NON_CURRENCY_AMOUNT_ROLES = {"percentage", "quantity", "other_numeric"}
CORRECTABLE_FIELDS = AMOUNT_FIELDS | {
    "process_number", "due_date", "organization_reference", "service_reference",
    "material_reference", "supplier_reference",
}


def _amount_basis(field_name: str, basis: str | None) -> str | None:
    if field_name in AMOUNT_FIELDS:
        return basis or "unspecified"
    if basis is not None:
        raise HTTPException(status_code=422, detail="A natureza bruto/líquido só se aplica a valores monetários")
    return None


def _amount_role(field_name: str, role: str | None) -> str | None:
    if role is None:
        return None
    if field_name not in AMOUNT_FIELDS or role not in AMOUNT_ROLES:
        raise HTTPException(status_code=422, detail="A classificação do número só se aplica a candidatos de valor")
    return role


def _superseded_candidate_ids(candidates: list[ExtractionCandidate]) -> set[UUID]:
    """Return source candidates replaced by append-only manual proposals."""
    prefix = "manual_proposal:prior:"
    result: set[UUID] = set()
    for candidate in candidates:
        if candidate.extraction_method != "manual_proposal" or not candidate.evidence_location:
            continue
        if not candidate.evidence_location.startswith(prefix):
            continue
        try:
            result.add(UUID(candidate.evidence_location.removeprefix(prefix)))
        except ValueError:
            continue
    return result


def _is_effective_total_candidate(
    candidate: ExtractionCandidate,
    superseded_ids: set[UUID],
) -> bool:
    """Keep legacy candidates until classified; exclude replaced rows and explicit components."""
    return candidate.id not in superseded_ids and candidate.amount_role in (None, "total_amount")


def _invoice_release_checks(
    document: SourceDocument,
    candidates: list[ExtractionCandidate],
) -> list[dict[str, object]]:
    """Return human-readable prerequisites before a PDF leaves quarantine."""
    superseded_ids = _superseded_candidate_ids(candidates)
    effective = [candidate for candidate in candidates if candidate.id not in superseded_ids]
    amount_candidates = [candidate for candidate in effective if candidate.field_name in AMOUNT_FIELDS]
    invoice_totals = [
        candidate for candidate in effective
        if candidate.field_name == "invoice_amount_brl"
        and candidate.amount_role == "total_amount"
        and candidate.normalized_value
    ]
    process_values = {
        candidate.normalized_value or candidate.raw_value
        for candidate in effective if candidate.field_name == "process_number"
    }
    due_values = {
        candidate.normalized_value or candidate.raw_value
        for candidate in effective if candidate.field_name == "due_date"
    }
    organization_values = {
        candidate.normalized_value
        for candidate in effective
        if candidate.field_name == "organization_reference"
        and candidate.normalized_value in {str(item["id"]) for item in ORGANIZATIONS}
    }
    supplier, _ = _supplier_group_from_path(document.relative_path, effective)
    material = _material_group_from_path(document.relative_path)
    unclassified_amounts = [
        candidate for candidate in amount_candidates
        if candidate.amount_role in (None, "unspecified")
    ]
    return [
        {
            "key": "invoice_total",
            "label": "Um único valor total da fatura classificado",
            "complete": len(invoice_totals) == 1,
        },
        {
            "key": "all_numbers_classified",
            "label": "Todos os números monetários candidatos classificados",
            "complete": not unclassified_amounts,
            "remaining": len(unclassified_amounts),
        },
        {
            "key": "process",
            "label": "Um único número de processo identificado",
            "complete": len(process_values) == 1,
        },
        {
            "key": "due_date",
            "label": "Uma única data de vencimento identificada",
            "complete": len(due_values) == 1,
        },
        {
            "key": "catalog_group",
            "label": "Fornecedor ou material reconhecido no catálogo/pasta",
            "complete": supplier is not None or material is not None,
        },
        {
            "key": "organization",
            "label": "Um único órgão associado por candidato revisado",
            "complete": len(organization_values) == 1,
        },
    ]


def _single_reference(candidates: list[ExtractionCandidate], field_name: str) -> str | None:
    values = {
        candidate.normalized_value
        for candidate in candidates
        if candidate.field_name == field_name and candidate.normalized_value
    }
    return next(iter(values)) if len(values) == 1 else None


def _repair_path_text(value: str) -> str:
    """Repair common UTF-8-as-Windows-1252 path mojibake when reversible."""
    repaired = value
    for _ in range(2):
        try:
            candidate = repaired.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        if candidate == repaired:
            break
        repaired = candidate
    return repaired


def _normalize_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", _repair_path_text(value).upper())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]+", " ", ascii_text).strip()


def _folder_reference(relative_path: str, folder_label: str, items: list[dict[str, object]]) -> str | None:
    parts = PurePosixPath(relative_path).parts
    label = _normalize_label(folder_label)
    known = {_normalize_label(str(item["nome"])): str(item["id"]) for item in items}
    for index, part in enumerate(parts[:-1]):
        if _normalize_label(part) != label:
            continue
        for candidate_part in parts[index + 1:-1]:
            reference_id = known.get(_normalize_label(candidate_part))
            if reference_id is not None:
                return reference_id
    return None


def _filename_organization_reference(relative_path: str) -> str | None:
    filename = _repair_path_text(PurePosixPath(relative_path).stem).upper()
    tokens = set(re.findall(r"[A-Z0-9]+", filename))
    matches = [str(item["id"]) for item in ORGANIZATIONS if item["sigla"].upper() in tokens]
    return matches[0] if len(matches) == 1 else None


def _month_from_relative_path(relative_path: str) -> int | None:
    normalized_path = unicodedata.normalize("NFKD", relative_path.upper())
    normalized_path = "".join(char for char in normalized_path if not unicodedata.combining(char))
    for month_index, month in enumerate(MONTHS_PT_ASCII, start=1):
        if re.search(rf"(?<![A-Z]){month}(?![A-Z])", normalized_path):
            return month_index
    numeric_month = re.search(r"(?:^|[^0-9])(0?[1-9]|1[0-2])\s*[-_]", PurePosixPath(relative_path).name)
    return int(numeric_month.group(1)) if numeric_month else None


def _catalog_service_from_path(relative_path: str) -> dict[str, object] | None:
    normalized_path = f" {_normalize_label(relative_path)} "
    matches = [
        service
        for service in SERVICES
        if f" {_normalize_label(str(service['nome']))} " in normalized_path
    ]
    if not matches:
        return None
    longest = max(len(_normalize_label(str(service["nome"]))) for service in matches)
    best = [service for service in matches if len(_normalize_label(str(service["nome"]))) == longest]
    return best[0] if len(best) == 1 else None


def _supplier_group_from_path(
    relative_path: str,
    candidates: list[ExtractionCandidate],
) -> tuple[str | None, str | None]:
    service = _catalog_service_from_path(relative_path)
    service_name = str(service["nome"]) if service else None
    associated = []
    if service_name:
        normalized_service = _normalize_label(service_name)
        associated = [
            supplier for supplier in SUPPLIERS
            if normalized_service in _normalize_label(str(supplier["servico_associado"]))
        ]

    path_text = f" {_normalize_label(relative_path)} "
    path_matches = [
        supplier for supplier in SUPPLIERS
        if f" {_normalize_label(str(supplier['nome']))} " in path_text
    ]
    associated_ids = {str(item["id"]) for item in associated}
    path_ids = {str(item["id"]) for item in path_matches}
    candidate_ids = {
        candidate.normalized_value
        for candidate in candidates
        if candidate.field_name == "supplier_reference" and candidate.normalized_value
    }
    valid_candidate_ids = {
        value for value in candidate_ids
        if value in associated_ids or value in path_ids
    }

    if len(valid_candidate_ids) == 1:
        supplier_id = next(iter(valid_candidate_ids))
        supplier = next((item for item in SUPPLIERS if str(item["id"]) == supplier_id), None)
        return (str(supplier["nome"]), service_name) if supplier else (None, service_name)
    resolved_ids = path_ids or associated_ids
    if len(resolved_ids) == 1:
        supplier_id = next(iter(resolved_ids))
        supplier = next((item for item in SUPPLIERS if str(item["id"]) == supplier_id), None)
        return (str(supplier["nome"]), service_name) if supplier else (None, service_name)
    return None, service_name


def _material_group_from_path(relative_path: str) -> str | None:
    material_id = _folder_reference(relative_path, "MATERIAL", MATERIALS)
    if material_id is None:
        return None
    material = next((item for item in MATERIALS if str(item["id"]) == material_id), None)
    return str(material["nome"]) if material else None


def _document_financial_value(candidates: list[ExtractionCandidate]) -> dict[str, str | bool | None]:
    superseded_ids = _superseded_candidate_ids(candidates)
    for field_name, label in (
        ("reimbursement_term_amount_brl", "Termo de recebimento · preferencial"),
        ("invoice_amount_brl", "Fatura · secundário"),
        ("amount_brl", "Valor sem origem identificada"),
    ):
        values = {
            (candidate.normalized_value, candidate.amount_basis or "unspecified")
            for candidate in candidates
            if candidate.field_name == field_name and candidate.normalized_value
            and _is_effective_total_candidate(candidate, superseded_ids)
        }
        if not values:
            continue
        if len(values) != 1:
            return {"amount": None, "amount_source": label, "amount_ambiguous": True, "amount_evidence_location": None}
        value, basis = next(iter(values))
        evidence_locations = sorted({
            candidate.evidence_location
            for candidate in candidates
            if candidate.field_name == field_name
            and _is_effective_total_candidate(candidate, superseded_ids)
            and candidate.normalized_value == value
            and (candidate.amount_basis or "unspecified") == basis
            and candidate.evidence_location
        })
        return {
            "amount": value,
            "amount_source": label,
            "amount_ambiguous": False,
            "amount_evidence_location": evidence_locations[0] if len(evidence_locations) == 1 else None,
        }
    return {"amount": None, "amount_source": None, "amount_ambiguous": False, "amount_evidence_location": None}


def _amount_comparison(candidates: list[ExtractionCandidate]) -> str:
    superseded_ids = _superseded_candidate_ids(candidates)
    def values_for(field_name: str) -> set[tuple[str, str]]:
        return {
            (candidate.normalized_value, candidate.amount_basis or "unspecified")
            for candidate in candidates
            if candidate.field_name == field_name and candidate.normalized_value
            and _is_effective_total_candidate(candidate, superseded_ids)
        }

    invoice_values = values_for("invoice_amount_brl")
    term_values = values_for("reimbursement_term_amount_brl")
    if not invoice_values or not term_values:
        return "incomplete"
    if len(invoice_values) != 1 or len(term_values) != 1:
        return "ambiguous"
    invoice_value, invoice_basis = next(iter(invoice_values))
    term_value, term_basis = next(iter(term_values))
    if invoice_value != term_value:
        return "different"
    if invoice_basis != term_basis and "unspecified" not in {invoice_basis, term_basis}:
        return "basis_conflict"
    return "same"


def _normalize_proposed_candidate(field_name: str, value: str, amount_role: str | None = None) -> tuple[str, str]:
    """Validate a proposed value and return its display and normalized forms."""
    cleaned = value.strip()
    if field_name in {"amount_brl", "invoice_amount_brl", "reimbursement_term_amount_brl"}:
        amount_text = cleaned.replace(" ", "")
        if amount_role in NON_CURRENCY_AMOUNT_ROLES:
            if amount_role == "percentage":
                amount_text = re.sub(r"%$", "", amount_text)
        else:
            amount_text = re.sub(r"^R\$\s*", "", amount_text, flags=re.IGNORECASE)
        if "," in amount_text:
            amount_text = amount_text.replace(".", "").replace(",", ".")
        try:
            amount = Decimal(amount_text)
        except InvalidOperation:
            raise HTTPException(status_code=422, detail="Informe um valor monetário válido") from None
        if not amount.is_finite() or amount < 0 or (amount_role not in NON_CURRENCY_AMOUNT_ROLES and amount == 0):
            raise HTTPException(status_code=422, detail="Informe um número válido e não negativo")
        if amount_role in NON_CURRENCY_AMOUNT_ROLES:
            normalized = format(amount.quantize(Decimal("0.0001")), "f").rstrip("0").rstrip(".")
        else:
            normalized = format(amount.quantize(Decimal("0.01")), "f")
        return cleaned, normalized

    if field_name == "process_number":
        if not re.fullmatch(r"\d{5}\.\d{6}/\d{4}-\d{2}", cleaned):
            raise HTTPException(status_code=422, detail="Número SEI fora do formato esperado")
        return cleaned, cleaned

    if field_name == "due_date":
        try:
            parsed = datetime.strptime(cleaned, "%d/%m/%Y").date()
        except ValueError:
            try:
                parsed = datetime.strptime(cleaned, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=422, detail="Data deve ser DD/MM/AAAA ou AAAA-MM-DD") from None
        return cleaned, parsed.isoformat()

    catalog: list[dict[str, object]] | None = None
    if field_name == "organization_reference":
        catalog = ORGANIZATIONS
    elif field_name == "service_reference":
        catalog = SERVICES
    elif field_name == "material_reference":
        catalog = MATERIALS
    elif field_name == "supplier_reference":
        catalog = SUPPLIERS
    if catalog is not None:
        pending_only: bool = False,
        wanted = _normalize_label(cleaned)
        matches = [
            item for item in catalog
            if wanted == str(item["id"])
            or wanted == _normalize_label(str(item["nome"]))
            or (field_name == "organization_reference" and wanted == _normalize_label(str(item.get("sigla", ""))))
        ]
        if len(matches) != 1:
            raise HTTPException(status_code=422, detail="Selecione um item único do catálogo informado")
        canonical_name = str(matches[0].get("sigla") or matches[0]["nome"])
        return canonical_name, str(matches[0]["id"])

    raise HTTPException(status_code=422, detail="Este campo não pode ser corrigido nesta etapa")


def _money_rows(
    totals: dict[str, Decimal],
    counts: dict[str, int],
    names: list[str] | None = None,
) -> list[dict[str, object]]:
    all_names = set(totals) | set(names or [])
    return [
        {
            "name": name,
            "amount": format(totals.get(name, Decimal("0.00")).quantize(Decimal("0.01")), "f"),
            "documents": counts.get(name, 0),
        }
        for name in sorted(all_names, key=lambda key: (-totals.get(key, Decimal("0.00")), key))
    ]


@router.get("/catalog/summary", response_model=CatalogSummary)
def catalog_summary() -> CatalogSummary:
    """Return user-provided reference lists with origin and verification status."""
    return CatalogSummary(
        organization_count=len(ORGANIZATIONS),
        material_count=len(MATERIALS),
        service_count=len(SERVICES),
        supplier_count=len(SUPPLIERS),
        organizations=ORGANIZATIONS,
        materials=MATERIALS,
        services=SERVICES,
        fornecedores=SUPPLIERS,
        catalog_source=CATALOG_SOURCE,
        catalog_verified=CATALOG_VERIFIED,
    )


@router.get("/dashboard/financial-candidates", tags=["dashboard"])
def dashboard_financial_candidates(session: Session = Depends(get_session)) -> dict[str, object]:
    """Aggregate only unique reimbursement-term amounts, never confirmed spending.

    Each current source path contributes at most once. Invoice amounts do not
    replace missing/ambiguous term amounts. Entity totals require exactly one
    distinct catalog reference on the same source document.
    """
    latest_document_by_path: dict[tuple[str, str], SourceDocument] = {}
    documents = session.scalars(
        select(SourceDocument).order_by(SourceDocument.last_seen_at.desc())
    ).all()
    for document in documents:
        key = (document.source_key, document.relative_path)
        latest_document_by_path.setdefault(key, document)
    current_document_ids = {document.id for document in latest_document_by_path.values()}
    if not current_document_ids:
        return _empty_financial_candidate_summary()

    fields = {
        "reimbursement_term_amount_brl", "invoice_amount_brl", "amount_brl",
        "organization_reference", "service_reference", "material_reference", "supplier_reference",
    }
    rows = session.execute(
        select(ExtractionCandidate, SourceDocument.id, SourceDocument.relative_path)
        .join(SourceDocument, SourceDocument.id == ExtractionCandidate.document_id)
        .where(
            SourceDocument.id.in_(current_document_ids),
            ExtractionCandidate.field_name.in_(fields),
            ExtractionCandidate.review_state != "rejected",
        )
    ).all()
    candidates_by_document: dict[object, list[ExtractionCandidate]] = {}
    paths_by_document: dict[object, str] = {}
    for candidate, document_id, relative_path in rows:
        candidates_by_document.setdefault(document_id, []).append(candidate)
        paths_by_document[document_id] = relative_path

    organization_names = {str(item["id"]): item["sigla"] for item in ORGANIZATIONS}
    service_names = {str(item["id"]): item["nome"] for item in SERVICES}
    material_names = {str(item["id"]): item["nome"] for item in MATERIALS}
    supplier_names = {str(item["id"]): item["nome"] for item in SUPPLIERS}
    org_totals: dict[str, Decimal] = {}
    service_totals: dict[str, Decimal] = {}
    material_totals: dict[str, Decimal] = {}
    supplier_totals: dict[str, Decimal] = {}
    org_counts: dict[str, int] = {}
    service_counts: dict[str, int] = {}
    material_counts: dict[str, int] = {}
    supplier_counts: dict[str, int] = {}
    monthly_totals = [Decimal("0.00") for _ in range(12)]
    monthly_counts = [0 for _ in range(12)]
    total_candidate_amount = Decimal("0.00")
    selected_term_documents = ambiguous_term_documents = missing_term_documents = 0
    unassigned_org_documents = 0

    for document_id, candidates in candidates_by_document.items():
        superseded_ids = _superseded_candidate_ids(candidates)
        term_values = {
            (candidate.normalized_value, candidate.amount_basis or "unspecified")
            for candidate in candidates
            if candidate.field_name == "reimbursement_term_amount_brl" and candidate.normalized_value
            and _is_effective_total_candidate(candidate, superseded_ids)
        }
        if not term_values:
            missing_term_documents += 1
            continue
        if len(term_values) != 1:
            ambiguous_term_documents += 1
            continue
        try:
            amount = Decimal(next(iter(term_values))[0])
        except (InvalidOperation, TypeError):
            ambiguous_term_documents += 1
            continue
        if not amount.is_finite() or amount <= 0:
            ambiguous_term_documents += 1
            continue

        selected_term_documents += 1
        total_candidate_amount += amount
        organization_id = _single_reference(candidates, "organization_reference")
        if organization_id in organization_names:
            acronym = organization_names[organization_id]
            org_totals[acronym] = org_totals.get(acronym, Decimal("0.00")) + amount
            org_counts[acronym] = org_counts.get(acronym, 0) + 1
        else:
            unassigned_org_documents += 1

        service_id = _single_reference(candidates, "service_reference")
        if service_id in service_names:
            name = service_names[service_id]
            service_totals[name] = service_totals.get(name, Decimal("0.00")) + amount
            service_counts[name] = service_counts.get(name, 0) + 1

        material_id = _single_reference(candidates, "material_reference")
        if material_id in material_names:
            name = material_names[material_id]
            material_totals[name] = material_totals.get(name, Decimal("0.00")) + amount
            material_counts[name] = material_counts.get(name, 0) + 1

        supplier_id = _single_reference(candidates, "supplier_reference")
        if supplier_id in supplier_names:
            name = supplier_names[supplier_id]
            supplier_totals[name] = supplier_totals.get(name, Decimal("0.00")) + amount
            supplier_counts[name] = supplier_counts.get(name, 0) + 1

        month_number = _month_from_relative_path(paths_by_document[document_id])
        if month_number is not None:
            monthly_totals[month_number - 1] += amount
            monthly_counts[month_number - 1] += 1

    return {
        "measure": "unconfirmed_reimbursement_term_amounts",
        "currency": "BRL",
        "confirmed_spending": False,
        "amount_source": "reimbursement_term_amount_brl",
        "month_source": "month_in_relative_filename",
        "deduplication": "latest_document_per_source_and_relative_path; one amount per document only when unique",
        "included_term_documents": selected_term_documents,
        "total_candidate_amount": format(total_candidate_amount.quantize(Decimal("0.01")), "f"),
        "ambiguous_term_documents": ambiguous_term_documents,
        "documents_without_term_amount": missing_term_documents,
        "unassigned_organization_documents": unassigned_org_documents,
        "by_organization": _money_rows(org_totals, org_counts, list(organization_names.values())),
        "by_month": [
            {
                "month": MONTHS_PT_ASCII[index].title(),
                "month_number": index + 1,
                "amount": format(monthly_totals[index].quantize(Decimal("0.01")), "f"),
                "documents": monthly_counts[index],
            }
            for index in range(12)
        ],
        "by_service": _money_rows(service_totals, service_counts, list(service_names.values())),
        "by_material": _money_rows(material_totals, material_counts, list(material_names.values())),
        "by_supplier": _money_rows(supplier_totals, supplier_counts, list(supplier_names.values())),
    }


def _empty_financial_candidate_summary() -> dict[str, object]:
    return {
        "measure": "unconfirmed_reimbursement_term_amounts",
        "currency": "BRL",
        "confirmed_spending": False,
        "amount_source": "reimbursement_term_amount_brl",
        "month_source": "month_in_relative_filename",
        "deduplication": "latest_document_per_source_and_relative_path; one amount per document only when unique",
        "included_term_documents": 0,
        "total_candidate_amount": "0.00",
        "ambiguous_term_documents": 0,
        "documents_without_term_amount": 0,
        "unassigned_organization_documents": 0,
        "by_organization": _money_rows({}, {}, [item["sigla"] for item in ORGANIZATIONS]),
        "by_month": [
            {"month": month.title(), "month_number": index + 1, "amount": "0.00", "documents": 0}
            for index, month in enumerate(MONTHS_PT_ASCII)
        ],
        "by_service": _money_rows({}, {}, [item["nome"] for item in SERVICES]),
        "by_material": _money_rows({}, {}, [item["nome"] for item in MATERIALS]),
        "by_supplier": _money_rows({}, {}, [item["nome"] for item in SUPPLIERS]),
    }


@router.get("/invoice-documents", tags=["invoices"])
def list_invoice_documents(
    group_by: Literal["supplier", "material"] = "supplier",
    limit: int = Query(default=48, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, max_length=128),
    pending_only: bool = False,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """List imported PDFs as unconfirmed invoice/source-document cards.

    Service names stay as supplier-associated metadata rather than a third
    grouping dimension. Material groups are derived only from MATERIAL folders.
    """
    documents = session.scalars(
        select(SourceDocument)
        .where(SourceDocument.source_key == "local-copy-2026")
        .where(func.lower(SourceDocument.relative_path).like("%.pdf"))
        .order_by(SourceDocument.relative_path)
    ).all()
    def is_invoice_area(relative_path: str) -> bool:
        parts = [_normalize_label(part) for part in PurePosixPath(relative_path).parts]
        return any(
            part == "SERVICO" or part == "MATERIAL"
            for index, part in enumerate(parts)
            if index > 0 and parts[index - 1].startswith("EXECUTADO PROGRAMADO")
        )

    documents = [document for document in documents if is_invoice_area(document.relative_path)]
    if not documents:
        return {
            "items": [], "page": {"limit": limit, "offset": offset, "total": 0},
            "groups": [], "group_by": group_by, "pending_only": pending_only,
            "all_cards_are_unconfirmed_candidates": True,
        }

    document_ids = [document.id for document in documents]
    candidate_rows = session.execute(
        select(ExtractionCandidate)
        .where(ExtractionCandidate.document_id.in_(document_ids))
        .where(ExtractionCandidate.review_state != "rejected")
        .order_by(ExtractionCandidate.created_at)
    ).scalars().all()
    candidates_by_document: dict[object, list[ExtractionCandidate]] = {}
    for candidate in candidate_rows:
        candidates_by_document.setdefault(candidate.document_id, []).append(candidate)

    cards: list[dict[str, object]] = []
    for document in documents:
        candidates = candidates_by_document.get(document.id, [])
        supplier, service = _supplier_group_from_path(document.relative_path, candidates)
        material = _material_group_from_path(document.relative_path)
        group_name = supplier if group_by == "supplier" else material
        if group_name is None:
            group_name = "Fornecedor não identificado" if group_by == "supplier" else "Material não identificado"

        process_values = sorted({
            candidate.raw_value
            for candidate in candidates
            if candidate.field_name == "process_number"
        })
        due_values = sorted({
            candidate.raw_value
            for candidate in candidates
            if candidate.field_name == "due_date"
        })
        financial = _document_financial_value(candidates)
        amount_candidates = [
            {
                "id": str(candidate.id),
                "field_name": candidate.field_name,
                "raw_value": candidate.raw_value,
                "normalized_value": candidate.normalized_value,
                "amount_basis": candidate.amount_basis,
                "amount_role": candidate.amount_role,
                "evidence_location": candidate.evidence_location,
                "review_state": candidate.review_state,
            }
            for candidate in candidates
            if candidate.field_name in {
                "reimbursement_term_amount_brl", "invoice_amount_brl", "amount_brl",
            }
        ]
        release_checks = _invoice_release_checks(document, candidates)
        pending_review = document.invoice_workflow_state == "quarantined"
        card = {
            "id": str(document.id),
            "relative_path": document.relative_path,
            "filename": document.original_filename,
            "processing_state": document.processing_state,
            "group_by": group_by,
            "group_name": group_name,
            "supplier": supplier,
            "service_associated": service,
            "material": material,
            "process_number": process_values[0] if len(process_values) == 1 else None,
            "process_ambiguous": len(process_values) > 1,
            "due_date": due_values[0] if len(due_values) == 1 else None,
            "amount": financial["amount"],
            "amount_source": financial["amount_source"],
            "amount_ambiguous": financial["amount_ambiguous"],
            "amount_evidence_location": financial["amount_evidence_location"],
            "amount_candidates": amount_candidates,
            "invoice_amount_candidates": [
                candidate for candidate in amount_candidates
                if candidate["field_name"] == "invoice_amount_brl"
            ],
            "term_amount_candidates": [
                candidate for candidate in amount_candidates
                if candidate["field_name"] == "reimbursement_term_amount_brl"
            ],
            "amount_comparison": _amount_comparison(candidates),
            "editable_candidates": [
                {
                    "id": str(candidate.id),
                    "field_name": candidate.field_name,
                    "raw_value": candidate.raw_value,
                    "normalized_value": candidate.normalized_value,
                    "amount_basis": candidate.amount_basis,
                    "amount_role": candidate.amount_role,
                    "evidence_location": candidate.evidence_location,
                    "review_state": candidate.review_state,
                }
                for candidate in candidates
                if candidate.review_state == "candidate"
                and candidate.field_name in {
                    "process_number", "due_date", "amount_brl", "invoice_amount_brl",
                    "reimbursement_term_amount_brl", "organization_reference",
                    "service_reference", "material_reference", "supplier_reference",
                }
            ],
            "review_state": document.invoice_workflow_state,
            "invoice_workflow_state": document.invoice_workflow_state,
            "pending_review": pending_review,
            "release_ready": all(bool(item["complete"]) for item in release_checks),
            "release_checks": release_checks,
            "pdf_url": f"/api/v1/source-documents/{document.id}/open",
        }
        cards.append(card)

    if search:
        normalized_search = _normalize_label(search)
        cards = [
            card for card in cards
            if normalized_search in _normalize_label(" ".join(str(card.get(key) or "") for key in (
                "relative_path", "filename", "supplier", "service_associated", "material", "process_number",
            )))
        ]

    cards = [card for card in cards if card["pending_review"] is pending_only]

    group_counts: dict[str, int] = {}
    for card in cards:
        group = str(card["group_name"])
        group_counts[group] = group_counts.get(group, 0) + 1
    page_items = cards[offset:offset + limit]
    return {
        "items": page_items,
        "page": {"limit": limit, "offset": offset, "total": len(cards)},
        "group_by": group_by,
        "groups": [
            {"name": group, "documents": count}
            for group, count in sorted(group_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "all_cards_are_unconfirmed_candidates": True,
        "pending_only": pending_only,
        "source": "local-copy-2026",
    }


@router.post("/source-documents/{document_id}/release-to-invoices", tags=["review"])
def release_source_document_to_invoices(
    document_id: str,
    transition: InvoiceWorkflowTransition,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """Move a fully reviewed PDF from quarantine into the invoice workspace."""
    try:
        parsed_id = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Documento não encontrado") from None
    document = session.get(SourceDocument, parsed_id)
    if document is None or document.source_key != "local-copy-2026":
        raise HTTPException(status_code=404, detail="Documento local não encontrado")
    if document.invoice_workflow_state != "quarantined":
        raise HTTPException(status_code=409, detail="O documento não está em quarentena")

    candidates = session.scalars(
        select(ExtractionCandidate)
        .where(ExtractionCandidate.document_id == document.id)
        .where(ExtractionCandidate.review_state != "rejected")
        .order_by(ExtractionCandidate.created_at)
    ).all()
    checks = _invoice_release_checks(document, candidates)
    missing = [item["label"] for item in checks if not item["complete"]]
    if missing:
        raise HTTPException(
            status_code=409,
            detail={"message": "A fatura ainda não está completa para liberação.", "missing": missing},
        )

    document.invoice_workflow_state = "invoices"
    session.add(AuditEvent(
        action="invoice_document_released_from_quarantine",
        entity_type="source_document",
        entity_id=document.id,
        before_state={"invoice_workflow_state": "quarantined"},
        after_state={
            "invoice_workflow_state": "invoices",
            "reason": transition.reason,
            "release_checks": checks,
        },
    ))
    session.commit()
    return {"document_id": str(document.id), "invoice_workflow_state": "invoices", "released": True}


@router.post("/source-documents/{document_id}/return-to-review", tags=["review"])
def return_source_document_to_review(
    document_id: str,
    transition: InvoiceWorkflowTransition,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """Return a released PDF to quarantine while preserving all candidates."""
    try:
        parsed_id = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Documento não encontrado") from None
    document = session.get(SourceDocument, parsed_id)
    if document is None or document.source_key != "local-copy-2026":
        raise HTTPException(status_code=404, detail="Documento local não encontrado")
    if document.invoice_workflow_state != "invoices":
        raise HTTPException(status_code=409, detail="O documento não está na área Faturas")

    document.invoice_workflow_state = "quarantined"
    session.add(AuditEvent(
        action="invoice_document_returned_to_review",
        entity_type="source_document",
        entity_id=document.id,
        before_state={"invoice_workflow_state": "invoices"},
        after_state={"invoice_workflow_state": "quarantined", "reason": transition.reason},
    ))
    session.commit()
    return {"document_id": str(document.id), "invoice_workflow_state": "quarantined", "returned_to_review": True}


@router.post("/extraction-candidates/{candidate_id}/propose-correction", tags=["review"])
def propose_candidate_correction(
    candidate_id: str,
    proposal: CandidateCorrectionProposal,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """Append an unconfirmed correction proposal while preserving its source row."""
    try:
        parsed_id = UUID(candidate_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Candidato não encontrado") from None

    original = session.get(ExtractionCandidate, parsed_id)
    if original is None or original.review_state != "candidate":
        raise HTTPException(status_code=404, detail="Candidato pendente não encontrado")
    document = session.get(SourceDocument, original.document_id)
    if document is None or document.source_key != "local-copy-2026":
        raise HTTPException(status_code=404, detail="Documento de origem não encontrado")

    amount_role = _amount_role(original.field_name, proposal.amount_role)
    corrected_raw, corrected_normalized = _normalize_proposed_candidate(
        original.field_name, proposal.corrected_value, amount_role
    )
    amount_basis = (
        None if amount_role in NON_CURRENCY_AMOUNT_ROLES
        else _amount_basis(original.field_name, proposal.amount_basis)
    )
    evidence_location = f"manual_proposal:prior:{original.id}"
    existing = session.scalar(
        select(ExtractionCandidate).where(
            ExtractionCandidate.document_id == original.document_id,
            ExtractionCandidate.field_name == original.field_name,
            ExtractionCandidate.raw_value == corrected_raw,
            ExtractionCandidate.normalized_value == corrected_normalized,
            ExtractionCandidate.amount_role.is_(None) if amount_role is None
            else ExtractionCandidate.amount_role == amount_role,
            ExtractionCandidate.amount_basis.is_(None) if amount_basis is None
            else ExtractionCandidate.amount_basis == amount_basis,
            ExtractionCandidate.extraction_method == "manual_proposal",
            ExtractionCandidate.evidence_location == evidence_location,
            ExtractionCandidate.review_state == "candidate",
        )
    )
    if existing is not None:
        return {
            "proposal_id": str(existing.id),
            "source_candidate_id": str(original.id),
            "field_name": original.field_name,
            "raw_value": existing.raw_value,
            "normalized_value": existing.normalized_value,
            "amount_basis": existing.amount_basis,
            "amount_role": existing.amount_role,
            "evidence_location": existing.evidence_location,
            "review_state": existing.review_state,
            "confirmed": False,
            "duplicate": True,
        }

    corrected = ExtractionCandidate(
        document_id=original.document_id,
        field_name=original.field_name,
        raw_value=corrected_raw,
        normalized_value=corrected_normalized,
        amount_basis=amount_basis,
        amount_role=amount_role,
        extraction_method="manual_proposal",
        evidence_location=evidence_location,
        confidence=None,
        review_state="candidate",
    )
    session.add(corrected)
    session.flush()
    session.add(
        AuditEvent(
            action="candidate_correction_proposed",
            entity_type="extraction_candidate",
            entity_id=corrected.id,
            before_state={
                "source_candidate_id": str(original.id),
                "field_name": original.field_name,
                "raw_value": original.raw_value,
                "normalized_value": original.normalized_value,
                "amount_basis": original.amount_basis,
                "amount_role": original.amount_role,
            },
            after_state={
                "source_candidate_id": str(original.id),
                "field_name": corrected.field_name,
                "raw_value": corrected.raw_value,
                "normalized_value": corrected.normalized_value,
                "amount_basis": corrected.amount_basis,
                "amount_role": corrected.amount_role,
                "reason": proposal.reason,
                "review_state": "candidate",
            },
        )
    )
    session.commit()
    return {
        "proposal_id": str(corrected.id),
        "source_candidate_id": str(original.id),
        "field_name": corrected.field_name,
        "raw_value": corrected.raw_value,
        "normalized_value": corrected.normalized_value,
        "amount_basis": corrected.amount_basis,
        "amount_role": corrected.amount_role,
        "evidence_location": corrected.evidence_location,
        "review_state": corrected.review_state,
        "confirmed": False,
        "duplicate": False,
    }


@router.post("/source-documents/{document_id}/propose-correction", tags=["review"])
def propose_manual_candidate(
    document_id: str,
    proposal: ManualCandidateProposal,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """Add a missing field as a pending manual proposal without altering its PDF."""
    try:
        parsed_id = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Documento não encontrado") from None

    document = session.get(SourceDocument, parsed_id)
    if document is None or document.source_key != "local-copy-2026":
        raise HTTPException(status_code=404, detail="Documento de origem não encontrado")
    if proposal.field_name not in CORRECTABLE_FIELDS:
        raise HTTPException(status_code=422, detail="Este campo não pode ser proposto nesta etapa")

    amount_role = _amount_role(proposal.field_name, proposal.amount_role)
    corrected_raw, corrected_normalized = _normalize_proposed_candidate(
        proposal.field_name, proposal.corrected_value, amount_role
    )
    amount_basis = (
        None if amount_role in NON_CURRENCY_AMOUNT_ROLES
        else _amount_basis(proposal.field_name, proposal.amount_basis)
    )
    evidence_location = "manual_proposal:new_field"
    existing = session.scalar(
        select(ExtractionCandidate).where(
            ExtractionCandidate.document_id == document.id,
            ExtractionCandidate.field_name == proposal.field_name,
            ExtractionCandidate.raw_value == corrected_raw,
            ExtractionCandidate.normalized_value == corrected_normalized,
            ExtractionCandidate.amount_role.is_(None) if amount_role is None
            else ExtractionCandidate.amount_role == amount_role,
            ExtractionCandidate.amount_basis.is_(None) if amount_basis is None
            else ExtractionCandidate.amount_basis == amount_basis,
            ExtractionCandidate.extraction_method == "manual_proposal",
            ExtractionCandidate.evidence_location == evidence_location,
            ExtractionCandidate.review_state == "candidate",
        )
    )
    if existing is not None:
        return {
            "proposal_id": str(existing.id),
            "document_id": str(document.id),
            "field_name": existing.field_name,
            "raw_value": existing.raw_value,
            "normalized_value": existing.normalized_value,
            "amount_basis": existing.amount_basis,
            "amount_role": existing.amount_role,
            "evidence_location": existing.evidence_location,
            "review_state": existing.review_state,
            "confirmed": False,
            "duplicate": True,
        }

    candidate = ExtractionCandidate(
        document_id=document.id,
        field_name=proposal.field_name,
        raw_value=corrected_raw,
        normalized_value=corrected_normalized,
        amount_basis=amount_basis,
        amount_role=amount_role,
        extraction_method="manual_proposal",
        evidence_location=evidence_location,
        confidence=None,
        review_state="candidate",
    )
    session.add(candidate)
    session.flush()
    session.add(
        AuditEvent(
            action="candidate_manual_field_proposed",
            entity_type="extraction_candidate",
            entity_id=candidate.id,
            before_state=None,
            after_state={
                "document_id": str(document.id),
                "field_name": candidate.field_name,
                "raw_value": candidate.raw_value,
                "normalized_value": candidate.normalized_value,
                "amount_basis": candidate.amount_basis,
                "amount_role": candidate.amount_role,
                "reason": proposal.reason,
                "review_state": "candidate",
            },
        )
    )
    session.commit()
    return {
        "proposal_id": str(candidate.id),
        "document_id": str(document.id),
        "field_name": candidate.field_name,
        "raw_value": candidate.raw_value,
        "normalized_value": candidate.normalized_value,
        "amount_basis": candidate.amount_basis,
        "amount_role": candidate.amount_role,
        "evidence_location": candidate.evidence_location,
        "review_state": candidate.review_state,
        "confirmed": False,
        "duplicate": False,
    }


@router.get("/source-documents/{document_id}/open", tags=["source-documents"])
def open_source_pdf(
    document_id: str,
    request: Request,
    session: Session = Depends(get_session),
) -> FileResponse:
    """Stream an unchanged PDF only from the explicitly monitored root.

    The relative path is resolved beneath the configured monitor root, symlinks
    are rejected and the SHA-256 must still match the indexed source record.
    """
    monitor = getattr(request.app.state, "file_monitor", None)
    if monitor is None:
        raise HTTPException(status_code=503, detail="Local source folder is not configured")
    try:
        parsed_id = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Source document not found") from None
    document = session.get(SourceDocument, parsed_id)
    if document is None or document.source_key != "local-copy-2026":
        raise HTTPException(status_code=404, detail="Source document not found")
    relative_path = document.relative_path
    expected_hash = document.sha256
    filename = document.original_filename

    relative = PurePosixPath(relative_path)
    if relative.suffix.lower() != ".pdf" or relative.is_absolute() or ".." in relative.parts:
        raise HTTPException(status_code=404, detail="PDF source not found")
    path = monitor.root.joinpath(*relative.parts)
    if path.is_symlink():
        raise HTTPException(status_code=404, detail="PDF source not found")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(monitor.root)
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="PDF source not found") from None
    if not resolved.is_file() or resolved.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="PDF source not found")
    digest = hashlib.sha256()
    try:
        with resolved.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        raise HTTPException(status_code=404, detail="PDF source not readable") from None
    if digest.hexdigest() != expected_hash:
        raise HTTPException(status_code=409, detail="PDF changed since it was indexed")
    return FileResponse(
        resolved,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="inline",
    )


@router.get("/invoices", response_model=InvoicePage)
def list_invoices(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    review_state: Literal["pending_review", "confirmed", "rejected", "archived"] | None = None,
    session: Session = Depends(get_session),
) -> InvoicePage:
    """List persisted invoices; no demonstration fixtures are mixed into this API."""
    statement = select(Invoice)
    count_statement = select(func.count()).select_from(Invoice)
    if review_state:
        statement = statement.where(Invoice.review_state == review_state)
        count_statement = count_statement.where(Invoice.review_state == review_state)
    items = session.scalars(statement.order_by(Invoice.created_at.desc()).limit(limit).offset(offset)).all()
    total = session.scalar(count_statement) or 0
    return InvoicePage(items=items, page=PageInfo(limit=limit, offset=offset, total=total))


@router.get("/processes", response_model=ProcessPage)
def list_processes(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> ProcessPage:
    """List locally recorded process identifiers without claiming SEI validation."""
    items = session.scalars(
        select(SeiProcess).order_by(SeiProcess.created_at.desc()).limit(limit).offset(offset)
    ).all()
    total = session.scalar(select(func.count()).select_from(SeiProcess)) or 0
    return ProcessPage(items=items, page=PageInfo(limit=limit, offset=offset, total=total))


@router.get("/alerts", response_model=AlertPage)
def list_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: Literal["new", "acknowledged", "resolved", "dismissed"] | None = None,
    session: Session = Depends(get_session),
) -> AlertPage:
    """List persisted alerts with bounded pagination."""
    statement = select(Alert)
    count_statement = select(func.count()).select_from(Alert)
    if status:
        statement = statement.where(Alert.status == status)
        count_statement = count_statement.where(Alert.status == status)
    items = session.scalars(statement.order_by(Alert.created_at.desc()).limit(limit).offset(offset)).all()
    total = session.scalar(count_statement) or 0
    return AlertPage(items=items, page=PageInfo(limit=limit, offset=offset, total=total))


@router.get("/source-documents", response_model=SourceDocumentPage)
def list_source_documents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    state: Literal["discovered", "queued", "processing", "review", "complete", "error", "ignored"] | None = None,
    session: Session = Depends(get_session),
) -> SourceDocumentPage:
    """List ingested local metadata; this route never returns file contents."""
    statement = select(SourceDocument)
    count_statement = select(func.count()).select_from(SourceDocument)
    if state:
        statement = statement.where(SourceDocument.processing_state == state)
        count_statement = count_statement.where(SourceDocument.processing_state == state)
    items = session.scalars(
        statement.order_by(SourceDocument.first_seen_at.desc()).limit(limit).offset(offset)
    ).all()
    total = session.scalar(count_statement) or 0
    return SourceDocumentPage(items=items, page=PageInfo(limit=limit, offset=offset, total=total))


@router.get("/extraction-candidates", response_model=ExtractionCandidatePage)
def list_extraction_candidates(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    review_state: Literal["candidate", "accepted", "rejected"] | None = None,
    field_name: str | None = Query(default=None, max_length=64),
    session: Session = Depends(get_session),
) -> ExtractionCandidatePage:
    """List unconfirmed values with relative provenance for human validation."""
    statement = select(ExtractionCandidate, SourceDocument.relative_path).join(
        SourceDocument, SourceDocument.id == ExtractionCandidate.document_id
    )
    count_statement = select(func.count()).select_from(ExtractionCandidate)
    if review_state:
        statement = statement.where(ExtractionCandidate.review_state == review_state)
        count_statement = count_statement.where(ExtractionCandidate.review_state == review_state)
    if field_name:
        statement = statement.where(ExtractionCandidate.field_name == field_name)
        count_statement = count_statement.where(ExtractionCandidate.field_name == field_name)
    rows = session.execute(
        statement.order_by(ExtractionCandidate.created_at.desc()).limit(limit).offset(offset)
    ).all()
    items = [
        ExtractionCandidateRead(
            id=candidate.id,
            document_id=candidate.document_id,
            relative_path=relative_path,
            field_name=candidate.field_name,
            raw_value=candidate.raw_value,
            normalized_value=candidate.normalized_value,
            amount_basis=candidate.amount_basis,
                amount_role=candidate.amount_role,
            extraction_method=candidate.extraction_method,
            evidence_location=candidate.evidence_location,
            confidence=candidate.confidence,
            review_state=candidate.review_state,
            created_at=candidate.created_at,
        )
        for candidate, relative_path in rows
    ]
    total = session.scalar(count_statement) or 0
    return ExtractionCandidatePage(items=items, page=PageInfo(limit=limit, offset=offset, total=total))


@router.get("/ingestion/summary", tags=["ingestion"])
def ingestion_summary(session: Session = Depends(get_session)) -> dict[str, object]:
    """Return aggregate counts for imported metadata and review candidates."""
    documents = session.scalar(select(func.count()).select_from(SourceDocument)) or 0
    candidates = session.scalar(select(func.count()).select_from(ExtractionCandidate)) or 0
    pending_review = session.scalar(
        select(func.count()).select_from(ExtractionCandidate).where(
            ExtractionCandidate.review_state == "candidate"
        )
    ) or 0
    document_states = session.execute(
        select(SourceDocument.processing_state, func.count()).group_by(SourceDocument.processing_state)
    ).all()
    candidate_fields = session.execute(
        select(ExtractionCandidate.field_name, func.count())
        .group_by(ExtractionCandidate.field_name)
        .order_by(func.count().desc())
    ).all()
    relative_paths = session.scalars(select(SourceDocument.relative_path)).all()
    directory_counts: dict[str, int] = {}
    extension_counts: dict[str, int] = {}
    for relative_path in relative_paths:
        relative = PurePosixPath(relative_path)
        parent = relative.parent.as_posix()
        if parent != ".":
            directory_counts[parent] = directory_counts.get(parent, 0) + 1
        extension = relative.suffix.lower() or "(sem extensão)"
        extension_counts[extension] = extension_counts.get(extension, 0) + 1
    return {
        "source_key": "local-copy-2026",
        "documents": documents,
        "candidates": candidates,
        "pending_review": pending_review,
        "document_states": {state: count for state, count in document_states},
        "candidate_fields": {field: count for field, count in candidate_fields},
        "directory_hints": [
            {"relative_path": path, "documents": count}
            for path, count in sorted(directory_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "extensions": dict(sorted(extension_counts.items())),
        "all_extractions_unconfirmed": True,
    }


@router.get("/administrative-rules", tags=["administrative-rules"])
def list_administrative_rules(
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """Return unverified catalog entries with either a saved draft or safe defaults."""
    stored = session.scalars(select(AdministrativeRuleDraft)).all()
    by_scope = {(row.scope_type, row.scope_id): row for row in stored}
    items: list[dict[str, object]] = []
    for scope_type in ("supplier", "material"):
        for item in _administrative_catalog(scope_type):
            scope_key = (scope_type, int(item["scope_id"]))
            row = by_scope.get(scope_key)
            items.append({
                **item,
                "rule": row.rule_data if row else _default_administrative_rule(),
                "version": row.version if row else 0,
                "saved": row is not None,
            })
    return {
        "items": items,
        "supplier_count": len(SUPPLIERS),
        "material_count": len(MATERIALS),
        "catalog_verified": CATALOG_VERIFIED,
        "all_rules_are_drafts": True,
        "rules_applied_automatically": False,
    }


@router.put("/administrative-rules/{scope_type}/{scope_id}", tags=["administrative-rules"])
def save_administrative_rule_draft(
    scope_type: Literal["supplier", "material"],
    scope_id: int,
    proposal: AdministrativeRuleProposal,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """Save a versioned draft, audit it, and deliberately never activate it."""
    catalog_item = next(
        (item for item in _administrative_catalog(scope_type) if item["scope_id"] == scope_id),
        None,
    )
    if catalog_item is None:
        raise HTTPException(status_code=404, detail="Fornecedor/material não encontrado no catálogo de referência")
    if proposal.billing_mode != "rateio" and proposal.rateio_method != "not_defined":
        raise HTTPException(status_code=422, detail="Método de rateio só pode ser informado para cobrança rateada")

    rule_data: dict[str, str] = {
        "billing_mode": proposal.billing_mode,
        "rateio_method": proposal.rateio_method,
        "invoice_amount_basis": proposal.invoice_amount_basis,
        "term_amount_basis": proposal.term_amount_basis,
        "difference_policy": "manual_review",
        "status": "draft",
    }
    row = session.scalar(
        select(AdministrativeRuleDraft).where(
            AdministrativeRuleDraft.scope_type == scope_type,
            AdministrativeRuleDraft.scope_id == scope_id,
        )
    )
    if row is not None and row.rule_data == rule_data:
        return {
            "scope_type": scope_type,
            "scope_id": scope_id,
            "rule": row.rule_data,
            "version": row.version,
            "saved": True,
            "unchanged": True,
            "rules_applied_automatically": False,
        }

    previous_version = row.version if row else 0
    before_state = {
        "scope_type": scope_type,
        "scope_id": scope_id,
        "version": previous_version,
        "rule": row.rule_data if row else None,
    }
    if row is None:
        row = AdministrativeRuleDraft(
            scope_type=scope_type,
            scope_id=scope_id,
            version=1,
            rule_data=rule_data,
        )
        session.add(row)
    else:
        row.version += 1
        row.rule_data = rule_data
    session.flush()
    session.add(
        AuditEvent(
            action="administrative_rule_draft_saved",
            entity_type="administrative_rule",
            entity_id=row.id,
            before_state=before_state,
            after_state={
                "scope_type": scope_type,
                "scope_id": scope_id,
                "version": row.version,
                "rule": rule_data,
                "reason": proposal.reason,
                "status": "draft",
            },
        )
    )
    session.commit()
    return {
        "scope_type": scope_type,
        "scope_id": scope_id,
        "rule": row.rule_data,
        "version": row.version,
        "saved": True,
        "unchanged": False,
        "rules_applied_automatically": False,
    }
