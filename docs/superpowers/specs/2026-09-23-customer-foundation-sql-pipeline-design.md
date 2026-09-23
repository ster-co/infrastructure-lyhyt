# Customer Foundation SQL Deployment and Migration Pipeline Design

**Date:** 2026-09-23  
**Status:** Approved in principle; implementation pending spec review

## Goal

Provide an end-to-end GitHub Actions workflow that selects a customer and environment, deploys the customer foundation in the customer tenant, applies approved SQL migrations using the foundation deployment outputs and Entra token authentication, and then deploys the customer runtime separately in the LYHYT tenant.

## Non-negotiable boundaries

- Customer foundation resources, including SQL Server and SQL Database, are created only in the selected customer tenant and subscription.
- LYHYT customer runtime resources are created only in the fixed LYHYT tenant and runtime subscription.
- The runtime managed identity is not used as the SQL migration identity and receives no migration permissions.
- No SQL passwords, client secrets, access tokens, or secret-bearing connection strings are stored in Bicep parameters, outputs, workflow outputs, files, or logs.
- Existing `*.local.bicepparam` files are not read, changed, or exposed by the implementation.
- The workflow cannot deploy from a branch. It must validate that `github.ref_type == 'tag'` and that `github.ref_name` starts with `v` before any deployment job can run.

## Release and customer selection

The workflow is manually dispatched with exactly two operator inputs: `customer_id` and `environment`. `release_version` is derived from the release tag in `github.ref_name`; the leading `v` is removed before it is passed to the migration runner, so tag `v2026.09.23` produces release version `2026.09.23`.

The first resolver job performs these checks before producing job outputs:

1. `GITHUB_REF_TYPE` is exactly `tag`.
2. `GITHUB_REF_NAME` starts with `v` and has a non-empty version suffix.
3. `customer_id` identifies one catalog record.
4. The catalog record is enabled.
5. `environment` identifies one environment under that customer.
6. The environment has a subscription ID, location, and region code.
7. The selected subscription ID is read from that customer/environment record and is never accepted as an input.
8. The catalog migration identity is present and contains only non-secret object/application IDs.

The resolver writes only safe values to `GITHUB_OUTPUT`. A branch invocation fails in the resolver and all deployment jobs are gated on its successful tag validation.

## Catalog

Create `config/customers.json` as a non-secret catalog. Each customer record contains the tenant and migration identity, and each environment contains its subscription, location, region code, and deployment-safe Bicep configuration. The migration identity shape is:

```json
{
  "migration": {
    "principalObjectId": "replace-with-customer-enterprise-application-object-id",
    "applicationClientId": "replace-with-multitenant-application-client-id"
  }
}
```

The resolver validates UUID-shaped identifiers and ensures the foundation administrator tenant matches the selected customer tenant. It does not accept credentials or secret values. The checked-in example parameter files remain templates; the workflow renders temporary parameter JSON from catalog values and never uses a local parameter file.

## Workflow architecture

Create `.github/workflows/customer-foundation-sql-runtime.yml` with these jobs:

### `resolve`

Loads the catalog and emits the resolved customer tenant, customer subscription, location, region code, release version, migration application client ID, migration principal object ID, and safe parameter payloads. It fails on branch refs and invalid catalog selections.

### `customer_foundation_what_if`

Logs in with `azure/login` using the customer tenant and the catalog migration application client ID through GitHub OIDC/WIF. It runs the required Bicep lint/build/build-params checks and a subscription-scoped foundation what-if. It does not provide SQL connection outputs to later jobs.

### `customer_foundation_apply`

Requires the protected `customer-foundation-apply` GitHub Environment. It logs in again to the customer tenant, deploys `infra/customer-foundation/main.bicep`, and reads `properties.outputs` from that apply deployment. It emits exactly these SQL handoff values as safe job outputs:

- `sqlServerFqdn`
- `sqlDatabaseName`
- `sqlServerResourceId`
- `sqlDatabaseResourceId`

It also emits `customerKeyVaultResourceId`, `customerKeyVaultUri`, `searchEndpoint`, and `aiEndpoint` for the runtime handoff. Outputs are queried directly from the apply deployment; what-if output is never used as a connection target.

### `migration_preflight`

Logs in to the customer tenant with the catalog migration application client ID, confirms that the active Azure CLI identity matches that client ID, validates both SQL resource IDs are subscription-scoped under the resolved customer subscription, and runs the SQL tooling preflight.

The preflight fails before migration execution if any of these are missing or unusable:

- Python `pyodbc` import
- Microsoft ODBC Driver 18 for SQL Server in `pyodbc.drivers()`
- an Entra token for `https://database.windows.net/.default`
- token-based pyodbc connection to the exact apply-job `sqlServerFqdn` and `sqlDatabaseName`

