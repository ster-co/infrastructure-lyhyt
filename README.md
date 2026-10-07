# LYHYT Infrastructure

Azure Bicep templates for the LYHYT shared platform, customer foundation, and customer runtime resources.

## Repository layout

- `infra/lyhyt-platform/` provisions the shared platform resource group, Azure Container Registry, and optional shared platform Key Vault.
- `infra/customer-foundation/` provisions customer-scoped Storage, Key Vault, Azure SQL, AI Services, Document Intelligence, and AI model deployments.
- `infra/lyhyt-customer-runtime/` provisions a customer resource group, Log Analytics, Application Insights, Container Apps Environment, exactly one LYHYT-owned runtime Key Vault, the customer Container App, three Flex Consumption Function Apps, one user-assigned identity and plan per Function App, shared identity-based host storage, dedicated Flex deployment containers, and workload queues/containers.
- `reference/exports/` contains exported Azure reference templates for comparison only and is excluded from Git.

Each entry point is subscription-scoped and has an example parameter file under its `environments/` directory.

The customer runtime requires an explicit `vnetAddressPrefix`. Allocate a unique, non-overlapping range for every customer and environment; do not derive it from a customer code, environment name, or hash. The example uses `10.20.0.0/21` and deterministically derives this topology:

```text
VNet:                              10.20.0.0/21
Container Apps infrastructure:    cidrSubnet(prefix, 23, 0) -> 10.20.0.0/23
Private Endpoints:                 cidrSubnet(prefix, 24, 4) -> 10.20.4.0/24
```

The second `cidrSubnet` argument is the absolute new prefix length, so `23` and `24` derive `/23` and `/24` from the `/21` VNet prefix.

The infrastructure subnet is delegated to `Microsoft.App/environments` and is used exclusively by the external Workload Profiles Container Apps Environment with its `Consumption` workload profile. The temporary TST pilot explicitly uses `internal: false`, `publicNetworkAccess: 'Enabled'`, `zoneRedundant: false`, and external Container App ingress. Production parameter files must choose `publicNetworkAccess` and `zoneRedundant` explicitly.

The final Front Door Premium route is intended to use Private Link. That transition will set `publicNetworkAccess` to `Disabled` while retaining the external Environment VIP type (`internal: false`). Front Door, Private Link, Private Endpoints, and Private DNS are not created by this pilot configuration.

The address space between the two subnets is intentionally reserved for future runtime networking requirements. The pilot leaves `dockerBridgeCidr`, `platformReservedCidr`, and `platformReservedDnsIP` unset so Azure manages those platform CIDR defaults. Before production peering or VPN integration, perform explicit non-overlapping IP planning and parameterize those ranges.

The pilot uses direct same-tenant Managed Identity RBAC for LYHYT-owned resources such as ACR. Workload identity federation for cross-tenant access is deliberately not implemented yet.

The runtime uses separate user-assigned managed identities for the three Function Apps and the Container App. Function Apps use dedicated Flex deployment containers authenticated by their own identities, while host storage remains a shared account with account-level RBAC; separate identities therefore do not isolate application queues or containers. Runtime configuration is application-level: Bicep passes only identity client IDs, the runtime vault URI through the existing vault settings, host-storage settings, monitoring settings, and feature flags. Applications read secrets themselves through their approved Key Vault bootstrap. See [`docs/key-vault-contract.md`](docs/key-vault-contract.md) for the exact 49-entry contract, hydration rules, storage boundary, RBAC rules, and deployment handoff.

## Prerequisites

- Azure CLI with Bicep support (`az bicep version`)
- An Azure subscription and permission to create the resources
- An authenticated Azure CLI session (`az login`)
- Contributor access and `Role Based Access Control Administrator` permission; the latter is required for the ACR pull role assignment

## Validate templates

Validation compiles templates locally and does not create Azure resources:

```bash
az bicep lint --file infra/lyhyt-platform/main.bicep
az bicep build --file infra/lyhyt-platform/main.bicep --stdout > /dev/null
az bicep build-params --file infra/lyhyt-platform/environments/tst.bicepparam --stdout > /dev/null

az bicep lint --file infra/customer-foundation/main.bicep
az bicep build --file infra/customer-foundation/main.bicep --stdout > /dev/null
az bicep build-params --file infra/customer-foundation/environments/customer.example.bicepparam --stdout > /dev/null

az bicep lint --file infra/lyhyt-customer-runtime/main.bicep
az bicep build --file infra/lyhyt-customer-runtime/main.bicep --stdout > /dev/null
az bicep build-params --file infra/lyhyt-customer-runtime/environments/customer.example.bicepparam --stdout > /dev/null

python3 -m unittest discover -s tests -v
git diff --check
```

