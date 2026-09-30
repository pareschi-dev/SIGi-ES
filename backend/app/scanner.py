"""Read-only discovery and idempotent indexing of files under an explicit root.

This module does not extract document contents or modify source files. Callers must
provide an authorized root; no institutional path is configured as a default.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import mimetypes
import os
from pathlib import Path
import re
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SourceDocument

DEFAULT_EXTENSIONS = frozenset({".pdf", ".xls", ".xlsx", ".xlsm", ".docx", ".xml", ".csv"})
SOURCE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    """Safe metadata for one stable file discovered during a scan."""

    source_key: str
    relative_path: str
    original_filename: str
    sha256: str
    byte_size: int
    media_type: str | None


@dataclass(frozen=True, slots=True)
class ScanIssue:
    """Non-fatal file-level issue represented without an absolute path."""

    relative_path: str
    code: str


@dataclass(frozen=True, slots=True)
class ScanReport:
    """Files and recoverable issues found by a single directory scan."""

    files: tuple[DiscoveredFile, ...]
    issues: tuple[ScanIssue, ...]


@dataclass(frozen=True, slots=True)
class IndexSummary:
    """Counts for idempotent persistence of a scan report."""

    inserted: int
    refreshed: int


def _validate_source_key(source_key: str) -> None:
    if not SOURCE_KEY_PATTERN.fullmatch(source_key):
        raise ValueError("source_key deve conter somente letras, números, ponto, hífen ou underscore")


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _hash_stable_file(path: Path) -> tuple[str, int]:
    """Hash a file in bounded memory and reject it if it changes while read."""
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_ctime_ns != after.st_ctime_ns
    ):
        raise RuntimeError("file_changed_during_scan")
    return digest.hexdigest(), after.st_size


def scan_directory(
    root: Path,
    source_key: str,
    *,
    allowed_extensions: Iterable[str] = DEFAULT_EXTENSIONS,
    max_file_bytes: int = 100 * 1024 * 1024,
) -> ScanReport:
    """Discover and hash eligible files beneath an explicitly supplied root.

    Symlinks are skipped, traversal is bounded to the resolved root, unsupported
    extensions are ignored, and source files are opened read-only. Files larger
    than ``max_file_bytes`` are reported but never read.
    """
    _validate_source_key(source_key)
    if max_file_bytes < 1:
        raise ValueError("max_file_bytes deve ser positivo")
    extensions = frozenset(
        ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        for ext in allowed_extensions
    )
    if not extensions:
        raise ValueError("é necessário informar ao menos uma extensão permitida")

    root_path = Path(root).expanduser().resolve(strict=True)
    if not root_path.is_dir():
        raise NotADirectoryError("a raiz informada não é um diretório")

    found: list[DiscoveredFile] = []
    issues: list[ScanIssue] = []
    for current, directories, filenames in os.walk(root_path, followlinks=False):
        current_path = Path(current)
        directories[:] = [
            name for name in directories
            if not (current_path / name).is_symlink()
        ]
        for filename in filenames:
            candidate = current_path / filename
            if candidate.is_symlink() or candidate.suffix.lower() not in extensions:
                continue
            try:
                resolved = candidate.resolve(strict=True)
                if not _is_inside(resolved, root_path) or not resolved.is_file():
                    issues.append(ScanIssue(candidate.relative_to(root_path).as_posix(), "outside_root_or_not_file"))
                    continue
                relative = resolved.relative_to(root_path).as_posix()
                initial_size = resolved.stat().st_size
                if initial_size > max_file_bytes:
                    issues.append(ScanIssue(relative, "file_too_large"))
                    continue
                digest, byte_size = _hash_stable_file(resolved)
                found.append(
                    DiscoveredFile(
                        source_key=source_key,
                        relative_path=relative,
                        original_filename=resolved.name,
                        sha256=digest,
                        byte_size=byte_size,
                        media_type=mimetypes.guess_type(resolved.name)[0],
                    )
                )
            except FileNotFoundError:
                issues.append(ScanIssue(candidate.relative_to(root_path).as_posix(), "file_disappeared"))
            except PermissionError:
                issues.append(ScanIssue(candidate.relative_to(root_path).as_posix(), "permission_denied"))
            except OSError:
                issues.append(ScanIssue(candidate.relative_to(root_path).as_posix(), "read_error"))
            except RuntimeError:
                issues.append(ScanIssue(candidate.relative_to(root_path).as_posix(), "file_changed_during_scan"))

    found.sort(key=lambda item: item.relative_path.casefold())
    issues.sort(key=lambda item: (item.relative_path.casefold(), item.code))
    return ScanReport(files=tuple(found), issues=tuple(issues))


def index_scan_report(session: Session, report: ScanReport) -> IndexSummary:
    """Insert or refresh discovered metadata using a stable idempotency key."""
    inserted = 0
    refreshed = 0
    now = datetime.now(timezone.utc)
    for item in report.files:
        statement = select(SourceDocument).where(
            SourceDocument.source_key == item.source_key,
            SourceDocument.relative_path == item.relative_path,
            SourceDocument.sha256 == item.sha256,
        )
        existing = session.scalar(statement)
        if existing is not None:
            existing.last_seen_at = now
            refreshed += 1
            continue
        session.add(
            SourceDocument(
                source_key=item.source_key,
                relative_path=item.relative_path,
                original_filename=item.original_filename,
                sha256=item.sha256,
                byte_size=item.byte_size,
                media_type=item.media_type,
                processing_state="discovered",
                first_seen_at=now,
                last_seen_at=now,
            )
        )
        inserted += 1
    session.commit()
    return IndexSummary(inserted=inserted, refreshed=refreshed)
