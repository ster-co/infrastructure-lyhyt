# Additional Customer Foundation Workflow Design

**Date:** 2026-10-07
**Status:** Approved for implementation; review considerations incorporated

## Goal

Add a manually dispatched GitHub Actions workflow that deploys and configures
the customer foundation, including its Bicep resources, customer foundation
Key Vault values, and SQL migrations. Keep the existing combined
customer-foundation/runtime workflow and the standalone LYHYT runtime workflow
unchanged.

## Scope and boundaries

- Add `.github/workflows/customer-foundation.yml` as an additional workflow.
- Do not edit or remove `.github/workflows/customer-foundation-sql-runtime.yml`
  or `.github/workflows/lyhyt-runtime.yml`.
- Use the same concurrency group as the existing combined workflow:
  `customer-foundation-${customer_id}-${environment}`. This serializes
  foundation deployments and SQL migrations for the same customer/environment
  across the two customer workflows.
- The new workflow authenticates and deploys only in the selected customer
  tenant and subscription. It does not read shared-platform deployment output,
  log in to the LYHYT tenant, query or deploy the LYHYT runtime, publish to the
  LYHYT runtime Key Vault, or require a runtime bootstrap input.
- Keep the customer foundation's optional same-tenant runtime Key Vault role
  assignment disabled. The workflow does not receive or use a runtime identity.
- Do not deploy Azure resources as part of local verification.

## Workflow inputs and resolution

The workflow is manually dispatched from a selected branch and accepts:

- `customer_id`;
- `environment`; and
- `release_version`.

It rejects non-branch refs, resolves the customer tenant/subscription,
foundation parameters, migration WIF application and principal, SQL runner
label, location, region, and numeric migration release. Resolution is
foundation-scoped: it does not require or validate LYHYT client IDs,
subscriptions, runtime parameters, or runtime Key Vault configuration. A
focused `resolve_foundation_customer.py` resolver will validate the customer
catalog fields required by this workflow.

## Workflow sequence

1. Resolve the selected customer/environment and release version.
2. Log in with customer-tenant workload identity federation and run Bicep
   lint, build, parameter build, and subscription-scoped what-if for
   `infra/customer-foundation/main.bicep`.
3. Wait at the protected `customer-foundation-apply` GitHub Environment, apply
   the customer foundation, and capture validated safe outputs from the apply
   deployment.
4. After apply, publish safe customer-foundation outputs to the deployed
   customer foundation Key Vault. This runs on the configured customer SQL
   runner so the runner can reach private customer resources when required.
5. In parallel with Key Vault publication, run SQL dependency/network/token
   preflight, migration manifest planning, then exactly one migration path:
   the standard path or the `sql-migrations-destructive` protected path.
   Preserve the existing Stabu reference-data import after successful
   migration execution.
6. Mark the workflow complete only after both customer Key Vault publication
   and the SQL migration path complete successfully.

The foundation apply deploys the existing customer resource group and its
Storage account/containers, customer Key Vault, SQL server/database, Azure AI
Search service, Azure AI Services and model deployments, and Document
Intelligence resource. The workflow does not introduce LYHYT runtime
resources.

## Customer foundation Key Vault publication

The publisher writes only the 12 non-secret values exposed by the customer
foundation deployment. The mapping is:

| Foundation output | Customer Key Vault name |
|---|---|
| `storageAccountName` | `storage-account-name` |
| `blobEndpoint` | `storage-blob-endpoint` |
| `sqlServerFqdn` | `db-server-name` |
| `sqlDatabaseName` | `db-name` |
| `searchServiceName` | `azure-search-service-name` |
| `searchEndpoint` | `azure-search-service-endpoint` |
| `aiEndpoint` | `azure-openai-endpoint` |
| `documentIntelligenceEndpoint` | `document-intelligence-endpoint` |
| `gpt5DeploymentName` | `azure-openai-deployment-gpt5` |
| `gpt54DeploymentName` | `azure-openai-deployment-gpt54` |
| `gpt5MiniDeploymentName` | `azure-openai-deployment-gpt5-mini` |
| `textEmbedding3LargeDeploymentName` | `azure-openai-deployment-text-embedding-3-large` |

All 12 mappings are mandatory. The customer-specific output extractor validates
that every mapped output exists as a string and is non-empty before it starts
publishing. The shared foundation output extractor may continue treating some
fields as optional for other consumers; this publisher must not use those
optional defaults for its 12 required entries.

