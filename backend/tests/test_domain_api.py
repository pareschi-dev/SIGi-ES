"""Tests for persistent read-only domain list endpoints."""

from datetime import date
from decimal import Decimal
import hashlib
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models import AdministrativeRuleDraft, AuditEvent, ExtractionCandidate, Invoice
from app.models import SourceDocument


def test_invoice_list_is_empty_without_persisted_records(client_and_session) -> None:
    client, _ = client_and_session

    response = client.get("/api/v1/invoices")

    assert response.status_code == 200
    assert response.json() == {"items": [], "page": {"limit": 50, "offset": 0, "total": 0}}


def test_invoice_list_returns_persisted_data(client_and_session: tuple) -> None:
    client, session_factory = client_and_session
    session: sessionmaker = session_factory()
    session.add(
        Invoice(
            invoice_number="SYNTHETIC-TEST-01",
            amount=Decimal("1250.40"),
            due_date=date(2026, 10, 1),
            review_state="pending_review",
            payment_state="unknown",
        )
    )
    session.commit()
    session.close()

    response = client.get("/api/v1/invoices?review_state=pending_review")

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"]["total"] == 1
    assert payload["items"][0]["invoice_number"] == "SYNTHETIC-TEST-01"
    assert payload["items"][0]["amount"] == "1250.40"
    assert payload["items"][0]["payment_state"] == "unknown"


def test_list_limits_are_bounded(client_and_session) -> None:
    client, _ = client_and_session

    response = client.get("/api/v1/invoices?limit=201")

    assert response.status_code == 422


def test_ingestion_api_exposes_relative_provenance_and_unconfirmed_candidates(client_and_session) -> None:
    client, session_factory = client_and_session
    session = session_factory()
    document = SourceDocument(
        source_key="local-copy-2026",
        relative_path="SERVICO/fatura.pdf",
        original_filename="fatura.pdf",
        sha256="a" * 64,
        byte_size=120,
        processing_state="review",
    )
    session.add(document)
    session.flush()
    session.add(
        ExtractionCandidate(
            document_id=document.id,
            field_name="amount_brl",
            raw_value="1.234,56",
            normalized_value="1234.56",
            extraction_method="pdf_native_text",
            evidence_location="page:1",
            review_state="candidate",
        )
    )
    session.commit()
    session.close()

    summary = client.get("/api/v1/ingestion/summary").json()
    docs = client.get("/api/v1/source-documents").json()
    candidates = client.get("/api/v1/extraction-candidates").json()

    assert summary["documents"] == 1
    assert summary["pending_review"] == 1
    assert summary["all_extractions_unconfirmed"] is True
    assert docs["items"][0]["relative_path"] == "SERVICO/fatura.pdf"
    assert "C:" not in docs["items"][0]["relative_path"]
    assert candidates["items"][0]["field_name"] == "amount_brl"
    assert candidates["items"][0]["evidence_location"] == "page:1"
    assert candidates["items"][0]["review_state"] == "candidate"
    assert candidates["items"][0]["amount_basis"] is None