The token is held in memory only for the connection attribute and is never printed or written to a file.

### `migration_plan`

Runs manifest and checksum validation without changing the database and reports whether destructive migrations are present. It validates contiguous sequence numbers, unique IDs, unique sequence numbers, file existence, minimum release version, and the absence of out-of-manifest historical migrations.

### `migration_standard` and `migration_destructive`

Exactly one migration execution path runs after planning. The standard path executes without a destructive approval flag. If destructive migrations are present, the standard path is skipped and the `migration_destructive` job requires the protected `sql-migrations-destructive` Environment before passing `--allow-destructive`.

Both paths use only the four SQL values emitted by `customer_foundation_apply` and the catalog release version. They fail on a missing bootstrap database user or insufficient database permissions and do not attempt to grant permissions or roll back incompatible production migrations.

### `lyhyt_runtime`

Runs only after the successful migration path. It logs in separately with the fixed LYHYT tenant/client/subscription configuration, renders the runtime parameter payload from catalog values plus safe customer foundation outputs, and deploys `infra/lyhyt-customer-runtime/main.bicep`. The runtime payload may contain customer tenant IDs, endpoints, and resource IDs, but no credentials or SQL passwords. The runtime template is verified to contain no SQL, Search, AI, or customer Key Vault resource creation.

## SQL migration system

Create:

- `docs/database/migrations/manifest.json`
- `docs/database/migrations/README.md`
- `scripts/sql/apply_migrations.py`
- `scripts/sql/verify_migrations.py`
- `tests/test_sql_migrations.py`

The manifest references `docs/database/0001_baseline.sql` as sequence 1, ID `0001_baseline`, transactional and non-destructive, with minimum release `2026.09.23`.

The runner exposes a testable database adapter boundary. The production adapter obtains an Entra token through the Azure CLI credential established by `azure/login`, creates a token-authenticated pyodbc connection, and uses one connection for the session application lock and migration work.

Before applying migrations it:

1. Validates the manifest and original migration file checksums.
2. Ensures `dbo.sdb_schema_migrations` exists with sequence, ID, checksum, applied UTC, applying identity, and release version columns.
3. Acquires an exclusive session-owned `sp_getapplock` with a zero or bounded timeout and fails clearly on conflict.
4. Loads and validates the existing ledger, rejecting changed historical checksums, missing historical migrations, duplicate IDs/sequences, or gaps.
5. Splits SQLCMD `GO` batches without splitting occurrences inside strings or comments.
6. Executes transactional migrations inside a transaction.
7. Inserts the ledger row only after all batches in that migration succeed.
8. Skips a ledger row only when its sequence, ID, and checksum exactly match the manifest.
9. Releases the application lock and closes the connection.

Destructive migrations require an explicit `--allow-destructive` flag, supplied only by the protected destructive-migration job. No automatic rollback is attempted.

The initial bootstrap is documented as:

```text
Customer SQL administrator
    creates/approves migration database user
        |
GitHub Actions WIF identity
    connects using an Entra token
        |
Migration runner
    applies the schema
```

For the pilot, the WIF deployment application may be configured as the SQL Entra administrator and is explicitly marked privileged and pilot-only. Production onboarding requires the customer administrator to create a contained database user for the customer-tenant enterprise application and grant only the permissions required by the migration runner. The runtime managed identity is excluded from this process.

## Testing

Unit tests use fake database adapters and do not require Azure or a live SQL database. They cover:

- valid manifests, duplicate IDs, duplicate sequences, missing files, and out-of-order migrations
- first execution and repeated execution with matching checksums
- checksum mismatch and missing historical migration detection
- destructive approval enforcement
- transaction rollback behavior
- application-lock conflicts
- SQLCMD `GO` batch splitting
- absence of credentials/tokens/connection strings in logs
- use of `sqlServerFqdn` and `sqlDatabaseName` from apply outputs
- pyodbc/driver/token preflight failures

The workflow and catalog resolver are covered by tests that prove branch refs cannot deploy, only `v*` tags produce release versions, customer/environment validation is authoritative, migration identity values are explicit, and SQL resource IDs must belong to the selected customer subscription.

## Documentation

Update `README.md` with customer catalog onboarding, tag-only manual deployment, required GitHub variables/secrets and protected Environments, customer-tenant WIF behavior, apply-output handoff, private-network runner requirements, destructive approval, and the LYHYT tenant runtime boundary. Put SQL-specific bootstrap, authorization, migration authoring, and operational guidance in `docs/database/migrations/README.md`.

## Verification

Before completion, run the required Bicep lint/build/build-params commands for both entry points, `python3 -m unittest discover -s tests -v`, and `git diff --check`. No Azure deployment is performed; a subscription what-if may be proposed only if Azure access is available.