## Deployment order

The repository has separate customer-foundation-only, combined customer-foundation/runtime, and LYHYT-runtime-only workflows. The two customer-foundation workflows share a concurrency group so they cannot deploy the same customer/environment at once. Review and customize each parameter file before deployment, and pass only safe deployment outputs between independent entry points. See [`docs/key-vault-contract.md`](docs/key-vault-contract.md) for the vault boundaries and publication sequence.

### Standalone runtime deployment workflow

The shared platform deployment must already exist before using the standalone
runtime workflow. It reads the named `lyhyt-platform-<environment>` deployment
outputs for the ACR reference and optional platform Key Vault; it does not
redeploy the shared platform. In GitHub Actions, select the
`.github/workflows/lyhyt-runtime.yml` workflow and manually provide:

- `customer_id`: the enabled customer catalog identifier from
  `config/customers.json`;
- `environment`: the customer environment catalog key; and
- a branch ref from which to run the workflow.

The workflow logs in only to the LYHYT tenant and LYHYT platform/runtime
subscriptions. It deploys only the LYHYT runtime resources and its single
runtime Key Vault. It never deploys, queries, or authenticates to the customer
foundation or customer tenant, and it does not run customer SQL migrations.
The customer tenant ID is used only as a non-secret catalog value for the
existing `sp-tenant-id` runtime entry; it is not used for Azure access.

The standalone sequence is bootstrap, runtime-only Key Vault publication, and
final runtime wiring. Because no customer-foundation outputs are available in
this path, foundation-derived entries—including SQL, AI, Search, and model
deployment values—remain `not-configured`. Runtime-derived endpoints and other
safe values are published when available. The combined customer-foundation
workflow remains the path for later safe SQL/AI/Search hydration.

### 1. Shared platform

```bash
az deployment sub create \
  --name lyhyt-platform-tst \
  --location swedencentral \
  --template-file infra/lyhyt-platform/main.bicep \
  --parameters infra/lyhyt-platform/environments/tst.bicepparam
```

### 2. Customer foundation

Copy `infra/customer-foundation/environments/customer.example.bicepparam` to a customer-specific `.bicepparam` file, replace the placeholder tenant and SQL administrator values, review AI deployment capacities, then run:

```bash
az deployment sub create \
  --location swedencentral \
  --template-file infra/customer-foundation/main.bicep \
  --parameters infra/customer-foundation/environments/customer.example.bicepparam
```

### 3. Customer runtime

Update `infra/lyhyt-customer-runtime/environments/customer.example.bicepparam` with the actual registry name, registry resource group, login server, and image, then run:

```bash
az deployment sub create \
  --location swedencentral \
  --template-file infra/lyhyt-customer-runtime/main.bicep \
  --parameters infra/lyhyt-customer-runtime/environments/customer.example.bicepparam
```

Review deployment outputs for resource IDs, names, and the Container App FQDN. Do not commit credentials, secrets, customer tenant details, or local parameter files; files matching `*.local.bicepparam` are ignored.

## Customer deployment workflows

### Customer foundation only

The additional manual workflow in
`.github/workflows/customer-foundation.yml` deploys the customer foundation
from `infra/customer-foundation/main.bicep`, publishes its 12 required
foundation outputs into the customer foundation Key Vault, and runs SQL
preflight, migration planning, and exactly one approved migration path. It
does not authenticate to the LYHYT tenant, read shared-platform outputs,
deploy LYHYT runtime resources, or publish to the LYHYT runtime vault. Its
inputs are `customer_id`, `environment`, and numeric `release_version`; it
rejects tag refs. The final workflow gate succeeds only if the foundation
apply, customer-vault publication, and SQL path all succeed.

The workflow uses `migration.applicationClientId` as the `azure/login`
`client-id`. `migration.principalObjectId` is the customer tenant's enterprise
application/service principal **object ID**; the foundation Bicep uses this
tenant-local object ID as the `Key Vault Secrets Officer` RBAC principal for
the customer foundation vault. It is not the application/client ID. The
deployment identity must have permission to create that role assignment.
Protect the `customer-foundation-apply` GitHub Environment with required
reviewers. Key Vault publication and SQL jobs use
`automation.customerSqlRunnerLabel`, which must reach customer private DNS and
private endpoints when those are enabled.

The publisher requires all 12 outputs and fails before writing if any are
missing or empty. It creates or leaves matching metadata unchanged, rejects
drift by default, and reports secret names without logging values. It does
not publish API keys, passwords, credentials, or other operator-managed
secrets. The SQL path imports the versioned Stabu code reference data from
`docs/database/reference/stabucodes.csv`; destructive migrations remain behind
the separately protected `sql-migrations-destructive` Environment.