def test_business_catalog_api_exposes_real_organizations_services_materials_and_suppliers(client_and_session) -> None:
    client, _ = client_and_session

    response = client.get("/api/v1/catalog/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["organization_count"] == 11
    assert payload["material_count"] == 6
    assert payload["service_count"] == 45
    assert payload["supplier_count"] == 22
    assert payload["catalog_verified"] is False
    assert payload["organizations"][0] == {"id": 1, "nome": "SRA/ES", "sigla": "SRA"}
    assert payload["materials"][0] == {"id": 1, "nome": "AÇÚCAR", "categoria": "Alimentos"}
    assert payload["services"][0]["nome"] == "ÁGUA E ESGOTO - BRK - ART CACHOEIRO DE ITAPEMIRIM"
    assert payload["fornecedores"][0] == {
        "id": 1,
        "nome": "BRK",
        "servico_associado": "ÁGUA E ESGOTO - BRK - ART CACHOEIRO DE ITAPEMIRIM",
    }


def test_administrative_rules_list_catalog_and_save_versioned_audited_drafts(client_and_session) -> None:
    client, session_factory = client_and_session

    initial = client.get("/api/v1/administrative-rules")
    assert initial.status_code == 200
    initial_payload = initial.json()
    assert initial_payload["supplier_count"] == 22
    assert initial_payload["material_count"] == 6
    assert len(initial_payload["items"]) == 28
    assert initial_payload["all_rules_are_drafts"] is True
    assert initial_payload["rules_applied_automatically"] is False
    assert initial_payload["items"][0]["rule"]["billing_mode"] == "unclassified"

    endpoint = "/api/v1/administrative-rules/supplier/1"
    rateio = {
        "billing_mode": "rateio",
        "rateio_method": "consumption",
        "invoice_amount_basis": "gross",
        "term_amount_basis": "net",
        "reason": "Contrato e termo indicam consumo por unidade.",
    }
    first = client.put(endpoint, json=rateio)
    same = client.put(endpoint, json={**rateio, "reason": "Revalidação do rascunho atual."})
    exclusive = {
        **rateio,
        "billing_mode": "exclusive",
        "rateio_method": "not_defined",
        "reason": "Revisão administrativa mudou a classificação.",
    }
    second = client.put(endpoint, json=exclusive)

    assert first.status_code == 200
    assert first.json()["version"] == 1
    assert first.json()["rule"]["difference_policy"] == "manual_review"
    assert first.json()["rules_applied_automatically"] is False
    assert same.json()["unchanged"] is True
    assert same.json()["version"] == 1
    assert second.status_code == 200
    assert second.json()["version"] == 2

    session = session_factory()
    rows = session.scalars(select(AdministrativeRuleDraft)).all()
    audit_events = session.scalars(select(AuditEvent)).all()
    session.close()
    assert len(rows) == 1
    assert rows[0].rule_data["billing_mode"] == "exclusive"
    assert rows[0].version == 2
    assert len(audit_events) == 2
    assert all(event.action == "administrative_rule_draft_saved" for event in audit_events)
    assert audit_events[1].before_state["rule"]["billing_mode"] == "rateio"
    assert audit_events[1].after_state["reason"] == exclusive["reason"]


def test_administrative_rule_rejects_unknown_catalog_ids_and_rateio_method_for_exclusive(client_and_session) -> None:
    client, _ = client_and_session
    valid_body = {
        "billing_mode": "exclusive",
        "rateio_method": "not_defined",
        "invoice_amount_basis": "unspecified",
        "term_amount_basis": "unspecified",
        "reason": "Regra de teste não oficial.",
    }
    unknown_id = client.put("/api/v1/administrative-rules/material/999", json=valid_body)
    invalid_combination = client.put(
        "/api/v1/administrative-rules/material/1",
        json={**valid_body, "rateio_method": "consumption"},
    )

    assert unknown_id.status_code == 404
    assert invalid_combination.status_code == 422


def test_financial_dashboard_uses_only_unique_term_amount_per_current_document(client_and_session) -> None:
    client, session_factory = client_and_session
    session = session_factory()
    january = SourceDocument(
        source_key="local-copy-2026",
        relative_path="SERVIÇO/BRK/BRK - 01 - JANEIRO - SRA.pdf",
        original_filename="BRK - 01 - JANEIRO - SRA.pdf",
        sha256="b" * 64,
        byte_size=256,
        processing_state="review",
    )
    february_ambiguous = SourceDocument(
        source_key="local-copy-2026",
        relative_path="SERVIÇO/BRK/BRK - 02 - FEVEREIRO - CGU.pdf",
        original_filename="BRK - 02 - FEVEREIRO - CGU.pdf",
        sha256="c" * 64,
        byte_size=256,
        processing_state="review",
    )
    invoice_only = SourceDocument(
        source_key="local-copy-2026",
        relative_path="SERVIÇO/BRK/BRK - 03 - MARÇO - IBGE.pdf",
        original_filename="BRK - 03 - MARÇO - IBGE.pdf",
        sha256="d" * 64,
        byte_size=256,
        processing_state="review",
    )
    session.add_all([january, february_ambiguous, invoice_only])
    session.flush()

    def add_candidate(document: SourceDocument, field_name: str, value: str) -> None:
        session.add(
            ExtractionCandidate(
                document_id=document.id,
                field_name=field_name,
                raw_value=value,
                normalized_value=value,
                extraction_method="test_fixture",
                evidence_location="page:1",
                review_state="candidate",
            )
        )

    add_candidate(january, "reimbursement_term_amount_brl", "100.00")
    add_candidate(january, "invoice_amount_brl", "125.00")
    add_candidate(january, "organization_reference", "1")
    add_candidate(january, "service_reference", "1")
    add_candidate(january, "material_reference", "1")
    add_candidate(january, "supplier_reference", "1")
    add_candidate(february_ambiguous, "reimbursement_term_amount_brl", "80.00")
    add_candidate(february_ambiguous, "reimbursement_term_amount_brl", "90.00")
    add_candidate(february_ambiguous, "organization_reference", "2")
    add_candidate(invoice_only, "invoice_amount_brl", "50.00")
    add_candidate(invoice_only, "organization_reference", "10")
    session.commit()
    session.close()

    response = client.get("/api/v1/dashboard/financial-candidates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["confirmed_spending"] is False
    assert payload["included_term_documents"] == 1
    assert payload["total_candidate_amount"] == "100.00"
    assert payload["ambiguous_term_documents"] == 1
    assert payload["documents_without_term_amount"] == 1
    assert payload["by_organization"][0] == {"name": "SRA", "amount": "100.00", "documents": 1}
    assert len(payload["by_organization"]) == 11
    assert payload["by_month"][0] == {
        "month": "Janeiro", "month_number": 1, "amount": "100.00", "documents": 1,
    }
    assert payload["by_month"][1]["amount"] == "0.00"
    assert payload["by_service"][0]["name"] == "ÁGUA E ESGOTO - BRK - ART CACHOEIRO DE ITAPEMIRIM"
    assert payload["by_material"][0] == {"name": "AÇÚCAR", "amount": "100.00", "documents": 1}
    assert len(payload["by_material"]) == 6
    assert payload["by_supplier"][0] == {"name": "BRK", "amount": "100.00", "documents": 1}
    assert len(payload["by_supplier"]) == 22


def test_invoice_document_cards_group_by_supplier_and_material(client_and_session) -> None:
    client, session_factory = client_and_session
    session = session_factory()
    supplier_document = SourceDocument(
        source_key="local-copy-2026",
        relative_path="EXECUTADO & PROGRAMADO/SERVIÇO/ÁGUA E ESGOTO - SAAE - ART SÃO MATEUS/SAAE - 03 - MARÇO - SÃO MATEUS.pdf",
        original_filename="SAAE - 03 - MARÇO - SÃO MATEUS.pdf",
        sha256="e" * 64,
        byte_size=100,
        media_type="application/pdf",
        processing_state="review",
        invoice_workflow_state="invoices",
    )
    material_document = SourceDocument(
        source_key="local-copy-2026",
        relative_path="EXECUTADO & PROGRAMADO/MATERIAL/COMBUSTÍVEL/COMBUSTÍVEL - MAIO.pdf",
        original_filename="COMBUSTÍVEL - MAIO.pdf",
        sha256="f" * 64,
        byte_size=120,
        media_type="application/pdf",
        processing_state="review",
        invoice_workflow_state="invoices",
    )
    session.add_all([supplier_document, material_document])
    session.flush()
    session.add_all([
        ExtractionCandidate(
            document_id=supplier_document.id,
            field_name="reimbursement_term_amount_brl",
            raw_value="124,50",
            normalized_value="124.50",
            extraction_method="pdf_native_text",
            evidence_location="page:3",
            review_state="candidate",
        ),
        ExtractionCandidate(
            document_id=supplier_document.id,
            field_name="invoice_amount_brl",
            raw_value="150,00",
            normalized_value="150.00",
            extraction_method="pdf_native_text",
            evidence_location="page:1",
            review_state="candidate",
        ),
        ExtractionCandidate(
            document_id=supplier_document.id,
            field_name="supplier_reference",
            raw_value="SAAE",
            normalized_value="3",
            extraction_method="user_catalog:pdf_native",
            evidence_location="page:2",
            review_state="candidate",
        ),
        ExtractionCandidate(
            document_id=material_document.id,
            field_name="invoice_amount_brl",
            raw_value="90,00",
            normalized_value="90.00",
            extraction_method="pdf_native_text",
            evidence_location="page:1",
            review_state="candidate",
        ),
    ])
    session.commit()
    session.close()

    supplier_payload = client.get("/api/v1/invoice-documents?group_by=supplier&limit=20").json()
    material_payload = client.get("/api/v1/invoice-documents?group_by=material&limit=20").json()

    supplier_card = next(item for item in supplier_payload["items"] if item["filename"] == supplier_document.original_filename)
    material_card = next(item for item in material_payload["items"] if item["filename"] == material_document.original_filename)
    assert supplier_payload["page"]["total"] == 2
    assert supplier_card["group_name"] == "SAAE"
    assert supplier_card["service_associated"] == "ÁGUA E ESGOTO - SAAE - ART SÃO MATEUS"
    assert supplier_card["amount"] == "124.50"
    assert supplier_card["amount_source"] == "Termo de recebimento · preferencial"
    assert supplier_card["review_state"] == "invoices"
    assert supplier_card["invoice_workflow_state"] == "invoices"
    assert supplier_card["pending_review"] is False
    assert supplier_card["amount_comparison"] == "different"
    assert supplier_card["invoice_amount_candidates"][0]["normalized_value"] == "150.00"
    assert supplier_card["term_amount_candidates"][0]["normalized_value"] == "124.50"
    assert {candidate["field_name"] for candidate in supplier_card["amount_candidates"]} == {
        "reimbursement_term_amount_brl", "invoice_amount_brl",
    }
    pending_payload = client.get("/api/v1/invoice-documents?pending_only=true&limit=20").json()
    assert pending_payload["page"]["total"] == 0
    assert pending_payload["all_cards_are_unconfirmed_candidates"] is True
    assert material_card["group_name"] == "COMBUSTÍVEL"
    assert material_card["amount"] == "90.00"
    assert material_card["amount_source"] == "Fatura · secundário"
    assert material_card["amount_comparison"] == "incomplete"


def test_quarantined_invoice_requires_complete_unique_candidates_before_release_and_can_return(client_and_session) -> None:
    client, session_factory = client_and_session
    session = session_factory()
    document = SourceDocument(
        source_key="local-copy-2026",
        relative_path="EXECUTADO & PROGRAMADO/MATERIAL/COMBUSTÍVEL/COMBUSTÍVEL - 05 - MAIO.pdf",
        original_filename="COMBUSTÍVEL - 05 - MAIO.pdf",
        sha256="b" * 64,
        byte_size=150,
        media_type="application/pdf",
        processing_state="review",
    )
    session.add(document)
    session.commit()
    document_id = str(document.id)
    session.close()

    initially_pending = client.get("/api/v1/invoice-documents?pending_only=true").json()
    initially_invoices = client.get("/api/v1/invoice-documents?pending_only=false").json()
    card = next(item for item in initially_pending["items"] if item["id"] == document_id)
    assert card["invoice_workflow_state"] == "quarantined"
    assert card["release_ready"] is False
    assert initially_invoices["page"]["total"] == 0

    incomplete = client.post(
        f"/api/v1/source-documents/{document_id}/release-to-invoices",
        json={"reason": "Revisão inicial concluída."},
    )
    assert incomplete.status_code == 409
    assert "missing" in incomplete.json()["detail"]

    session = session_factory()
    session.add_all([
        ExtractionCandidate(
            document_id=document.id,
            field_name="invoice_amount_brl",
            raw_value="6.940,22",
            normalized_value="6940.22",
            amount_role="total_amount",
            extraction_method="manual_proposal",
            evidence_location="manual_proposal:new_field",
            review_state="candidate",
        ),
        ExtractionCandidate(
            document_id=document.id,
            field_name="process_number",
            raw_value="10783.000158/2024-59",
            normalized_value="10783.000158/2024-59",
            extraction_method="manual_proposal",
            evidence_location="manual_proposal:new_field",
            review_state="candidate",
        ),
        ExtractionCandidate(
            document_id=document.id,
            field_name="due_date",
            raw_value="27/03/2026",
            normalized_value="2026-03-27",
            extraction_method="manual_proposal",
            evidence_location="manual_proposal:new_field",
            review_state="candidate",
        ),
        ExtractionCandidate(
            document_id=document.id,
            field_name="organization_reference",
            raw_value="SRA",
            normalized_value="1",
            extraction_method="manual_proposal",
            evidence_location="manual_proposal:new_field",
            review_state="candidate",
        ),
    ])
    session.commit()
    session.close()

    ready_card = client.get("/api/v1/invoice-documents?pending_only=true").json()
    ready_card = next(item for item in ready_card["items"] if item["id"] == document_id)
    assert ready_card["release_ready"] is True
    released = client.post(
        f"/api/v1/source-documents/{document_id}/release-to-invoices",
        json={"reason": "Campos conferidos visualmente com o documento."},
    )
    assert released.status_code == 200
    assert released.json()["invoice_workflow_state"] == "invoices"
    assert client.get("/api/v1/invoice-documents?pending_only=true").json()["page"]["total"] == 0
    invoice_cards = client.get("/api/v1/invoice-documents?pending_only=false").json()
    assert invoice_cards["page"]["total"] == 1
    assert invoice_cards["items"][0]["pending_review"] is False

    returned = client.post(
        f"/api/v1/source-documents/{document_id}/return-to-review",
        json={"reason": "Solicitada nova conferência do vínculo de processo."},
    )
    assert returned.status_code == 200
    assert returned.json()["invoice_workflow_state"] == "quarantined"
    assert client.get("/api/v1/invoice-documents?pending_only=true").json()["page"]["total"] == 1

    session = session_factory()
    events = session.scalars(select(AuditEvent)).all()
    final_document = session.get(SourceDocument, document.id)
    session.close()
    assert final_document is not None
    assert final_document.invoice_workflow_state == "quarantined"
    assert {event.action for event in events} == {
        "invoice_document_released_from_quarantine",
        "invoice_document_returned_to_review",
    }


def test_open_pdf_streams_only_matching_hash_under_configured_root(client_and_session, tmp_path: Path) -> None:
    client, session_factory = client_and_session
    root = tmp_path / "approved-root"
    relative_path = Path("MATERIAL") / "arquivo.pdf"
    source_file = root / relative_path
    source_file.parent.mkdir(parents=True)
    content = b"%PDF-1.4\nread-only test pdf\n%%EOF"
    source_file.write_bytes(content)
    document = SourceDocument(
        source_key="local-copy-2026",
        relative_path=relative_path.as_posix(),
        original_filename="arquivo.pdf",
        sha256=hashlib.sha256(content).hexdigest(),
        byte_size=len(content),
        media_type="application/pdf",
        processing_state="review",
    )
    session = session_factory()
    session.add(document)
    session.commit()
    document_id = str(document.id)
    session.close()

    client.app.state.file_monitor = SimpleNamespace(root=root)
    response = client.get(f"/api/v1/source-documents/{document_id}/open")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert "inline" in response.headers["content-disposition"]
    assert response.content == content
    assert source_file.read_bytes() == content


def test_open_pdf_rejects_changed_file_hash(client_and_session, tmp_path: Path) -> None:
    client, session_factory = client_and_session
    root = tmp_path / "approved-root"
    source_file = root / "altered.pdf"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"changed content")
    document = SourceDocument(
        source_key="local-copy-2026",
        relative_path="altered.pdf",
        original_filename="altered.pdf",
        sha256="0" * 64,
        byte_size=len(b"old content"),
        media_type="application/pdf",
        processing_state="review",
    )
    session = session_factory()
    session.add(document)
    session.commit()
    document_id = str(document.id)
    session.close()
    client.app.state.file_monitor = SimpleNamespace(root=root)

    response = client.get(f"/api/v1/source-documents/{document_id}/open")

    assert response.status_code == 409


def test_candidate_correction_appends_proposal_without_confirming_or_overwriting(client_and_session) -> None:
    client, session_factory = client_and_session
    session = session_factory()
    document = SourceDocument(
        source_key="local-copy-2026",
        relative_path="EXECUTADO & PROGRAMADO/SERVIÇO/BRK/BRK - 01 - JANEIRO - SRA.pdf",
        original_filename="BRK - 01 - JANEIRO - SRA.pdf",
        sha256="9" * 64,
        byte_size=100,
        processing_state="review",
    )
    session.add(document)
    session.flush()
    original = ExtractionCandidate(
        document_id=document.id,
        field_name="reimbursement_term_amount_brl",
        raw_value="1.250,00",
        normalized_value="1250.00",
        extraction_method="pdf_native_text",
        evidence_location="page:3",
        review_state="candidate",
    )
    session.add(original)
    session.commit()
    original_id = str(original.id)
    session.close()

    request_body = {
        "corrected_value": "1.200,00",
        "reason": "O termo apresenta o valor líquido de reembolso.",
        "amount_basis": "net",
    }
    response = client.post(f"/api/v1/extraction-candidates/{original_id}/propose-correction", json=request_body)
    duplicate_response = client.post(f"/api/v1/extraction-candidates/{original_id}/propose-correction", json=request_body)

    assert response.status_code == 200
    assert duplicate_response.status_code == 200
    assert response.json()["normalized_value"] == "1200.00"
    assert response.json()["amount_basis"] == "net"
    assert response.json()["confirmed"] is False
    assert duplicate_response.json()["duplicate"] is True

    session = session_factory()
    stored_candidates = session.scalars(
        select(ExtractionCandidate).where(ExtractionCandidate.document_id == document.id)
    ).all()
    audit_events = session.scalars(select(AuditEvent)).all()
    session.close()
    assert len(stored_candidates) == 2
    assert stored_candidates[0].raw_value == "1.250,00"
    proposal = next(candidate for candidate in stored_candidates if candidate.extraction_method == "manual_proposal")
    assert proposal.review_state == "candidate"
    assert proposal.amount_basis == "net"
    assert proposal.evidence_location == f"manual_proposal:prior:{original_id}"
    assert len(audit_events) == 1
    assert audit_events[0].action == "candidate_correction_proposed"
    assert audit_events[0].after_state["reason"] == request_body["reason"]


def test_manual_missing_amount_field_is_append_only_deduplicated_and_basis_aware(client_and_session) -> None:
    client, session_factory = client_and_session
    session = session_factory()
    document = SourceDocument(
        source_key="local-copy-2026",
        relative_path="EXECUTADO & PROGRAMADO/SERVIÇO/BRK/documento.pdf",
        original_filename="documento.pdf",
        sha256="7" * 64,
        byte_size=100,
        processing_state="error",
    )
    session.add(document)
    session.commit()
    document_id = str(document.id)
    session.close()

    endpoint = f"/api/v1/source-documents/{document_id}/propose-correction"
    gross = {
        "field_name": "invoice_amount_brl",
        "corrected_value": "1.250,00",
        "amount_basis": "gross",
        "reason": "A fatura indica o valor bruto.",
    }
    first = client.post(endpoint, json=gross)
    repeated = client.post(endpoint, json=gross)
    net = {**gross, "amount_basis": "net", "reason": "O termo indica o valor líquido."}
    second_basis = client.post(endpoint, json=net)

    assert first.status_code == 200
    assert first.json()["confirmed"] is False
    assert first.json()["amount_basis"] == "gross"
    assert repeated.json()["duplicate"] is True
    assert second_basis.status_code == 200
    assert second_basis.json()["duplicate"] is False

    session = session_factory()
    proposals = session.scalars(
        select(ExtractionCandidate).where(ExtractionCandidate.document_id == document.id)
    ).all()
    audit_events = session.scalars(select(AuditEvent)).all()
    session.close()
    assert len(proposals) == 2
    assert {candidate.amount_basis for candidate in proposals} == {"gross", "net"}
    assert len(audit_events) == 2
    assert all(event.action == "candidate_manual_field_proposed" for event in audit_events)

    cards = client.get("/api/v1/invoice-documents?pending_only=true&limit=10").json()
    card = next(item for item in cards["items"] if item["id"] == document_id)
    assert card["pending_review"] is True
    assert card["amount"] is None
    assert card["amount_ambiguous"] is True
    assert {candidate["amount_basis"] for candidate in card["amount_candidates"]} == {"gross", "net"}


def test_percentage_proposal_is_persisted_separately_and_excluded_from_financial_totals(client_and_session) -> None:
    client, session_factory = client_and_session
    session = session_factory()
    document = SourceDocument(
        source_key="local-copy-2026",
        relative_path="EXECUTADO & PROGRAMADO/SERVIÇO/BRK/BRK - 02 - FEVEREIRO - SRA.pdf",
        original_filename="BRK - 02 - FEVEREIRO - SRA.pdf",
        sha256="a" * 64,
        byte_size=100,
        processing_state="review",
    )
    session.add(document)
    session.flush()
    original = ExtractionCandidate(
        document_id=document.id,
        field_name="reimbursement_term_amount_brl",
        raw_value="5,5%",
        normalized_value="5.50",
        extraction_method="pdf_native_text",
        evidence_location="page:2",
        review_state="candidate",
    )
    session.add(original)
    session.commit()
    document_id = str(document.id)
    original_id = str(original.id)
    session.close()

    response = client.post(
        f"/api/v1/extraction-candidates/{original_id}/propose-correction",
        json={
            "corrected_value": "5,5%",
            "reason": "O campo da fatura identifica uma alíquota percentual.",
            "amount_role": "percentage",
            "amount_basis": "gross",
        },
    )

    assert response.status_code == 200
    assert response.json()["normalized_value"] == "5.5"
    assert response.json()["amount_role"] == "percentage"
    assert response.json()["amount_basis"] is None
    assert response.json()["confirmed"] is False

    session = session_factory()
    proposed = session.scalar(
        select(ExtractionCandidate).where(ExtractionCandidate.extraction_method == "manual_proposal")
    )
    assert proposed is not None
    assert proposed.amount_role == "percentage"
    assert proposed.amount_basis is None
    original_after_proposal = session.get(ExtractionCandidate, original.id)
    assert original_after_proposal is not None
    assert original_after_proposal.amount_role is None
    session.close()

    cards = client.get("/api/v1/invoice-documents?pending_only=true&limit=10").json()
    card = next(item for item in cards["items"] if item["id"] == document_id)
    assert any(candidate["amount_role"] == "percentage" for candidate in card["amount_candidates"])
    dashboard = client.get("/api/v1/dashboard/financial-candidates").json()
    assert dashboard["included_term_documents"] == 0
    assert dashboard["documents_without_term_amount"] == 1


def test_candidate_correction_rejects_invalid_catalog_and_process_values(client_and_session) -> None:
    client, session_factory = client_and_session
    session = session_factory()
    document = SourceDocument(
        source_key="local-copy-2026",
        relative_path="SERVIÇO/teste.pdf",
        original_filename="teste.pdf",
        sha256="8" * 64,
        byte_size=100,
        processing_state="review",
    )
    session.add(document)
    session.flush()
    candidates = [
        ExtractionCandidate(
            document_id=document.id,
            field_name=field_name,
            raw_value="original",
            extraction_method="pdf_native_text",
            evidence_location="page:1",
            review_state="candidate",
        )
        for field_name in ("organization_reference", "process_number")
    ]
    session.add_all(candidates)
    session.commit()
    candidate_ids = {candidate.field_name: str(candidate.id) for candidate in candidates}
    session.close()

    bad_org = client.post(
        f"/api/v1/extraction-candidates/{candidate_ids['organization_reference']}/propose-correction",
        json={"corrected_value": "ÓRGÃO INVENTADO", "reason": "Corrigindo o nome do órgão"},
    )
    bad_process = client.post(
        f"/api/v1/extraction-candidates/{candidate_ids['process_number']}/propose-correction",
        json={"corrected_value": "SEI-123", "reason": "Corrigindo o processo"},
    )

    assert bad_org.status_code == 422
    assert bad_process.status_code == 422
