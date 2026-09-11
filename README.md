# LYHYT Infrastructure

Azure Bicep templates for the LYHYT shared platform and customer runtimes.

## Repository layout

- `infra/lyhyt-platform/` provisions the shared platform resource group and Azure Container Registry.
- `infra/lyhyt-customer-runtime/` provisions a customer resource group, monitoring, Container Apps environment, identity, registry access, and Container App.
- `reference/exports/` contains exported Azure reference templates for comparison only.

## Prerequisites

- Azure CLI with Bicep support
- An Azure subscription and permission to create the resources
- An authenticated Azure CLI session (`az login`)

## Validate templates

```bash
az bicep lint --file infra/lyhyt-platform/main.bicep
az bicep build --file infra/lyhyt-platform/main.bicep --stdout > /dev/null
az bicep build-params --file infra/lyhyt-platform/environments/tst.bicepparam --stdout > /dev/null

az bicep lint --file infra/lyhyt-customer-runtime/main.bicep
az bicep build --file infra/lyhyt-customer-runtime/main.bicep --stdout > /dev/null
az bicep build-params --file infra/lyhyt-customer-runtime/environments/customer.example.bicepparam --stdout > /dev/null
```

## Deploy

Deploy the shared platform at subscription scope:

```bash
az deployment sub create \
  --location swedencentral \
  --template-file infra/lyhyt-platform/main.bicep \
  --parameters infra/lyhyt-platform/environments/tst.bicepparam
```

For a customer runtime, copy and update `infra/lyhyt-customer-runtime/environments/customer.example.bicepparam` with the target registry details and image, then deploy it using the same subscription-scope command pattern.

Review the template outputs after deployment for resource names, IDs, and the Container App endpoint.

## Required role assignments 

During testing a account with contributor rights and Role Based Access Control Administrator permissions was used. Role Based Access Control Administrator is needed for ACR pull
