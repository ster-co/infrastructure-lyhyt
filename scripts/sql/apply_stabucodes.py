"""Apply the versioned Stabu code CSV to a customer SQL database."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from scripts.sql.apply_migrations import (
    LOCK_NAME,
    LOCK_TIMEOUT_MS,
    AzureCliTokenProvider,
    AzureSqlAdapter,
    MigrationError,
    _load_pyodbc,
    _verify_expected_client_id,
    check_python_driver_and_token,
)
from scripts.sql.stabucodes import (
    StabuCode,
    StabuImportPlan,
    load_stabucodes_csv,
    plan_stabucode_import,
)


INSERT_SQL = """
INSERT INTO [dbo].[cc_stabucodes] ([code], [description], [parent_code])
VALUES (?, ?, ?);
"""

UPDATE_SQL = """
UPDATE [dbo].[cc_stabucodes]
SET [description] = ?, [parent_code] = ?
WHERE [code] = ?;
"""


class StabuCodeDatabase(Protocol):
    def begin(self) -> None:
        ...

    def fetch_stabucodes(self) -> list[StabuCode]:
        ...

    def executemany(self, sql: str, parameters: list[tuple[object, ...]]) -> None:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...


@dataclass(frozen=True)
class StabuImportSummary:
    inserted: int
    updated: int
    unchanged: int
    missing_from_csv: int
    missing_codes: tuple[str, ...]

    def as_json_dict(self) -> dict[str, object]:
        values = asdict(self)
        values["missing_codes"] = list(self.missing_codes)
        return values


def _execute_stabucode_plan(plan: StabuImportPlan, database: StabuCodeDatabase) -> None:
    if plan.inserts:
        database.executemany(
            INSERT_SQL,
            [(row.code, row.description, row.parent_code) for row in plan.inserts],
        )
    if plan.updated:
        database.executemany(
            UPDATE_SQL,
            [(row.description, row.parent_code, row.code) for row in plan.updated],
        )


def _summary_for_plan(plan: StabuImportPlan) -> StabuImportSummary:
    return StabuImportSummary(
        inserted=len(plan.inserts),
        updated=len(plan.updated),
        unchanged=plan.unchanged_count,
        missing_from_csv=len(plan.missing_from_csv),
        missing_codes=plan.missing_from_csv,
    )


def apply_stabucode_plan(
    plan: StabuImportPlan, database: StabuCodeDatabase
) -> StabuImportSummary:
    """Apply an already computed diff as one transaction."""

    database.begin()
    try:
        _execute_stabucode_plan(plan, database)
        database.commit()
    except Exception:
        database.rollback()
        raise
    return _summary_for_plan(plan)


def synchronize_stabucodes(
    source_rows: tuple[StabuCode, ...], database: StabuCodeDatabase
) -> StabuImportSummary:
    """Read, plan, and write Stabu codes inside one database transaction."""

    database.begin()
    try:
        existing_rows = database.fetch_stabucodes()
        plan = plan_stabucode_import(source_rows, existing_rows)
        _execute_stabucode_plan(plan, database)
        database.commit()
    except Exception:
        database.rollback()
        raise
    return _summary_for_plan(plan)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import LYHYT Stabu codes into customer SQL")
    parser.add_argument("--csv-file", required=True)
    parser.add_argument("--sql-server-fqdn", required=True)
    parser.add_argument("--sql-database-name", required=True)
    parser.add_argument("--expected-application-client-id", required=True)
    parser.add_argument("--output", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def _print_summary(summary: StabuImportSummary, output: str) -> None:
    if output == "json":
        print(json.dumps(summary.as_json_dict(), ensure_ascii=False, sort_keys=True))
        return
    print(
        "Stabu codes: "
        f"added={summary.inserted}, "
        f"updated={summary.updated}, "
        f"unchanged={summary.unchanged}, "
        f"missing_from_csv={summary.missing_from_csv}"
    )
    if summary.missing_codes:
        print("Codes missing from CSV: " + ", ".join(summary.missing_codes))


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    try:
        source_rows = load_stabucodes_csv(Path(args.csv_file))
        token_provider = AzureCliTokenProvider()
        _verify_expected_client_id(token_provider, args.expected_application_client_id)
        pyodbc_module = _load_pyodbc()
        check_python_driver_and_token(
            pyodbc_module,
            token_provider,
            pyodbc_module.connect,
            args.sql_server_fqdn,
            args.sql_database_name,
        )
        database = AzureSqlAdapter.connect(
            args.sql_server_fqdn,
            args.sql_database_name,
            token_provider,
            expected_application_client_id=args.expected_application_client_id,
            pyodbc_module=pyodbc_module,
        )
        lock_acquired = False
        try:
            lock_acquired = database.acquire_lock(LOCK_NAME, LOCK_TIMEOUT_MS)
            if not lock_acquired:
                raise MigrationError("could not acquire SQL migration application lock")
            summary = synchronize_stabucodes(source_rows, database)
            _print_summary(summary, args.output)
        finally:
            if lock_acquired:
                database.release_lock(LOCK_NAME)
            database.close()
    except MigrationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Stabu code import failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
