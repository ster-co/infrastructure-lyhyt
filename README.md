# LYHYT Infrastructure

Azure Bicep templates for the LYHYT shared platform, customer foundation, and customer runtime resources.

## Repository layout

- `infra/lyhyt-platform/` provisions the shared platform resource group and Azure Container Registry.
- `infra/customer-foundation/` provisions customer-scoped Storage, Key Vault, Azure SQL, AI Services, Document Intelligence, and AI model deployments.
- `infra/lyhyt-customer-runtime/` provisions a customer resource group, Log Analytics, Container Apps Environment, managed identity, ACR pull access, and the customer Container App.
- `reference/exports/` contains exported Azure reference templates for comparison only and is excluded from Git.

Each entry point is subscription-scoped and has an example parameter file under its `environments/` directory.

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
