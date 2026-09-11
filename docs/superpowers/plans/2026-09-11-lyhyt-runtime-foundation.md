# LYHYT Customer Runtime Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a subscription-scoped Bicep entry point that creates only one customer’s LYHYT resource group, Log Analytics workspace, and dedicated Container Apps Environment.

**Architecture:** `main.bicep` creates the customer resource group at subscription scope and delegates workspace and Container Apps Environment creation to focused modules at resource-group scope. The workspace supplies its customer ID and secure shared key internally to the Container Apps Environment; only resource IDs and the environment default domain are exposed as top-level outputs.

**Tech Stack:** Azure Bicep, Azure CLI Bicep lint/build/build-params validation.

**Spec:** `/Users/stijn/Downloads/PLAN(2).md`, approved runtime-foundation decisions in the conversation.

## Global Constraints

- Create no Azure resources during this phase.
- Do not run `az deployment`, `az deployment what-if`, or `az acr import`.
- Do not read from or mutate Sterco or Dynamic Power tenant resources.
- Do not copy reference export secrets or generated child resources.
- Create a new Log Analytics workspace for every customer runtime.
- Keep Container App, user-assigned identity, ACR role assignment, Key Vault, and application configuration out of this phase.
- Expose no secret, workspace shared key, or credential as a top-level output.

### Task 1: Add runtime foundation modules and entry point

**Files:**
- Create: `infra/lyhyt-customer-runtime/main.bicep`
- Create: `infra/lyhyt-customer-runtime/modules/monitoring.bicep`
- Create: `infra/lyhyt-customer-runtime/modules/container-environment.bicep`
- Create: `infra/lyhyt-customer-runtime/environments/customer.example.bicepparam`

**Interfaces:**
- `main.bicep` consumes `customerCode`, `environment`, `location`, `regionCode`, and optional `additionalTags`.
- `monitoring.bicep` produces a workspace resource ID, customer ID, and secure shared key for internal module composition.
- `container-environment.bicep` consumes the workspace customer ID and secure shared key and produces the managed environment ID and default domain.
- `main.bicep` produces `customerRuntimeResourceGroupName`, `logAnalyticsWorkspaceId`, `containerEnvironmentId`, and `containerEnvironmentDefaultDomain`.

- [x] **Step 1: Verify the new entry point is absent before implementation**

Run:

```bash
test ! -e infra/lyhyt-customer-runtime/main.bicep
```

Expected: exit code `0` before implementation.

- [x] **Step 2: Add the monitoring module**

Create a `Microsoft.OperationalInsights/workspaces@2025-07-01` resource with a generated customer-specific name, 30-day retention, `PerGB2018` SKU, resource-permission-only log access, and public ingestion/query enabled. Return only internal module outputs; mark the workspace shared key output secure.

- [x] **Step 3: Add the Container Apps Environment module**

Create a `Microsoft.App/managedEnvironments@2026-01-01` resource with customer-specific naming, Log Analytics application logging, public network access enabled, and a Consumption workload profile. Do not add a Container App, image, identity, Key Vault, or role assignment.

- [x] **Step 4: Add the subscription-scoped runtime entry point**

Create the customer runtime resource group and invoke both modules at that resource-group scope. Use names in the form:

```text
rg-lyhyt-<customer>-<environment>-<region>
log-lyhyt-<customer>-<environment>-<region>
cae-lyhyt-<customer>-<environment>-<region>
```

Expose only the four approved safe outputs.

- [x] **Step 5: Add a non-deploying example parameter file**

Use `customerCode = 'pilot'`, `environment = 'tst'`, `location = 'swedencentral'`, and `regionCode = 'swec'`. Keep the file free of subscription IDs, tenant IDs, credentials, and image references.

### Task 2: Validate the foundation without Azure mutation

**Files:**
- Test: `infra/lyhyt-customer-runtime/main.bicep`
- Test: `infra/lyhyt-customer-runtime/environments/customer.example.bicepparam`

- [x] **Step 1: Run structural assertions**

Confirm the runtime files exist, the four outputs exist, and no Container App, ACR, user-assigned identity, Key Vault, or role assignment is declared in the new phase.

- [x] **Step 2: Run Bicep lint and build**

```bash
az bicep lint --file infra/lyhyt-customer-runtime/main.bicep
az bicep build --file infra/lyhyt-customer-runtime/main.bicep --stdout > /dev/null
```

- [x] **Step 3: Build the example parameter file**

```bash
az bicep build-params \
  --file infra/lyhyt-customer-runtime/environments/customer.example.bicepparam \
  --stdout > /dev/null
```

- [x] **Step 4: Confirm no deployment command was run**

Review the executed command set and report that only local file operations and Bicep compilation were performed.
