"""Safety and idempotence tests for read-only filesystem discovery."""

import hashlib
from pathlib import Path

import pytest

from app.models import SourceDocument
from app.scanner import index_scan_report, scan_directory


def test_scan_reads_allowed_extensions_without_changing_sources(tmp_path: Path) -> None:
    root = tmp_path / "source"
    nested = root / "SERVICO" / "ENERGIA"
    nested.mkdir(parents=True)
    pdf = nested / "fatura-sintetica.pdf"
    pdf.write_bytes(b"synthetic pdf fixture")
    (nested / "ignore.exe").write_bytes(b"not accepted")
    original_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()

    report = scan_directory(root, "test-source")

    assert len(report.files) == 1
    item = report.files[0]
    assert item.relative_path == "SERVICO/ENERGIA/fatura-sintetica.pdf"
    assert item.sha256 == original_hash
    assert item.byte_size == len(b"synthetic pdf fixture")
    assert pdf.read_bytes() == b"synthetic pdf fixture"
    assert report.issues == ()


def test_scan_reports_oversized_file_without_reading(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "large.pdf").write_bytes(b"123456")

    report = scan_directory(root, "test-source", max_file_bytes=5)

    assert report.files == ()
    assert report.issues[0].code == "file_too_large"
    assert report.issues[0].relative_path == "large.pdf"


def test_scan_rejects_unsafe_source_key(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()

    with pytest.raises(ValueError):
        scan_directory(root, "../untrusted")


def test_scan_skips_symlinked_directories(tmp_path: Path) -> None:
    root = tmp_path / "source"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "external.pdf").write_bytes(b"outside")
    link = root / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable in this Windows environment")

    report = scan_directory(root, "test-source")

    assert report.files == ()


def test_indexing_is_idempotent_and_tracks_replacement(tmp_path: Path, client_and_session) -> None:
    _, session_factory = client_and_session
    root = tmp_path / "source"
    root.mkdir()
    file_path = root / "invoice.pdf"
    file_path.write_bytes(b"version one")
    session = session_factory()

    first = scan_directory(root, "test-source")
    first_result = index_scan_report(session, first)
    second_result = index_scan_report(session, first)
    assert (first_result.inserted, first_result.refreshed) == (1, 0)
    assert (second_result.inserted, second_result.refreshed) == (0, 1)

    file_path.write_bytes(b"version two")
    replacement_result = index_scan_report(session, scan_directory(root, "test-source"))
    count = session.query(SourceDocument).count()
    session.close()

    assert replacement_result.inserted == 1
    assert count == 2
