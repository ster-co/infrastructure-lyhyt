"""Apply customer SQL migrations using Entra-authenticated Azure SQL access."""

from __future__ import annotations

import argparse
import ipaddress
import re
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.sql.migration_common import (
    DatabaseAdapter,
    LedgerRow,
    Migration,
    MigrationError,
    load_manifest,
    sha256_file,
    split_sqlcmd_batches,
    validate_ledger_rows,
)
from scripts.sql.stabucodes import StabuCode


TOKEN_SCOPE = "https://database.windows.net/.default"
ACCESS_TOKEN_ATTRIBUTE = 1256
ODBC_DRIVER = "ODBC Driver 18 for SQL Server"
LOCK_NAME = "lyhyt-sql-migrations"
LOCK_TIMEOUT_MS = 0
LEDGER_TABLE = "dbo.sdb_schema_migrations"
_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_DATABASE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class AzureCliTokenProvider:
    def __init__(self) -> None:
        try:
            from azure.identity import AzureCliCredential
        except ImportError as exc:
            raise MigrationError(
                "missing Python package azure-identity; install it before running SQL migrations"
            ) from exc
        self._credential = AzureCliCredential()

    def get_token(self, scope: str) -> Any:
        return self._credential.get_token(scope)

    def active_application_client_id(self) -> str:
        try:
            result = subprocess.run(
                ["az", "account", "show", "--query", "user.name", "-o", "tsv"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise MigrationError(
                "could not verify Azure CLI application client ID for SQL migrations"
            ) from exc
        client_id = result.stdout.strip()
        if not client_id:
            raise MigrationError("Azure CLI application client ID is empty")
        return client_id


def _load_pyodbc() -> Any:
    try:
        import pyodbc
    except ImportError as exc:
        raise MigrationError(
            "missing Python package pyodbc; install pyodbc before running SQL migrations"
        ) from exc
    return pyodbc


def _validate_connection_target(server: str, database: str) -> None:
    if not isinstance(server, str) or not server or len(server) > 253:
        raise MigrationError("invalid SQL server FQDN")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in server):
        raise MigrationError("invalid SQL server FQDN")
    if any(character in server for character in ";{}"):
        raise MigrationError("invalid SQL server FQDN")
    try:
        ipaddress.ip_address(server)
    except ValueError:
        labels = server.split(".")
        if len(labels) < 2 or any(not _HOST_LABEL.fullmatch(label) for label in labels):
            raise MigrationError("invalid SQL server FQDN")
    else:
        raise MigrationError("invalid SQL server FQDN")

    if (
        not isinstance(database, str)
        or not _DATABASE_NAME.fullmatch(database)
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in database)
        or any(character in database for character in ";{}")
    ):
        raise MigrationError("invalid SQL database name")


