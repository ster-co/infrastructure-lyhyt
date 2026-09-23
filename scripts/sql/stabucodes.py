"""Validate and plan idempotent imports for dbo.cc_stabucodes."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


CSV_FIELDS = ("code", "description", "parent_code")
CSV_FIELDS_WITH_IGNORED_LAST_ALTERED = (*CSV_FIELDS, "last_altered")
MAX_CODE_LENGTH = 10


class StabuCodesValidationError(ValueError):
    """Raised when a Stabu code source cannot be safely imported."""


@dataclass(frozen=True)
class StabuCode:
    code: str
    description: str
    parent_code: str | None


@dataclass(frozen=True)
class StabuImportPlan:
    inserts: tuple[StabuCode, ...]
    updated: tuple[StabuCode, ...]
    unchanged_count: int
    missing_from_csv: tuple[str, ...]


def _normalise_row(row_number: int, row: dict[str, str | None]) -> StabuCode:
    code = (row.get("code") or "").strip()
    description = row.get("description")
    description = description if description is not None else ""
    parent_code = (row.get("parent_code") or "").strip() or None

    if not code:
        raise StabuCodesValidationError(f"row {row_number}: code is required")
    if not description:
        raise StabuCodesValidationError(
            f"row {row_number}: description is required for code {code}"
        )
    if len(code) > MAX_CODE_LENGTH:
        raise StabuCodesValidationError(
            f"row {row_number}: code length exceeds {MAX_CODE_LENGTH} for {code}"
        )
    if parent_code is not None and len(parent_code) > MAX_CODE_LENGTH:
        raise StabuCodesValidationError(
            f"row {row_number}: parent_code length exceeds {MAX_CODE_LENGTH} for {code}"
        )
    if parent_code == code:
        raise StabuCodesValidationError(f"row {row_number}: code {code} cannot parent itself")
    return StabuCode(code, description, parent_code)


def _validate_unique(rows: Sequence[StabuCode], source_name: str) -> None:
    seen: set[str] = set()
    for row in rows:
        if row.code in seen:
            raise StabuCodesValidationError(f"{source_name}: duplicate code {row.code}")
        seen.add(row.code)


def _validate_no_source_cycles(rows: Sequence[StabuCode]) -> None:
    parents = {row.code: row.parent_code for row in rows}
    for start in parents:
        path: set[str] = set()
        current: str | None = start
        while current is not None and current in parents:
            if current in path:
                raise StabuCodesValidationError(
                    f"source contains a parent cycle involving {current}"
                )
            path.add(current)
            current = parents[current]


def load_stabucodes_csv(path: Path) -> tuple[StabuCode, ...]:
    """Load and validate a UTF-8 or UTF-8-BOM Stabu code CSV."""

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if tuple(reader.fieldnames or ()) not in (
                CSV_FIELDS,
                CSV_FIELDS_WITH_IGNORED_LAST_ALTERED,
            ):
                raise StabuCodesValidationError(
                    "CSV columns must be "
                    f"{','.join(CSV_FIELDS)} or "
                    f"{','.join(CSV_FIELDS_WITH_IGNORED_LAST_ALTERED)}"
                )
            rows = tuple(
                _normalise_row(row_number, row)
                for row_number, row in enumerate(reader, start=2)
            )
    except FileNotFoundError as exc:
        raise StabuCodesValidationError(f"CSV file does not exist: {path}") from exc
    except csv.Error as exc:
        raise StabuCodesValidationError(f"invalid CSV file: {path}") from exc

    _validate_unique(rows, "CSV")
    _validate_no_source_cycles(rows)
    return rows


def _validate_existing(rows: Sequence[StabuCode]) -> None:
    _validate_unique(rows, "database")
    for row in rows:
        if not row.code:
            raise StabuCodesValidationError("database contains a row with an empty code")
        if len(row.code) > MAX_CODE_LENGTH:
            raise StabuCodesValidationError(
                f"database code length exceeds {MAX_CODE_LENGTH} for {row.code}"
            )


def _ordered_inserts(
    source_rows: Sequence[StabuCode], existing_codes: set[str]
) -> tuple[StabuCode, ...]:
    pending = {row.code: row for row in source_rows if row.code not in existing_codes}
    available = set(existing_codes)
    ordered: list[StabuCode] = []

    while pending:
        ready = [
            row
            for row in source_rows
            if row.code in pending
            and (row.parent_code is None or row.parent_code in available)
        ]
        if not ready:
            raise StabuCodesValidationError(
                "could not order inserts because a parent is unavailable"
            )
        for row in ready:
            ordered.append(row)
            available.add(row.code)
            pending.pop(row.code)
    return tuple(ordered)


def plan_stabucode_import(
    source_rows: Sequence[StabuCode], existing_rows: Sequence[StabuCode]
) -> StabuImportPlan:
    """Validate source/database relationships and compute a deterministic diff."""

    _validate_unique(source_rows, "CSV")
    _validate_no_source_cycles(source_rows)
    _validate_existing(existing_rows)

    source_by_code = {row.code: row for row in source_rows}
    existing_by_code = {row.code: row for row in existing_rows}
    existing_codes = set(existing_by_code)
    source_codes = set(source_by_code)

    for row in source_rows:
        if row.parent_code is not None and row.parent_code not in (
            source_codes | existing_codes
        ):
            raise StabuCodesValidationError(f"missing parent {row.parent_code} for code {row.code}")

    inserts = _ordered_inserts(source_rows, existing_codes)
    updated = tuple(
        row
        for row in source_rows
        if row.code in existing_by_code
        and (
            row.description != existing_by_code[row.code].description
            or row.parent_code != existing_by_code[row.code].parent_code
        )
    )
    updated_codes = {item.code for item in updated}
    unchanged_count = sum(
        1
        for row in source_rows
        if row.code in existing_by_code and row.code not in updated_codes
    )
    missing_from_csv = tuple(row.code for row in existing_rows if row.code not in source_by_code)

    return StabuImportPlan(inserts, updated, unchanged_count, missing_from_csv)


__all__ = [
    "CSV_FIELDS",
    "StabuCode",
    "StabuCodesValidationError",
    "StabuImportPlan",
    "load_stabucodes_csv",
    "plan_stabucode_import",
]
