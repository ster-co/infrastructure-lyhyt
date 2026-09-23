"""Pure manifest, checksum, ledger, and SQLCMD batch helpers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Migration:
    sequence: int
    migration_id: str
    file: Path
    transactional: bool
    destructive: bool
    minimum_release: str


@dataclass(frozen=True)
class LedgerRow:
    sequence: int
    migration_id: str
    checksum: str
    applied_utc: str
    applying_identity: str
    release_version: str


class MigrationError(Exception):
    """Safe migration failure message suitable for CI logs."""


class DatabaseAdapter(Protocol):
    def ensure_ledger(self) -> None:
        ...

    def acquire_lock(self, name: str, timeout_ms: int) -> bool:
        ...

    def ledger_rows(self) -> list[LedgerRow]:
        ...

    def current_identity(self) -> str:
        ...

    def set_autocommit(self, enabled: bool) -> None:
        ...

    def begin(self) -> None:
        ...

    def execute_batch(self, sql: str) -> None:
        ...

    def insert_ledger(self, row: LedgerRow) -> None:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...

    def release_lock(self, name: str) -> None:
        ...

    def close(self) -> None:
        ...


_RELEASE = re.compile(r"^\d+(?:\.\d+)*$")
_GO = re.compile(r"^\s*GO(?:\s+\d+)?(?:\s+--.*)?\s*$", re.IGNORECASE)


def _release_key(value: str) -> tuple[int, ...]:
    if not isinstance(value, str) or not _RELEASE.fullmatch(value):
        raise ValueError(f"invalid release version: {value!r}")
    return tuple(int(part) for part in value.split("."))


def load_manifest(manifest_path: Path, repository_root: Path, release_version: str) -> list[Migration]:
    release_key = _release_key(release_version)
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid migration manifest") from exc
    if not isinstance(document, dict) or document.get("version") != 1:
        raise ValueError("migration manifest version must be 1")
    entries = document.get("migrations")
    if not isinstance(entries, list):
        raise ValueError("migration manifest migrations must be a list")

    root = repository_root.resolve()
    migrations: list[Migration] = []
    ids: set[str] = set()
    sequences: set[int] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("migration entries must be objects")
        required = ("sequence", "id", "file", "transactional", "destructive", "minimumRelease")
        if any(key not in entry for key in required):
            raise ValueError("migration entry is missing a required field")
        sequence = entry["sequence"]
        migration_id = entry["id"]
        relative_file = entry["file"]
        minimum_release = entry["minimumRelease"]
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise ValueError("migration sequence must be a positive integer")
        if not isinstance(migration_id, str) or not migration_id:
            raise ValueError("migration id must be a non-empty string")
        if migration_id in ids or sequence in sequences:
            raise ValueError("migration IDs and sequences must be unique")
        if not isinstance(relative_file, str) or not relative_file:
            raise ValueError("migration file must be a non-empty string")
        if not isinstance(entry["transactional"], bool) or not isinstance(entry["destructive"], bool):
            raise ValueError("transactional and destructive must be booleans")
        if _release_key(minimum_release) > release_key:
            raise ValueError(f"migration {migration_id} requires a newer release")
        path = (root / relative_file).resolve()
        if root not in path.parents or not path.is_file():
            raise ValueError(f"migration file is missing or outside repository: {relative_file}")
        ids.add(migration_id)
        sequences.add(sequence)
        migrations.append(Migration(sequence, migration_id, path, entry["transactional"], entry["destructive"], minimum_release))

    original_sequences = [migration.sequence for migration in migrations]
    if original_sequences != list(range(1, len(migrations) + 1)):
        raise ValueError("migration sequences must be ordered and contiguous starting at 1")
    return migrations


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_ledger_rows(rows: list[LedgerRow], migrations: list[Migration]) -> None:
    if len(rows) > len(migrations):
        raise ValueError("ledger contains more rows than the migration manifest")
    for index, row in enumerate(rows):
        migration = migrations[index]
        if (row.sequence, row.migration_id) != (migration.sequence, migration.migration_id):
            raise ValueError("ledger rows must be the contiguous applied migration prefix")
        expected_checksum = sha256_file(migration.file)
        if row.checksum.casefold() != expected_checksum.casefold():
            raise ValueError(f"checksum mismatch for migration {row.migration_id}")


def split_sqlcmd_batches(sql_text: str) -> list[str]:
    batches: list[str] = []
    current: list[str] = []
    in_string = False
    in_block_comment = False
    for line in sql_text.splitlines():
        if not in_string and not in_block_comment and _GO.fullmatch(line):
            batch = "".join(current).strip()
            if batch:
                batches.append(batch)
            current = []
            continue
        current.append(line + "\n")
        index = 0
        while index < len(line):
            if in_block_comment:
                if line[index:index + 2] == "*/":
                    in_block_comment = False
                    index += 2
                else:
                    index += 1
            elif in_string:
                if line[index:index + 2] == "''":
                    index += 2
                elif line[index] == "'":
                    in_string = False
                    index += 1
                else:
                    index += 1
            elif line[index:index + 2] == "--":
                break
            elif line[index:index + 2] == "/*":
                in_block_comment = True
                index += 2
            elif line[index] == "'":
                in_string = True
                index += 1
            else:
                index += 1
    batch = "".join(current).strip()
    if batch:
        batches.append(batch)
    return batches


def has_destructive_migrations(migrations: list[Migration]) -> bool:
    return any(migration.destructive for migration in migrations)