The customer publisher keeps idempotent, name-only drift reporting: it creates
missing values, leaves matching values intact, and stops when an existing
value differs unless an explicit update path is used. The workflow does not
accept secret values or print Key Vault values. It does not initialize
runtime-only or operator-managed secrets, including `BRAVE_SEARCH_API_KEY`.
Tests must cover the full output-to-secret mapping, failure on every missing
or empty mapped output, default drift rejection, explicit update behavior, and
that publisher output/logs do not contain any published value.

The foundation Bicep will accept an optional
`keyVaultPublisherPrincipalObjectId` parameter, defaulting to an empty string.
When supplied, a focused module grants that principal `Key Vault Secrets
Officer` scoped only to the customer foundation vault. The workflow supplies
`migration.principalObjectId`, which is the **customer tenant's enterprise
application/service principal object ID**. It is the RBAC principal ID; it is
not the application/client ID. The separate `migration.applicationClientId`
is passed to `azure/login` as `client-id`. The existing combined workflow omits
the optional object-ID parameter and keeps its current RBAC behavior. No LYHYT
managed identity receives customer RBAC. The customer deployment identity
must be authorized to create the scoped role assignment. The customer WIF
identity then writes the mapped values using Azure CLI without logging command
output or Key Vault values.

This adds customer-foundation metadata publication to the customer vault. The
runtime-owned secrets and runtime vault flow in the existing workflows remain
unchanged.

## SQL migration behavior

Reuse the existing customer SQL migration tooling and protection model:

- customer-tenant WIF login using the catalog migration application;
- customer runner selected by `automation.customerSqlRunnerLabel`;
- validation of SQL resource IDs against the selected customer subscription;
- Python, ODBC Driver 18, Entra token, network, and database preflight;
- manifest/checksum planning without database writes;
- one of the standard or destructive migration paths, with the destructive
  path gated by `sql-migrations-destructive` and `--allow-destructive`; and
- the existing Stabu code reference-data import following migration execution.

The workflow creates no SQL password, connection string, or other credential.
The SQL migration identity remains separate from any runtime managed identity.

## Concurrency, approvals, and reruns

The shared customer/environment concurrency group prevents this additional
workflow from racing the existing combined workflow. The foundation apply
continues to use the protected `customer-foundation-apply` GitHub Environment;
destructive migrations continue to use the protected
`sql-migrations-destructive` Environment. Deployment names and Bicep-generated
resource names remain deterministic for safe reruns.

## Files expected to change during implementation

- Create `.github/workflows/customer-foundation.yml`.
- Create `scripts/pipeline/resolve_foundation_customer.py`.
- Restore strict safe-output extraction and publication in
  `scripts/pipeline/customer_configuration.py`; retain the existing CLI entry
  point, which delegates to those functions.
- Add an optional publisher-principal-object-ID parameter, a focused Bicep role
  assignment module, and conditional wiring in
  `infra/customer-foundation/main.bicep`. Its empty default preserves the
  existing combined workflow's current RBAC behavior.
- Extend `tests/test_customer_foundation_resources.py` to verify the optional
  vault-scoped assignment uses the service-principal object ID.
- Add `tests/test_resolve_foundation_customer.py` for foundation-scoped
  catalog resolution, including operation without LYHYT-only catalog fields.
- Extend `tests/test_deployment_outputs.py` for the exact 12-value mapping,
  missing/empty output failures, drift behavior, and absence of value logging.
- Extend `tests/test_workflow_architecture.py` for the new workflow's lack of
  LYHYT dependencies and for the completion gate requiring both Key Vault
  publication and SQL success.
- Include `tests/__init__.py` and narrow `.gitignore` exceptions so the
  required regression tests and the updated Key Vault contract are included
  in the repository change.
- Update `README.md`, `docs/database/migrations/README.md`, and
  `docs/key-vault-contract.md` to describe the additive workflow, exact
  principal-ID distinction, and customer-vault output mapping.
- Leave both existing workflow YAML files unchanged.

## Verification

Run the repository-required Bicep lint, build, and build-params commands for
the affected customer foundation entry point and relevant parameter files.
Inspect the new workflow to confirm it contains no LYHYT authentication,
platform lookup, runtime template, runtime Key Vault publication, or runtime
deployment step. Do not run an Azure deployment.
