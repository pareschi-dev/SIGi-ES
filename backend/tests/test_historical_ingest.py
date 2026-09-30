"""Tests for local historical ingestion into isolated SQLite."""

from pathlib import Path

from sqlalchemy import select

from app.ingest_local_copy import ingest
from app.models import ExtractionCandidate, SourceDocument


def test_ingest_persists_candidates_idempotently_and_preserves_sources(
    tmp_path: Path, client_and_session
) -> None:
    _, session_factory = client_and_session
    root = tmp_path / "copy-2026"
    folder = root / "EXECUTADO" / "SERVIÇO" / "ENERGIA"
    folder.mkdir(parents=True)
    csv_path = folder / "sintetica.csv"
    original = (
        "Campo;Valor\n"
        "Processo;12345.123456/2026-00\n"
        "Valor;R$ 1.234,56\n"
        "Vencimento;31/10/2026\n"
    ).encode("utf-8")
    csv_path.write_bytes(original)
    (root / "unknown.bin").write_bytes(b"synthetic unsupported file")

    first = ingest(root, session_factory=session_factory)
    second = ingest(root, session_factory=session_factory)

    session = session_factory()
    documents = session.scalars(select(SourceDocument).order_by(SourceDocument.relative_path)).all()
    candidates = session.scalars(select(ExtractionCandidate)).all()
    session.close()

    assert first["files_discovered"] == 2
    assert first["files_parsed"] == 1
    assert first["unsupported_files"] == 1
    assert first["candidates_added"] >= 4
    assert second["candidates_added"] == 0
    assert len(documents) == 2
    assert any(item.field_name == "process_number" and item.raw_value == "12345.123456/2026-00" for item in candidates)
    assert any(item.field_name == "directory_classification_hint" for item in candidates)
    assert all(item.review_state == "candidate" for item in candidates)
    assert all(item.confidence is None for item in candidates)
    assert csv_path.read_bytes() == original


def test_ingest_rejects_missing_root(tmp_path: Path) -> None:
    try:
        ingest(tmp_path / "missing")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("missing root must be rejected")