def _build_connection_string(server: str, database: str) -> str:
    _validate_connection_target(server, database)
    return (
        f"Driver={{{ODBC_DRIVER}}};"
        f"Server=tcp:{server},1433;"
        f"Database={database};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )


def _token_attrs(token: str) -> dict[int, bytes]:
    token_bytes = token.encode("utf-16-le")
    return {ACCESS_TOKEN_ATTRIBUTE: struct.pack("=i", len(token_bytes)) + token_bytes}


def _connect_with_access_token(
    pyodbc_module: Any,
    token_provider: Any,
    connector: Callable[..., Any],
    server: str,
    database: str,
) -> Any:
    _validate_connection_target(server, database)
    try:
        drivers = pyodbc_module.drivers()
    except Exception as exc:
        raise MigrationError(
            "SQL migration preflight could not enumerate ODBC drivers"
        ) from exc
    if ODBC_DRIVER not in drivers:
        raise MigrationError(f"missing {ODBC_DRIVER}; install the Microsoft SQL ODBC driver")

    try:
        access_token = token_provider.get_token(TOKEN_SCOPE).token
        return connector(
            _build_connection_string(server, database),
            attrs_before=_token_attrs(access_token),
        )
    except MigrationError:
        raise
    except Exception as exc:
        raise MigrationError(
            "SQL migration preflight failed; verify the SQL bootstrap user and token authentication"
        ) from exc


def check_python_driver_and_token(
    pyodbc_module: Any,
    token_provider: Any,
    connector: Callable[..., Any],
    server: str,
    database: str,
) -> None:
    connection = None
    failure: MigrationError | None = None
    try:
        connection = _connect_with_access_token(
            pyodbc_module,
            token_provider,
            connector,
            server,
            database,
        )
        connection.cursor().execute("SELECT 1").fetchone()
    except MigrationError as exc:
        failure = exc
    except Exception as exc:
        failure = MigrationError(
            "SQL migration preflight failed; verify the SQL bootstrap user and token authentication"
        )
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception as exc:
                if failure is None:
                    failure = MigrationError(
                        "SQL migration preflight failed while closing the test connection"
                    )

    if failure is not None:
        raise failure


def _verify_expected_client_id(token_provider: Any, expected_application_client_id: str) -> None:
    if not expected_application_client_id:
        raise MigrationError("expected migration application client ID is required")
    try:
        actual = token_provider.active_application_client_id()
    except MigrationError:
        raise
    except Exception as exc:
        raise MigrationError(
            "could not verify Azure CLI application client ID for SQL migrations"
        ) from exc
    if actual.casefold() != expected_application_client_id.casefold():
        raise MigrationError(
            "active Azure CLI application client ID does not match the catalog migration identity"
        )


class AzureSqlAdapter:
    def __init__(self, connection: Any) -> None:
        self._connection = connection
        self._transaction_failed = False

    @classmethod
    def connect(
        cls,
        server: str,
        database: str,
        token_provider: Any | None = None,
        *,
        expected_application_client_id: str | None = None,
        pyodbc_module: Any | None = None,
    ) -> "AzureSqlAdapter":
        if expected_application_client_id is None:
            raise MigrationError("expected migration application client ID is required")
        token_provider = token_provider or AzureCliTokenProvider()
        _verify_expected_client_id(token_provider, expected_application_client_id)
        pyodbc_module = pyodbc_module or _load_pyodbc()
        connection = _connect_with_access_token(
            pyodbc_module,
            token_provider,
            pyodbc_module.connect,
            server,
            database,
        )
        return cls(connection)

    def ensure_ledger(self) -> None:
        self._connection.cursor().execute(
            f"""
IF OBJECT_ID(N'{LEDGER_TABLE}', N'U') IS NULL
BEGIN
    CREATE TABLE {LEDGER_TABLE} (
        sequence int NOT NULL PRIMARY KEY,
        migration_id nvarchar(200) NOT NULL UNIQUE,
        checksum char(64) NOT NULL,
        applied_utc datetime2(0) NOT NULL,
        applying_identity nvarchar(256) NOT NULL,
        release_version nvarchar(64) NOT NULL
    );
END
"""
        )
        self._connection.commit()

    def acquire_lock(self, name: str, timeout_ms: int) -> bool:
        cursor = self._connection.cursor()
        cursor.execute(
            """
DECLARE @result int;
EXEC @result = sp_getapplock
    @Resource = ?,
    @LockMode = 'Exclusive',
    @LockOwner = 'Session',
    @LockTimeout = ?;
SELECT @result;
""",
            name,
            timeout_ms,
        )
        row = cursor.fetchone()
        return row is not None and int(row[0]) >= 0

    def ledger_rows(self) -> list[LedgerRow]:
        cursor = self._connection.cursor()
        cursor.execute(
            f"""
SELECT sequence, migration_id, checksum, applied_utc, applying_identity, release_version
FROM {LEDGER_TABLE}
ORDER BY sequence;
"""
        )
        return [
            LedgerRow(
                int(row[0]),
                str(row[1]),
                str(row[2]),
                str(row[3]),
                str(row[4]),
                str(row[5]),
            )
            for row in cursor.fetchall()
        ]

    def current_identity(self) -> str:
        row = self._connection.cursor().execute(
            "SELECT CONVERT(nvarchar(256), SUSER_SNAME())"
        ).fetchone()
        return str(row[0]) if row else "unknown"

    def set_autocommit(self, enabled: bool) -> None:
        try:
            self._connection.autocommit = enabled
        except Exception as exc:
            raise MigrationError("SQL migration transaction mode change failed") from exc

    def begin(self) -> None:
        self._transaction_failed = False
        self.set_autocommit(False)

    def execute_batch(self, sql: str) -> None:
        self._connection.cursor().execute(sql)

    def fetch_stabucodes(self) -> list[StabuCode]:
        cursor = self._connection.cursor()
        cursor.execute(
            """
SELECT [code], [description], [parent_code]
FROM [dbo].[cc_stabucodes];
"""
        )
        return [
            StabuCode(
                str(row[0]),
                str(row[1]),
                None if row[2] is None else str(row[2]),
            )
            for row in cursor.fetchall()
        ]

    def executemany(self, sql: str, parameters: list[tuple[object, ...]]) -> None:
        if parameters:
            self._connection.cursor().executemany(sql, parameters)

    def insert_ledger(self, row: LedgerRow) -> None:
        self._connection.cursor().execute(
            f"""
INSERT INTO {LEDGER_TABLE}
    (sequence, migration_id, checksum, applied_utc, applying_identity, release_version)
VALUES (?, ?, ?, ?, ?, ?);
""",
            row.sequence,
            row.migration_id,
            row.checksum,
            row.applied_utc,
            row.applying_identity,
            row.release_version,
        )

    def commit(self) -> None:
        try:
            self._connection.commit()
        except Exception as exc:
            self._transaction_failed = True
            raise MigrationError("SQL migration transaction commit failed") from exc
        self._transaction_failed = False

    def rollback(self) -> None:
        try:
            self._connection.rollback()
        except Exception as exc:
            self._transaction_failed = True
            raise MigrationError("SQL migration transaction rollback failed") from exc
        self._transaction_failed = False

    def release_lock(self, name: str) -> None:
        self._connection.cursor().execute(
            "EXEC sp_releaseapplock @Resource = ?, @LockOwner = 'Session';",
            name,
        )
        if not self._connection.autocommit and not self._transaction_failed:
            self._connection.commit()

    def close(self) -> None:
        self._connection.close()


def apply_migrations(
    migrations: list[Migration],
    adapter: DatabaseAdapter,
    release_version: str,
    allow_destructive: bool = False,
) -> None:
    lock_acquired = False
    failure: MigrationError | None = None
    try:
        try:
            adapter.ensure_ledger()
        except Exception as exc:
            raise MigrationError("SQL migration ledger setup failed") from exc

        try:
            lock_acquired = adapter.acquire_lock(LOCK_NAME, LOCK_TIMEOUT_MS)
        except Exception as exc:
            raise MigrationError("SQL migration lock acquisition failed") from exc
        if not lock_acquired:
            raise MigrationError("could not acquire SQL migration application lock")

        try:
            existing_rows = adapter.ledger_rows()
        except Exception as exc:
            raise MigrationError("SQL migration ledger read failed") from exc
        try:
            validate_ledger_rows(existing_rows, migrations)
        except ValueError as exc:
            raise MigrationError(str(exc)) from exc

        applied_count = len(existing_rows)
        pending_migrations = migrations[applied_count:]
        if any(migration.destructive for migration in pending_migrations) and not allow_destructive:
            raise MigrationError("destructive SQL migrations require explicit approval")

        try:
            applying_identity = adapter.current_identity()
        except Exception as exc:
            raise MigrationError("SQL migration identity lookup failed") from exc

        for migration in pending_migrations:
            transaction_open = False
            try:
                if migration.transactional:
                    adapter.begin()
                    transaction_open = True
                else:
                    adapter.set_autocommit(True)
                for batch in split_sqlcmd_batches(migration.file.read_text(encoding="utf-8")):
                    adapter.execute_batch(batch)
                adapter.insert_ledger(
                    LedgerRow(
                        migration.sequence,
                        migration.migration_id,
                        sha256_file(migration.file),
                        datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                        applying_identity,
                        release_version,
                    )
                )
                if migration.transactional:
                    adapter.commit()
                    transaction_open = False
            except Exception as exc:
                if transaction_open:
                    try:
                        adapter.rollback()
                    except Exception as rollback_exc:
                        raise MigrationError(
                            "SQL migration transaction rollback failed"
                        ) from rollback_exc
                raise MigrationError(
                    f"failed applying migration {migration.migration_id}"
                ) from exc
    except MigrationError as exc:
        failure = exc
    except Exception as exc:
        failure = MigrationError("SQL migration execution failed")
    finally:
        cleanup_failure: MigrationError | None = None
        if lock_acquired:
            try:
                adapter.release_lock(LOCK_NAME)
            except Exception as exc:
                cleanup_failure = MigrationError("SQL migration lock release failed")
        try:
            adapter.close()
        except Exception as exc:
            if cleanup_failure is None:
                cleanup_failure = MigrationError("SQL migration connection close failed")
        if failure is None and cleanup_failure is not None:
            failure = cleanup_failure

    if failure is not None:
        raise failure


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply LYHYT customer SQL migrations")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--sql-server-fqdn", required=True)
    parser.add_argument("--sql-database-name", required=True)
    parser.add_argument("--release-version", required=True)
    parser.add_argument("--expected-application-client-id", required=True)
    parser.add_argument("--allow-destructive", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    repository_root = Path(__file__).resolve().parents[2]

    try:
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
        if args.preflight:
            return 0
        migrations = load_manifest(
            Path(args.manifest),
            repository_root,
            args.release_version,
        )
        adapter = AzureSqlAdapter.connect(
            args.sql_server_fqdn,
            args.sql_database_name,
            token_provider,
            expected_application_client_id=args.expected_application_client_id,
            pyodbc_module=pyodbc_module,
        )
        apply_migrations(
            migrations,
            adapter,
            args.release_version,
            allow_destructive=args.allow_destructive,
        )
    except MigrationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
