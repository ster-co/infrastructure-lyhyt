"""Verify migration manifests and files without connecting to SQL."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.sql.migration_common import (
    Migration,
    has_destructive_migrations,
    load_manifest,
    sha256_file,
)


@dataclass(frozen=True)
class VerifiedMigration:
    sequence: int
    migration_id: str
    file: str
    checksum: str
    destructive: bool
    minimum_release: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "migrationId": self.migration_id,
            "file": self.file,
            "checksum": self.checksum,
            "destructive": self.destructive,
            "minimumRelease": self.minimum_release,
        }


@dataclass(frozen=True)
class VerificationResult:
    release_version: str
    has_destructive_migrations: bool
    migrations: list[VerifiedMigration]

    def to_dict(self) -> dict[str, Any]:
        return {
            "releaseVersion": self.release_version,
            "hasDestructiveMigrations": self.has_destructive_migrations,
            "migrations": [migration.to_dict() for migration in self.migrations],
        }


def _manifest_checksums(manifest_path: Path) -> dict[int, str]:
    """Return optional expected checksums without reimplementing manifest validation."""
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid migration manifest") from exc

    if not isinstance(document, dict) or not isinstance(document.get("migrations"), list):
        raise ValueError("invalid migration manifest")

    expected: dict[int, str] = {}
    for entry in document["migrations"]:
        if not isinstance(entry, dict) or "checksum" not in entry:
            continue
        checksum = entry["checksum"]
        sequence = entry.get("sequence")
        if (
            not isinstance(sequence, int)
            or isinstance(sequence, bool)
            or not isinstance(checksum, str)
            or len(checksum) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in checksum)
        ):
            raise ValueError("migration checksum must be a 64-character hexadecimal string")
        expected[sequence] = checksum
    return expected


def _verified_migration(migration: Migration, root: Path, expected_checksum: str | None) -> VerifiedMigration:
    try:
        checksum = sha256_file(migration.file)
    except (OSError, ValueError) as exc:
        raise ValueError(f"could not checksum migration {migration.migration_id}") from exc
    if expected_checksum is not None and checksum.casefold() != expected_checksum.casefold():
        raise ValueError(f"checksum mismatch for migration {migration.migration_id}")
    return VerifiedMigration(
        sequence=migration.sequence,
        migration_id=migration.migration_id,
        file=migration.file.resolve().relative_to(root.resolve()).as_posix(),
        checksum=checksum,
        destructive=migration.destructive,
        minimum_release=migration.minimum_release,
    )


def verify_manifest(manifest_path: Path, repository_root: Path, release_version: str) -> VerificationResult:
    """Load and verify a manifest and return only JSON-safe metadata."""
    migrations = load_manifest(manifest_path, repository_root, release_version)
    expected_checksums = _manifest_checksums(manifest_path)
    verified = [
        _verified_migration(migration, repository_root, expected_checksums.get(migration.sequence))
        for migration in migrations
    ]
    return VerificationResult(
        release_version=release_version,
        has_destructive_migrations=has_destructive_migrations(migrations),
        migrations=verified,
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify LYHYT customer SQL migrations")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--release-version", required=True)
    parser.add_argument("--output", choices=("json",), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = verify_manifest(args.manifest, Path.cwd(), args.release_version)
    except (OSError, ValueError) as exc:
        print(f"migration verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