### Existing combined customer foundation and runtime workflow

The manual GitHub Actions workflow in
`.github/workflows/customer-foundation-sql-runtime.yml` deploys one catalog
customer and environment from the branch selected in the GitHub Actions
workflow-dispatch form. It accepts `customer_id`, `environment`, and the
numeric `release_version` used for migration minimum-version checks, plus
`bootstrap_runtime`. `bootstrap_runtime` defaults to `false`: the workflow
discovers and reuses the existing runtime deployment outputs. Set it to
`true` only when creating the runtime for the first time. The
workflow rejects tag refs and requires a branch; the migration release version
is supplied explicitly because branches do not carry a release version. The customer tenant, subscription, location, migration
identity, and deployment parameters come from the non-secret
`config/customers.json` catalog. The subscription is never an operator input.
Generated platform and customer resource IDs and URIs are deliberately not
catalog fields; the workflow obtains them from Bicep deployment outputs.

Before enabling this combined workflow, add the LYHYT automation values to the
selected record in `config/customers.json`:

```json
"automation": {
  "lyhytAzureClientId": "...",
  "lyhytAzureTenantId": "...",
  "lyhytPlatformSubscriptionId": "...",
  "lyhytRuntimeSubscriptionId": "...",
  "customerSqlRunnerLabel": "ubuntu-latest"
}
```

The workflow resolves these values from the typed `customer_id`; they are no
longer repository-level GitHub variables. They are identifiers and runner
labels, not secrets. The referenced client application must still have a
matching GitHub OIDC federated credential and the required Azure RBAC access.

For this combined workflow's subject-based federated credential, replace the
old tag subject with the selected branch subject. For example, the `main` branch uses
`repo:ster-co/infrastructure-lyhyt:ref:refs/heads/main`. Update the federated
credential on both the customer-tenant migration application and the LYHYT
automation application. Because this workflow permits selecting different
branches, create one exact credential per permitted branch or use an Entra
claims-matching credential if your tenant supports it; do not use a broad
repository-wide subject.

Jobs that use a GitHub Environment have a different OIDC subject. Keep or add
these exact customer-application subjects for the protected jobs:
`repo:ster-co/infrastructure-lyhyt:environment:customer-foundation-apply` and
`repo:ster-co/infrastructure-lyhyt:environment:sql-migrations-destructive`.
The branch subject applies to login steps that do not use an Environment.

Protect the `customer-foundation-apply` Environment with required reviewers.
Protect `sql-migrations-destructive` separately with customer change-control
reviewers. That Environment is used only when the migration plan finds a
destructive migration and the job must pass `--allow-destructive`. No SQL
password, client secret, access token, or secret-bearing connection string is
configured as a workflow variable.

The customer foundation is deployed in the selected customer tenant. The SQL
migration jobs authenticate through GitHub OIDC/WIF using the catalog
migration application, and consume only the safe SQL outputs from the
foundation apply (`sqlServerFqdn`, `sqlDatabaseName`, and the two SQL resource
IDs). They run preflight, verify the manifest, apply exactly one standard or
approved destructive migration path, and then hand off to a separate runtime
deployment in the LYHYT tenant. The runtime managed identity is not the SQL
migration identity and receives no migration permissions.

Production private endpoints require the SQL preflight, plan, and apply jobs
to run on the labeled self-hosted runner inside or connected to the customer
network. A GitHub-hosted runner cannot reach a SQL server whose public access
is disabled. Temporary `.bicepparam` files are rendered for each job and
deleted after the job; do not read, modify, expose, or commit files matching
`*.local.bicepparam`.

The platform deployment must use a stable deployment name per environment
(for example, `lyhyt-platform-tst`). The customer workflow reads the safe ACR
and optional platform Key Vault outputs from that named deployment; it does not
redeploy the shared platform for every customer.

The safe Key Vault handoff is customer-first: apply the customer foundation,
run the SQL gates, then create or discover the LYHYT runtime vault and
identities, publish all runtime entries, and redeploy or restart the runtime
with the runtime vault URI. Populate real operator-managed secrets later
through a secured workflow, validate the application, and only then set
`REQUIRE_KEY_VAULT=true`. The customer foundation vault remains
customer-tenant-owned and receives no runtime-owned values. See
[`docs/key-vault-contract.md`](docs/key-vault-contract.md) and
[`docs/database/migrations/README.md`](docs/database/migrations/README.md) for
the detailed bootstrap, permissions, migration authoring, Stabu code
reference-data import, and operations runbooks.
