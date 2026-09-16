# LYHYT Infrastructure

Azure Bicep templates for the LYHYT shared platform, customer foundation, and customer runtime resources.

## Repository layout

- `infra/lyhyt-platform/` provisions the shared platform resource group and Azure Container Registry.
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
```

## Deployment order

Deploy the shared platform first, then the customer foundation, and finally the customer runtime. Review and customize each parameter file before deployment. The customer runtime parameter file expects the registry created by the platform deployment and a fully qualified container image.

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
