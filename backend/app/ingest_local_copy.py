"""Historical, local-only ingestion of explicitly approved files.

The command stores document metadata and unconfirmed extraction candidates in
SIG-ES. It never writes source files, classifies payment as confirmed, or calls
external services. Reports contain aggregate counts, not extracted values.
"""

from collections import Counter
from datetime import datetime, timezone
import contextlib
import io
import hashlib
import logging
import mimetypes
import os
from pathlib import Path
import sys
import time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.extractor import ExtractionResult, FieldCandidate, extract_document, persist_candidates
from app.models import ExtractionCandidate, SourceDocument
from app.scanner import DEFAULT_EXTENSIONS

SOURCE_KEY = "local-copy-2026"
MAX_FILE_BYTES = 100 * 1024 * 1024
PROGRESS_EVERY = 25
PDF_LOGGER = logging.getLogger("pypdf")


def _metadata(
    path: Path, root: Path
) -> tuple[str, str, int, str | None, tuple[int, int, int]] | None:
    """Hash a stable regular file; return only its relative metadata."""
    if path.is_symlink():
        return None
    try:
        resolved = path.resolve(strict=True)
        relative = resolved.relative_to(root).as_posix()
        if not resolved.is_file():
            return None
        before = resolved.stat()
        if before.st_size > MAX_FILE_BYTES:
            raise ValueError("file_too_large")
        digest = hashlib.sha256()
        with resolved.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        after = resolved.stat()
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ctime_ns != after.st_ctime_ns
        ):
            raise ValueError("file_changed_during_scan")
        signature = (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        return relative, digest.hexdigest(), after.st_size, mimetypes.guess_type(resolved.name)[0], signature
    except (FileNotFoundError, PermissionError, OSError) as exc:
        raise ValueError(type(exc).__name__) from exc


def _directory_candidate(relative_path: str) -> tuple[FieldCandidate, ...]:
    parent = Path(relative_path).parent.as_posix()
    if parent == ".":
        return ()
    return (
        FieldCandidate(
            field_name="directory_classification_hint",
            raw_value=parent,
            normalized_value=None,
            extraction_method="relative_folder_path_unverified",
            evidence_location="relative_path",
            confidence=None,
        ),
    )


def _get_or_create_document(
    session,
    *,
    relative: str,
    original_filename: str,
    sha256: str,
    byte_size: int,
    media_type: str | None,
) -> tuple[SourceDocument, bool]:
    existing = session.scalar(
        select(SourceDocument).where(
            SourceDocument.source_key == SOURCE_KEY,
            SourceDocument.relative_path == relative,
            SourceDocument.sha256 == sha256,
        )
    )
    now = datetime.now(timezone.utc)
    if existing is not None:
        existing.last_seen_at = now
        return existing, False
    document = SourceDocument(
        source_key=SOURCE_KEY,
        relative_path=relative,
        original_filename=original_filename,
        sha256=sha256,
        byte_size=byte_size,
        media_type=media_type,
        processing_state="discovered",
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(document)
    try:
        session.flush()
        return document, True
    except IntegrityError:
        session.rollback()
        concurrent = session.scalar(
            select(SourceDocument).where(
                SourceDocument.source_key == SOURCE_KEY,
                SourceDocument.relative_path == relative,
                SourceDocument.sha256 == sha256,
            )
        )
        if concurrent is None:
            raise
        concurrent.last_seen_at = now
        return concurrent, False


def ingest(root: Path, session_factory=SessionLocal) -> dict[str, object]:
    """Ingest supported documents recursively while preserving all source files."""
    resolved_root = root.expanduser().resolve(strict=True)
    if not resolved_root.is_dir():
        raise NotADirectoryError("ingest_root_must_be_directory")

    discovered = parsed = candidates_added = candidates_existing = 0
    unsupported = too_large_or_unstable = errors = no_candidate_files = 0
    extension_counts: Counter[str] = Counter()
    error_codes: Counter[str] = Counter()
    started = time.monotonic()
    session = session_factory()
    try:
        for current, directories, filenames in os.walk(
            resolved_root,
            followlinks=False,
            onerror=lambda exc: error_codes.update([type(exc).__name__]),
        ):
            current_path = Path(current)
            directories[:] = [name for name in directories if not (current_path / name).is_symlink()]
            for filename in filenames:
                path = current_path / filename
                if path.is_symlink():
                    continue
                extension = path.suffix.lower() or "(sem extensão)"
                try:
                    metadata = _metadata(path, resolved_root)
                    if metadata is None:
                        continue
                    relative, digest, byte_size, media_type, original_signature = metadata
                    discovered += 1
                    extension_counts[extension] += 1
                    document, created = _get_or_create_document(
                        session,
                        relative=relative,
                        original_filename=path.name,
                        sha256=digest,
                        byte_size=byte_size,
                        media_type=media_type,
                    )
                    if created:
                        session.commit()
                    with contextlib.redirect_stderr(io.StringIO()):
                        with contextlib.redirect_stdout(io.StringIO()):
                            if extension in DEFAULT_EXTENSIONS:
                                try:
                                    result = extract_document(path)
                                    parsed += 1
                                except ValueError as exc:
                                    if str(exc) != "unsupported_document_type":
                                        raise
                                    result = ExtractionResult(
                                        "unsupported_document_type", (), ("manual_review_required",)
                                    )
                                    unsupported += 1
                            else:
                                result = ExtractionResult(
                                    "unsupported_document_type", (), ("manual_review_required",)
                                )
                                unsupported += 1
                    current_stat = path.stat()
                    current_signature = (
                        current_stat.st_size,
                        current_stat.st_mtime_ns,
                        current_stat.st_ctime_ns,
                    )
                    if current_signature != original_signature:
                        raise ValueError("file_changed_during_extraction")
                    warning_candidates = tuple(
                        FieldCandidate(
                            field_name="parser_warning",
                            raw_value=warning,
                            normalized_value=None,
                            extraction_method=result.parser,
                            evidence_location="document",
                            confidence=None,
                        )
                        for warning in result.warnings
                    )
                    proposed = result.candidates + warning_candidates + _directory_candidate(relative)
                    added = persist_candidates(session, document.id, proposed)
                    candidates_added += added
                    candidates_existing += max(len(proposed) - added, 0)
                    document.processing_state = "review" if proposed or result.warnings else "complete"
                    session.commit()
                    if not result.candidates:
                        no_candidate_files += 1
                    if discovered % PROGRESS_EVERY == 0:
                        print(
                            f"Progresso local: {discovered} documentos; "
                            f"{candidates_added} candidatos novos; {errors} falhas.",
                            flush=True,
                        )
                except ValueError as exc:
                    session.rollback()
                    code = str(exc)[:80]
                    if code in {"file_too_large", "file_changed_during_scan"}:
                        too_large_or_unstable += 1
                    else:
                        errors += 1
                        error_codes[code] += 1
                except Exception as exc:
                    session.rollback()
                    errors += 1
                    error_codes[type(exc).__name__] += 1
                    try:
                        relative_path = path.relative_to(resolved_root).as_posix()
                        failed_document = session.scalar(
                            select(SourceDocument).where(
                                SourceDocument.source_key == SOURCE_KEY,
                                SourceDocument.relative_path == relative_path,
                            ).order_by(SourceDocument.last_seen_at.desc())
                        )
                        if failed_document is not None:
                            failed_document.processing_state = "error"
                            session.commit()
                    except Exception:
                        session.rollback()
    finally:
        session.close()

    return {
        "source_key": SOURCE_KEY,
        "files_discovered": discovered,
        "files_parsed": parsed,
        "files_without_candidates": no_candidate_files,
        "unsupported_files": unsupported,
        "too_large_or_unstable_files": too_large_or_unstable,
        "errors": errors,
        "candidates_added": candidates_added,
        "candidates_already_present_or_duplicate": candidates_existing,
        "extension_counts": dict(sorted(extension_counts.items())),
        "error_codes": dict(error_codes),
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python -m app.ingest_local_copy <raiz-autorizada>", file=sys.stderr)
        return 2
    try:
        report = ingest(Path(sys.argv[1]))
    except (OSError, ValueError) as exc:
        print(f"Ingestão não iniciada ({type(exc).__name__}); confirme a raiz autorizada.")
        return 1
    print("Resumo da ingestão local:")
    import json

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
