# LYHYT Infrastructure

Azure Bicep templates for the LYHYT shared platform, customer foundation, and customer runtime resources.

## Repository layout

- `infra/lyhyt-platform/` provisions the shared platform resource group, Azure Container Registry, and optional shared platform Key Vault.
- `infra/customer-foundation/` provisions customer-scoped Storage, Key Vault, Azure SQL, AI Services, Document Intelligence, and AI model deployments.
- `infra/lyhyt-customer-runtime/` provisions a customer resource group, Log Analytics, Container Apps Environment, managed identity, ACR pull access, and the customer Container App.
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

The runtime uses one user-assigned managed identity per customer. The dual-Key-Vault configuration is application-level: Bicep passes only the UAMI client ID, customer/platform vault resource IDs, vault URIs, and feature flags. The application reads secrets itself through `DefaultAzureCredential` and `SecretClient`; Container App `keyVaultUrl` references are intentionally not configured. See [`docs/key-vault-contract.md`](docs/key-vault-contract.md) for the exact contract, secret-name allowlists, RBAC boundaries, and deployment handoff.

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

Deploy the shared platform first, then run the runtime once with Key Vault integration disabled to create the per-customer UAMI. Use its safe identity outputs for the customer foundation access handoff, resolve both vault IDs/URIs, and redeploy the runtime with integration and applicable RBAC enabled. Review and customize each parameter file before deployment. Pass only safe deployment outputs between the independent entry points. Populate Key Vault secrets later through a secured workflow; keep `REQUIRE_KEY_VAULT=false` until application validation and restart the Container App after hydration changes. See [`docs/key-vault-contract.md`](docs/key-vault-contract.md) for the executable sequence.

### 1. Shared platform

```bash
az deployment sub create \
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

## Customer deployment workflow

The manual GitHub Actions workflow in
`.github/workflows/customer-foundation-sql-runtime.yml` deploys one catalog
customer and environment from a release tag. It accepts exactly two operator
inputs: `customer_id` and `environment`. The workflow rejects branches and
requires a `v*` tag, such as `v2026.09.23`; the migration release version is
derived from that tag. The customer tenant, subscription, location, migration
identity, and deployment parameters come from the non-secret
`config/customers.json` catalog. The subscription is never an operator input.

Before enabling the workflow, configure these GitHub variables:

- `CUSTOMER_SQL_RUNNER_LABEL`: label for a self-hosted runner with access to
  the customer's private SQL endpoint and private DNS;
- `LYHYT_AZURE_CLIENT_ID` and `LYHYT_AZURE_TENANT_ID`: the LYHYT deployment
  application and tenant;
- `LYHYT_RUNTIME_SUBSCRIPTION_ID`: the LYHYT customer-runtime subscription;
- `LYHYT_PLATFORM_SUBSCRIPTION_ID`: the LYHYT shared-platform subscription.

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

The safe Key Vault bootstrap is two-stage: deploy the LYHYT runtime once with
Key Vault integration disabled to create its UAMI, then deploy the customer
foundation and finally redeploy the runtime with the customer/platform vault
IDs and URIs. Populate secrets later through a secured workflow, validate the
application, and only then set `REQUIRE_KEY_VAULT=true`. For the same-tenant
pilot, the customer foundation may grant the UAMI the read-only customer Key
Vault role; cross-tenant production must use the customer-side enterprise
application model. See [`docs/key-vault-contract.md`](docs/key-vault-contract.md)
and [`docs/database/migrations/README.md`](docs/database/migrations/README.md)
for the detailed bootstrap, permissions, migration authoring, Stabu code
reference-data import, and operations runbooks.
