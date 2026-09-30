"""Read-only Windows directory event monitor for an explicitly approved root."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
from pathlib import Path
import queue
import threading
import time
from collections.abc import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from sqlalchemy import select

from app.db import SessionLocal
from app.extractor import ExtractionResult, FieldCandidate, extract_document, persist_candidates
from app.models import SourceDocument
from app.scanner import DiscoveredFile, ScanReport, index_scan_report

LOGGER = logging.getLogger(__name__)
MONITORED_EXTENSIONS = frozenset({".pdf", ".xls", ".xlsx", ".xlsm", ".docx", ".xml", ".csv"})
SOURCE_KEY = "local-copy-2026"
MAX_FILE_BYTES = 100 * 1024 * 1024
STABLE_INTERVAL_SECONDS = 0.5
STABLE_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class MonitorStatus:
    """Safe operational status that never reveals the local absolute path."""

    running: bool
    source_key: str
    queued: int
    indexed: int
    parsed: int
    refreshed: int
    skipped: int
    errors: int
    last_event_at: str | None
    last_error_code: str | None


class _Handler(FileSystemEventHandler):
    def __init__(self, monitor: "DirectoryMonitor") -> None:
        self._monitor = monitor

    def on_created(self, event: FileSystemEvent) -> None:
        self._monitor.enqueue_event(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._monitor.enqueue_event(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        self._monitor.enqueue_event(event, moved=True)


class DirectoryMonitor:
    """Observe new/changed supported files and index metadata only.

    Existing files are deliberately not traversed at startup. Paths are held only
    in process memory; persisted records contain relative paths, SHA-256 and file
    metadata, never document contents or absolute root paths.
    """

    def __init__(
        self,
        root: Path,
        source_key: str = SOURCE_KEY,
        session_factory: Callable = SessionLocal,
    ) -> None:
        resolved = Path(root).expanduser().resolve(strict=True)
        if not resolved.is_dir():
            raise NotADirectoryError("monitor_root_must_be_directory")
        if not source_key or len(source_key) > 128:
            raise ValueError("invalid_source_key")
        self.root = resolved
        self.source_key = source_key
        self._session_factory = session_factory
        self._queue: queue.Queue[Path | None] = queue.Queue()
        self._pending: set[Path] = set()
        self._lock = threading.Lock()
        self._observer = Observer()
        self._worker: threading.Thread | None = None
        self._running = False
        self._indexed = 0
        self._parsed = 0
        self._refreshed = 0
        self._skipped = 0
        self._errors = 0
        self._last_event_at: str | None = None
        self._last_error_code: str | None = None

    def enqueue_event(self, event: FileSystemEvent, moved: bool = False) -> None:
        if event.is_directory:
            return
        source = getattr(event, "dest_path", None) if moved else None
        source = source or event.src_path
        candidate = Path(source)
        if candidate.suffix.lower() not in MONITORED_EXTENSIONS:
            return
        with self._lock:
            if not self._running or candidate in self._pending:
                return
            self._pending.add(candidate)
            self._last_event_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._queue.put(candidate)

    def start(self) -> None:
        if self._running:
            return
        self._observer.schedule(_Handler(self), str(self.root), recursive=True)
        self._running = True
        self._worker = threading.Thread(target=self._worker_loop, name="sig-es-file-indexer", daemon=True)
        self._worker.start()
        self._observer.start()
        LOGGER.info("Read-only directory monitor started (source_key=%s)", self.source_key)

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._observer.stop()
        self._queue.put(None)
        self._observer.join(timeout=10)
        if self._worker:
            self._worker.join(timeout=10)
        LOGGER.info("Read-only directory monitor stopped (source_key=%s)", self.source_key)

    def status(self) -> MonitorStatus:
        with self._lock:
            return MonitorStatus(
                running=self._running,
                source_key=self.source_key,
                queued=self._queue.qsize(),
                indexed=self._indexed,
                parsed=self._parsed,
                refreshed=self._refreshed,
                skipped=self._skipped,
                errors=self._errors,
                last_event_at=self._last_event_at,
                last_error_code=self._last_error_code,
            )

    def _worker_loop(self) -> None:
        while True:
            candidate = self._queue.get()
            if candidate is None:
                self._queue.task_done()
                return
            try:
                discovered = self._stable_file(candidate)
                if discovered is None:
                    with self._lock:
                        self._skipped += 1
                    continue
                session = self._session_factory()
                try:
                    result = index_scan_report(
                        session,
                        ScanReport(files=(discovered,), issues=()),
                    )
                    source_document = session.scalar(
                        select(SourceDocument).where(
                            SourceDocument.source_key == discovered.source_key,
                            SourceDocument.relative_path == discovered.relative_path,
                            SourceDocument.sha256 == discovered.sha256,
                        )
                    )
                    if source_document is None:
                        raise RuntimeError("indexed_source_document_missing")
                    try:
                        extraction = extract_document(candidate)
                    except ValueError as exc:
                        if str(exc) != "unsupported_document_type":
                            raise
                        extraction = ExtractionResult(
                            "unsupported_document_type", (), ("manual_review_required",)
                        )
                    verified_after = self._stable_file(candidate)
                    if verified_after is None or verified_after.sha256 != discovered.sha256:
                        raise ValueError("file_changed_during_extraction")
                    warning_candidates = tuple(
                        FieldCandidate(
                            field_name="parser_warning",
                            raw_value=warning,
                            normalized_value=None,
                            extraction_method=extraction.parser,
                            evidence_location="document",
                            confidence=None,
                        )
                        for warning in extraction.warnings
                    )
                    parent = Path(discovered.relative_path).parent.as_posix()
                    directory_candidates = (
                        (
                            FieldCandidate(
                                field_name="directory_classification_hint",
                                raw_value=parent,
                                normalized_value=None,
                                extraction_method="relative_folder_path_unverified",
                                evidence_location="relative_path",
                                confidence=None,
                            ),
                        )
                        if parent != "."
                        else ()
                    )
                    proposed = extraction.candidates + warning_candidates + directory_candidates
                    persist_candidates(session, source_document.id, proposed)
                    source_document.processing_state = "review" if proposed else "complete"
                    session.commit()
                finally:
                    session.close()
                with self._lock:
                    self._indexed += result.inserted
                    self._parsed += 1
                    self._refreshed += result.refreshed
                    self._last_error_code = None
            except Exception as exc:  # Keep worker alive; don't log path or file content.
                code = type(exc).__name__[:64]
                with self._lock:
                    self._errors += 1
                    self._last_error_code = code
                LOGGER.warning("Directory monitor event failed (code=%s)", code)
            finally:
                with self._lock:
                    self._pending.discard(candidate)
                self._queue.task_done()

    def _stable_file(self, candidate: Path) -> DiscoveredFile | None:
        deadline = time.monotonic() + STABLE_TIMEOUT_SECONDS
        previous: tuple[int, int, int] | None = None
        while time.monotonic() < deadline:
            try:
                if candidate.is_symlink():
                    return None
                resolved = candidate.resolve(strict=True)
                relative = resolved.relative_to(self.root).as_posix()
                if not resolved.is_file():
                    return None
                before = resolved.stat()
                if before.st_size > MAX_FILE_BYTES:
                    return None
                snapshot = (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                if snapshot == previous:
                    digest = hashlib.sha256()
                    with resolved.open("rb") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                    after = resolved.stat()
                    after_snapshot = (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                    if snapshot != after_snapshot:
                        previous = None
                        continue
                    import mimetypes

                    return DiscoveredFile(
                        source_key=self.source_key,
                        relative_path=relative,
                        original_filename=resolved.name,
                        sha256=digest.hexdigest(),
                        byte_size=after.st_size,
                        media_type=mimetypes.guess_type(resolved.name)[0],
                    )
                previous = snapshot
            except (FileNotFoundError, PermissionError, OSError, ValueError):
                return None
            time.sleep(STABLE_INTERVAL_SECONDS)
        return None


def make_monitor(root: str | None) -> DirectoryMonitor | None:
    """Create and start monitoring only when an explicit root is configured."""
    if not root:
        return None
    monitor = DirectoryMonitor(Path(root))
    monitor.start()
    return monitor
