# LYHYT Runtime-Only Workflow Design

**Date:** 2026-10-02  
**Status:** Approved for implementation

## Goal

Provide a standalone GitHub Actions workflow that deploys and configures the
LYHYT customer runtime without deploying, querying, or authenticating to the
customer foundation or customer tenant.

## Scope and boundaries

- Keep `infra/lyhyt-customer-runtime/main.bicep` as the only runtime resource
  definition.
- Add a separate workflow for the Container App, three Function Apps, runtime
  identities, storage, networking, monitoring, and exactly one LYHYT runtime
  Key Vault.
- Treat the already-deployed LYHYT shared platform as a prerequisite. Read its
  named deployment outputs for the ACR reference and optional platform vault;
  never redeploy the platform in this workflow.
- Do not reference or deploy `infra/customer-foundation/main.bicep`.
- Do not log in to the customer tenant, query customer subscriptions, run SQL
  migrations, or accept a release version or customer-foundation parameters.
- Do not accept secrets, credentials, passwords, API keys, connection strings,
  or secret-bearing deployment outputs.

## Catalog resolution

The runtime-only workflow resolves the selected customer/environment from
`config/customers.json` using a focused resolver. It validates only the data
needed by this path:

- customer and environment existence and enabled state;
- runtime subscription, location, and region code;
- LYHYT automation client ID and tenant ID;
- LYHYT platform and runtime subscription IDs; and
- runtime Bicep parameters and their typed Key Vault configuration.

The customer tenant ID may be read as a non-secret value solely to populate
the existing `sp-tenant-id` runtime entry. It is never used for Azure login or
resource deployment.

## Workflow sequence

1. Validate that the workflow runs from a branch and resolve the runtime-only
   catalog record.
2. Log into the LYHYT tenant and read the stable shared-platform deployment
   outputs. Validate that the ACR resource ID belongs to the configured
   platform subscription and that any platform vault resource ID does too.
3. Log into the LYHYT runtime subscription and run a bootstrap deployment of
   the existing runtime template. The deployment creates or updates the
   runtime resource group, networking, storage, monitoring, runtime Key Vault,
   four workload identities, role assignments, Container App, and three
   Function Apps. On reruns, preserve an existing Container App's active
   Key Vault URI and `REQUIRE_KEY_VAULT` setting instead of temporarily
   disabling it.
4. Publish the complete 49-entry runtime Key Vault contract. The publisher
   receives runtime outputs and the catalog customer tenant ID only. Since no
   customer foundation outputs are available, foundation-derived entries are
   initialized as `not-configured`; runtime-derived Function route endpoints
   and `sp-tenant-id` are hydrated when valid.
5. Redeploy the existing runtime template with the runtime vault resource ID
   and URI, preserving the configured `requireKeyVault` value. This wires both
   existing application vault URI settings to the single runtime vault.

The deployment is safe to rerun. Temporary rendered `.bicepparam` files are
created in the runner temporary directory and deleted on exit. Deployment
outputs passed between jobs contain only resource IDs, names, URIs,
hostnames, and identity identifiers.

## Key Vault and security model

The runtime template creates the only runtime Key Vault in the LYHYT tenant
and runtime subscription. The four workload identities receive
`Key Vault Secrets User`. The LYHYT automation service principal receives
`Key Vault Secrets Officer` only at this vault scope for publication.

Publication retains the existing allowlist, placeholder, idempotency, and
name-only drift semantics. It never overwrites populated operator-managed
values and never prints secret values. `azure-web-jobs-storage` remains
`not-configured`; Function host storage continues to use the existing
identity-based `AzureWebJobsStorage__*` settings.

Foundation-derived entries such as SQL server/database names, AI and Search
endpoints, and model deployment names are intentionally not synthesized. They
can be hydrated later by the combined customer-foundation workflow or an
approved safe handoff, without changing this runtime-only workflow.

## Testing and verification

Add tests that prove:

- runtime-only catalog resolution does not require migration or foundation
  configuration;
- the standalone workflow has no customer-foundation jobs, template
  references, customer-tenant login, SQL migration, or release-version input;
- the workflow reads, but does not deploy, the shared platform;
- bootstrap, publication, and final runtime deployment occur in order;
- runtime-only publication initializes missing entries and hydrates only
  runtime-safe values; and
- the existing secret-surface and Key Vault architecture constraints remain
  intact.

Run the repository test suite, Bicep lint/build/build-params checks for the
affected entry points, and `git diff --check`. Do not deploy Azure resources
during verification.
