"""Metadata-only recursive inventory for an explicitly authorized local copy."""

from collections import Counter
import json
import os
from pathlib import Path
import sys


def inventory(root: Path) -> dict[str, object]:
    """Count files and sizes by extension and folder hierarchy, without opening files."""
    resolved = root.expanduser().resolve(strict=True)
    if not resolved.is_dir():
        raise NotADirectoryError("inventory_root_must_be_directory")

    extension_counts: Counter[str] = Counter()
    extension_bytes: Counter[str] = Counter()
    directory_counts: Counter[str] = Counter()
    total_files = 0
    total_bytes = 0
    errors = 0
    max_depth = 0

    for current, directories, filenames in os.walk(resolved, followlinks=False, onerror=lambda _: None):
        current_path = Path(current)
        directories[:] = [name for name in directories if not (current_path / name).is_symlink()]
        try:
            relative_dir = current_path.relative_to(resolved)
        except ValueError:
            errors += 1
            continue
        depth = len(relative_dir.parts)
        max_depth = max(max_depth, depth)
        for filename in filenames:
            path = current_path / filename
            if path.is_symlink():
                continue
            ext = path.suffix.lower() or "(sem extensão)"
            try:
                size = path.stat().st_size
            except OSError:
                errors += 1
                continue
            total_files += 1
            total_bytes += size
            extension_counts[ext] += 1
            extension_bytes[ext] += size
            folder = relative_dir.parts
            if folder:
                directory_counts[" / ".join(folder[: min(3, len(folder))])] += 1
            else:
                directory_counts["(raiz)"] += 1

    return {
        "root": str(resolved),
        "files": total_files,
        "total_bytes": total_bytes,
        "errors": errors,
        "max_directory_depth": max_depth,
        "extensions": [
            {"extension": ext, "files": count, "bytes": extension_bytes[ext]}
            for ext, count in extension_counts.most_common()
        ],
        "directories": [
            {"path": folder, "files": count}
            for folder, count in directory_counts.most_common(500)
        ],
        "directory_group_count": len(directory_counts),
        "directory_group_truncated": len(directory_counts) > 500,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso interno: python -m app.inventory_local <raiz-autorizada>", file=sys.stderr)
        return 2
    try:
        result = inventory(Path(sys.argv[1]))
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": type(exc).__name__}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
