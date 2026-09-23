# Customer SQL migrations

This runbook describes how a customer administrator bootstraps the migration
identity and how the repository applies the versioned SQL schema. It is
separate from the application runtime identity: the runtime managed identity
is never granted migration permissions.

## Customer and environment catalog onboarding

`config/customers.json` is the non-secret source of truth for workflow
selection. Add a customer only when its customer-tenant foundation, runtime,
network, and identity values are known and approved. A customer record has one
unique `id`, its customer `tenantId`, one `migration` identity, and an
`environments` object keyed by the supported environment names. The workflow
accepts the environment string only when that key exists for the selected
customer; a missing `tst`, `acc`, or `prod` record fails during resolution and
cannot deploy.

For each new customer/environment record:

1. Confirm the customer tenant, subscription, private-network address space,
   region, SQL administrator, and customer/runtime parameters with the
   customer owner. Allocate a non-overlapping VNet range; never derive one
   from the customer name or environment.
2. Add only non-secret tenant IDs, subscription IDs, resource IDs, endpoints,
   names, and deployment settings to the matching catalog record. Do not add
   passwords, client secrets, tokens, or connection strings.
3. Configure the customer tenant enterprise application and its GitHub OIDC
   federated credential before enabling the record. Verify the SQL bootstrap
   user and permissions described below.
4. Run the catalog resolver and focused tests from the repository root. Add a
   production environment key only with its real approved values; do not add
   fake records merely to populate a workflow dropdown.

The checked-in `pilot/tst` catalog record contains placeholders and is for
non-production testing only. It is not evidence that the pilot is production
ready and must not be used for a production deployment. Replace every
placeholder with approved customer values, or add a separate approved
environment record, before enabling production support.

### Migration identity field mapping

The `migration` object maps the same multitenant application across tenants:

| Catalog field | Required value |
| --- | --- |
| `migration.applicationClientId` | The Application (client) ID of the LYHYT multitenant app registration. This client ID is stable across the app registration and its customer-tenant enterprise application. |
| `migration.principalObjectId` | The Object ID of that app's service principal (enterprise application) in the customer tenant. This is a tenant-local object ID, not the app registration object ID, client ID, runtime UAMI principal ID, or SQL administrator object ID. |

To obtain the customer enterprise application's object ID, an authorized
operator can sign in to the customer tenant and query the service principal
for the multitenant client ID:

```bash
az login --tenant <customer-tenant-id>
az ad sp show --id <multitenant-application-client-id> --query id -o tsv
```

Put the second command's customer-tenant service-principal object ID in
`migration.principalObjectId`, and put the multitenant app's client ID in
`migration.applicationClientId`. These are identifiers, not secrets. The
customer enterprise application and federated credential must permit the
workflow's GitHub OIDC subject to log in before the catalog entry is enabled.

## Identity and bootstrap boundary

The customer owns approval of the database principal. The migration job uses
GitHub OIDC and workload identity federation (WIF) to obtain an Entra token;
it does not use a SQL password, client secret, or connection-string secret.

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

For the pilot, the WIF application may be configured as the privileged SQL
Entra administrator. This is a temporary, pilot-only arrangement. Production
requires a customer-tenant enterprise application represented by the catalog
migration identity and a contained database user with only migration
permissions. The customer administrator must approve that user and its
permissions in the target database before the workflow is enabled.

The runtime managed identity is never the migration identity and never
receives migration permissions. It is used by the application for its runtime
access contract only. The migration token is held in memory for the SQL
connection and is not written to parameters, outputs, files, or logs.

### Required database permissions

The contained migration user needs only the permissions required to perform
the operations in approved migration files and maintain the migration ledger:

- connect to the target customer database;
- create and alter the migration-owned schema objects used by approved
  migrations, including the baseline tables, indexes, constraints, views, and
  triggers;
- create `dbo.sdb_schema_migrations` on first use, then read it and insert its
  ledger rows; and
- read, insert, and update `dbo.cc_stabucodes` for the versioned reference-data
  import; and
- execute the session-owned `sp_getapplock` and `sp_releaseapplock` calls used
  to serialize migration runs.

Grant the narrowest database and schema/object permissions that satisfy the
approved migration set. Do not grant the runtime UAMI access to the ledger or
schema, and do not use the migration user for application data access. The
runner does not grant permissions, change firewall rules, create users, or
attempt an automatic rollback when a migration is incompatible.

## Runner preflight and network requirements

The migration jobs use the exact `sqlServerFqdn` and `sqlDatabaseName` emitted
by the successful `customer_foundation_apply` deployment. The SQL resource IDs
are validated against the selected customer subscription before connecting;
what-if output is never used as a connection target.

The runner must have all of the following:

- Python `pyodbc`;
- Python package `azure-identity==1.25.3`;
- `ODBC Driver 18 for SQL Server`;
- an Azure CLI login established by `azure/login` for the catalog migration
  application; and
- an Entra token for `https://database.windows.net/.default`.

Install and validate the Python migration prerequisite from the repository
root before running the preflight locally or provisioning a self-hosted
runner:

```bash
python3 -m pip install --requirement requirements.txt
python3 -c 'import azure.identity'
```

The workflow repeats these commands in every SQL job. The migration runner's
preflight also imports `azure.identity` and fails with an actionable message
if the package is missing; that check does not replace installation.

Production SQL uses private endpoints and private DNS. Set
`CUSTOMER_SQL_RUNNER_LABEL` to a self-hosted runner label whose runner has
customer-network access, can resolve the private SQL hostname through the
customer private DNS zone, and is allowed to reach Entra ID for token
acquisition. A GitHub-hosted runner is not a substitute when public SQL access
is disabled. Keep the runner's operating system and ODBC driver patched and
limit its network access to the required customer services.

## Migration authoring rules

1. Add a new SQL file under `docs/database/` with the next zero-padded
   sequence and a stable identifier, for example
   `docs/database/0002_add_index.sql`.
2. Append one matching entry to
   [`manifest.json`](manifest.json). Sequences start at 1 and must remain
   contiguous; IDs and sequence numbers must be unique. Never edit an already
   applied migration or change its bytes, because its checksum is part of the
   deployment ledger.
3. Mark migrations `transactional: true` when all batches can run in one
   transaction. Set `destructive: true` for drops, data-loss changes, or other
   changes requiring explicit operational approval. Set `minimumRelease` to
   the first release that may apply the migration.
4. Use SQLCMD `GO` batch separators on their own line when a batch boundary is
   required. The runner splits `GO` without splitting occurrences inside SQL
   strings or comments. Keep user creation, permissions, firewall rules, and
   customer data out of schema migrations; those are owned by onboarding and
   customer operations.
5. Keep migrations deterministic and reviewable. Do not put secrets,
   credentials, tokens, or secret-bearing connection strings in SQL, the
   manifest, or comments that could be printed in a job log.
6. Verify the manifest and checksums before opening a pull request. A pending
   destructive migration must be reviewed by the customer and run only after
   the protected destructive-migration approval.

The runner creates `dbo.sdb_schema_migrations`, takes an exclusive session
application lock with `sp_getapplock`, validates the applied contiguous prefix,
and records each migration only after its batches succeed. A matching sequence,
ID, and checksum is skipped on repeat execution. Changed historical files,
missing historical rows, duplicate IDs/sequences, gaps, lock conflicts, and
destructive migrations without approval fail the job.

## Stabu code reference-data import

[`docs/database/reference/stabucodes.csv`](../reference/stabucodes.csv) is the
versioned source for `dbo.cc_stabucodes`. It is deliberately not appended to
`0001_baseline.sql`: the baseline is a checksum-protected schema migration.
The importer runs immediately after the schema migration runner in both the
standard and approved destructive SQL jobs, so every selected customer
database receives the same reference data.

The versioned CSV contains `code`, `description`, and `parent_code` and keeps
the UTF-8-BOM. The importer also accepts a four-column export containing
`last_altered`; that value is ignored regardless of its contents and is never
written to SQL. It requires non-empty `code` and `description`, validates the
10-character code/parent limits, rejects duplicate codes and invalid parents,
and does not impose a limit on `description` because the column is
`varchar(max)`. Inserts are parent-first. Existing rows are updated only when `description` or
`parent_code` differs; unchanged rows are not written, so a second identical
run does not change `last_altered`. The whole diff is applied in one
transaction. Codes present in the database but absent from the CSV are
reported and not automatically deleted.

Run it locally after an Entra-authenticated SQL connection is available:

```bash
python3 -m scripts.sql.apply_stabucodes \
  --csv-file docs/database/reference/stabucodes.csv \
  --sql-server-fqdn <customer-sql-fqdn> \
  --sql-database-name <customer-database-name> \
  --expected-application-client-id <migration-application-client-id> \
  --output json
```

The command reports `inserted`, `updated`, `unchanged`, and
`missing_from_csv`, plus the missing code list. It uses the same Azure CLI
token, customer SQL runner, private DNS, and ODBC Driver 18 requirements as
the migration runner; it does not accept or print a password or connection
string. To release a new CSV version, replace the versioned source file, run
the focused tests and importer checks, and deploy a new release tag. The
existing workflow then applies only the source diff while leaving
`0001_baseline.sql` unchanged. Unit tests use an in-memory recording adapter;
no live SQL Server is part of the local test suite.

## Workflow operation

The workflow is manually dispatched from a release tag whose name starts with
`v`, such as `v2026.09.23`. It rejects branch dispatches before any deployment
job runs and derives `release_version` by removing the leading `v`. The only
operator inputs are:

- `customer_id`; and
- `environment`.

The customer subscription, tenant, location, migration application client ID,
and other deployment-safe values are resolved from `config/customers.json`.
They are not operator inputs. The execution order is foundation what-if,
protected foundation apply, SQL preflight, migration plan, exactly one of the
standard or destructive migration jobs, and finally the LYHYT runtime deploy.

The foundation apply passes only safe outputs to the SQL jobs:
`sqlServerFqdn`, `sqlDatabaseName`, `sqlServerResourceId`, and
`sqlDatabaseResourceId`. Each job renders a temporary `.bicepparam` file when
needed and deletes it after the job, including on failure. Do not create,
read, or commit customer-specific `*.local.bicepparam` files.

### GitHub variables and environments

Configure these non-secret GitHub repository or organization variables before
enabling the workflow:

| Variable | Purpose |
| --- | --- |
| `CUSTOMER_SQL_RUNNER_LABEL` | Self-hosted customer-network runner label for SQL preflight, plan, and apply jobs. |
| `LYHYT_AZURE_CLIENT_ID` | LYHYT multitenant application client ID used for runtime deployment. |
| `LYHYT_AZURE_TENANT_ID` | LYHYT tenant ID. |
| `LYHYT_RUNTIME_SUBSCRIPTION_ID` | LYHYT subscription containing customer runtime resources. |
| `LYHYT_PLATFORM_SUBSCRIPTION_ID` | LYHYT subscription containing shared platform resources, used for resource validation. |

Protect the following GitHub Environments with required reviewers and any
customer change-control rules:

- `customer-foundation-apply` gates creation or changes to customer
  foundation resources;
- `sql-migrations-destructive` gates the job that passes
  `--allow-destructive`.

The workflow needs `id-token: write` for WIF and `contents: read` for
checkout. No SQL password, client secret, access token, or other secret is a
required workflow variable. The catalog contains only non-secret tenant,
subscription, and application identifiers. The customer tenant must have the
enterprise application and federated credential configured so the WIF identity
can log in with the catalog migration application client ID.

## Key Vault bootstrap sequence

Key Vault integration is enabled only after the runtime identity and customer
foundation exist. Follow this order:

1. Deploy the shared platform and record its safe ACR and, when used, platform
   Key Vault outputs.
2. Deploy the customer runtime once in the LYHYT tenant with customer Key
   Vault integration disabled. Capture only `identityPrincipalId` and
   `identityClientId`; this creates the per-customer runtime UAMI.
3. Deploy the customer foundation in the customer tenant. For the same-tenant
   pilot only, pass the bootstrap UAMI principal ID and explicitly enable the
   read-only customer Key Vault role assignment when required. A future
   cross-tenant deployment must use the customer-side enterprise application
   principal, not assume that the LYHYT UAMI can receive customer-tenant RBAC.
4. Read the customer and platform Key Vault IDs and URIs from their own
   deployment outputs and pass those safe values together to the final runtime
   deployment. Never pass secret values through Bicep.
5. Redeploy the runtime with Key Vault integration enabled and
   `requireKeyVault=false`. Populate the documented allowlisted secrets later
   through a secured secret-management workflow, restart the Container App,
   and validate startup and application behavior.
6. Set `requireKeyVault=true` only after validation. Keep it false in examples
   and during bootstrap.

See [`docs/key-vault-contract.md`](../../key-vault-contract.md) for the full
vault contract, allowlists, and RBAC boundaries.

## Local verification

Run the manifest verifier without connecting to Azure or SQL:

```bash
python3 -m scripts.sql.verify_migrations \
  --manifest docs/database/migrations/manifest.json \
  --release-version 2026.09.23 \
  --output json
```

The focused unit tests use fake database adapters and do not require a live
database. Before changing deployment code, also run the repository's required
Bicep validation and test commands from the root `README.md`.
