# Key Vault and runtime identity contract

This document records the infrastructure-facing contract for the selected
user-assigned managed identity (UAMI) and dual-Key-Vault design. Bicep passes
resource IDs, principal IDs, client IDs, endpoints, names, feature flags, and
vault URIs only. Secret values are populated later by a secured workflow.
The platform and customer deployments remain independent subscription-scoped
entry points even when the TST pilot happens to use one tenant and
subscription.

## Azure Identity verification

The infrastructure workspace's resolved Python environment reports
`azure-identity 1.25.3`. Its `DefaultAzureCredential.__init__` implementation
sets `managed_identity_client_id` from `AZURE_CLIENT_ID` when the argument is
not explicitly supplied, and passes that value to `ManagedIdentityCredential`.
Therefore the infrastructure must set `AZURE_CLIENT_ID` to the runtime UAMI
client ID even though the application calls `DefaultAzureCredential()` rather
than reading that variable itself.

The `keyvault2` application source and lockfile are not part of this
infrastructure workspace, so the application branch's exact lockfile version
could not be independently re-resolved here. The verified local SDK behavior
above is the basis for this safe infrastructure contract.

## Runtime configuration

`lyhyt-customer-runtime` accepts this strongly typed non-secret object:

```bicep
type keyVaultConfigurationType = {
  enabled: bool
  customerKeyVaultResourceId: string
  customerKeyVaultUri: string
  platformKeyVaultResourceId: string
  platformKeyVaultUri: string
  requireKeyVault: bool
}
```

When `enabled` is `true`, the Container App receives these exact settings:

| Source | Container App setting |
|---|---|
| runtime UAMI client ID output | `AZURE_CLIENT_ID` |
| `customerKeyVaultUri` | `CLIENT_KEY_VAULT_URI` |
| `platformKeyVaultUri` | `PLATFORM_KEY_VAULT_URI` |
| `requireKeyVault` | `REQUIRE_KEY_VAULT` as lowercase `true` or `false` |

The resource IDs are safe deployment-handoff values and are not exposed as
application environment variables. `CUSTOMER_CODE` and `ENVIRONMENT` remain
unchanged.

No Container App `keyVaultUrl`, `secretRef`, or raw secret value is configured.
The application reads both vault URIs itself through `SecretClient` and uses
`DefaultAzureCredential()`.

The contract and `REQUIRE_KEY_VAULT` flag are disabled by default in generic
examples. `REQUIRE_KEY_VAULT=true` must only be enabled after application
behavior and secret population have been validated.

## Foundation handoff

Customer foundation exposes these safe Key Vault outputs:

| Foundation output | Use |
|---|---|
| `customerKeyVaultResourceId` | customer-side RBAC scope and pipeline handoff |
| `customerKeyVaultName` | customer-side RBAC and operations |
| `customerKeyVaultUri` | runtime `CLIENT_KEY_VAULT_URI` |

The shared platform deployment exposes `platformKeyVaultResourceId`,
`platformKeyVaultName`, and `platformKeyVaultUri`. The platform Key Vault is
created once in the LYHYT platform resource group and has a lifecycle separate
from the shared ACR.

Other customer-foundation safe outputs remain available for the existing
application contract, including AI/Search endpoints and SQL host/database
names. No secret output is added.

The runtime's external ACR handoff is one typed resource reference:

```bicep
type containerRegistryReferenceType = {
  resourceId: string
  loginServer: string
}
```

`resourceId` is the canonical identity. Runtime Bicep derives its subscription,
resource-group, and registry name from that ID and deploys the ACR role
assignment at the parsed resource-group scope. `loginServer` is the separate
application endpoint and must describe that same registry; it is not used to
select the RBAC target.

The Key Vault handoff is likewise one typed object:

```bicep
type keyVaultConfigurationType = {
  enabled: bool
  customerKeyVaultResourceId: string
  customerKeyVaultUri: string
  platformKeyVaultResourceId: string
  platformKeyVaultUri: string
  requireKeyVault: bool
}
```

The platform Key Vault resource ID drives the parsed subscription,
resource-group, vault name, RBAC scope, and deterministic role-assignment
name. Its URI is an application endpoint in the same handoff and must
correspond to that ID; in Azure Public Cloud the expected form is
`https://<vault-name>.vault.azure.net/`. The customer foundation emits its
vault ID and URI from the same Key Vault resource, so the same invariant holds
there.

Vault names use a short semantic prefix and a 13-character `uniqueString`
suffix: `kvp<suffix>` for the platform vault and `kvc<suffix>` for a customer
vault. The suffix is calculated from stable deployment identity inputs,
including subscription and intended resource-group identity. The result is
lowercase, 16 characters, globally suitable, and deterministic; for example,
`kvp3f8m2n6q1w0x9` and `kvc8r4p1z7d2hsc6` illustrate the shape (the exact suffix is
Azure's value for the supplied inputs). Changing a stable input intentionally
creates a different Key Vault and must be treated as a resource migration,
not as an in-place rename.

## Exact secret-name allowlists

These names are documented for the future secured Bash workflow only. This
repository must never contain their values.

Customer Key Vault:

- `azure-openai-api-key`
- `azure-search-api-key`
- `db-password`
- `db-user-name`
- `sp-secret-value`
- `azure-web-jobs-storage`
- `mail-attachments-storage-connection`
- `session-secret`
- `extraction-code`
- `document-parser-code`
- `afas-api-key`

Shared platform Key Vault:

- `brave-search-api-key`

## RBAC boundaries

The runtime UAMI receives:

- `AcrPull` on the shared ACR;
- optionally, `Key Vault Secrets User` on the shared platform Key Vault;
- optionally, through the customer-side handoff, `Key Vault Secrets User` on
  the customer Key Vault during the same-tenant pilot.

The customer-side module accepts `runtimeAccessPrincipalId` and a clearly
named `enableSameTenantRuntimeKeyVaultRoleAssignment` flag. The principal is
generic so a future cross-tenant deployment can supply a customer-tenant
service-principal object ID instead of the LYHYT UAMI principal ID. WIF and
cross-tenant assignments are not implemented here.

Only the read-only `Key Vault Secrets User` role is used. No Key Vault Secrets
Officer, Key Vault Administrator, Owner, or Contributor role is granted.

The Container App deployment explicitly depends on the ACR role assignment and,
when enabled, the platform Key Vault role assignment. This orders ARM resource
creation, but ARM completion does not guarantee that Azure RBAC has propagated
to the data plane. Startup verification and, if necessary, a Container App
revision restart are still required. Bicep intentionally contains no sleeps or
arbitrary deployment delays.

## Safe UAMI bootstrap sequence

Use the existing subscription-scoped templates in this order. No secret value
is needed at any step.

1. Deploy `infra/lyhyt-platform` and obtain the shared ACR ID/login server. If
   the shared platform vault is required, enable it in this separate
   deployment and obtain its ID/name/URI.
2. Deploy `infra/lyhyt-customer-runtime` once with
   `keyVaultConfiguration.enabled=false` and
   `enablePlatformKeyVaultRoleAssignment=false`. Supply the canonical ACR
   resource reference. This creates the per-customer UAMI and basic runtime;
   the ACR role assignment remains enabled for image pull.
3. Capture the runtime outputs `identityPrincipalId` and `identityClientId`.
4. Deploy `infra/customer-foundation` with the customer choices and vault
   settings. For the same-tenant pilot, supply `runtimeAccessPrincipalId` from
   step 3 and set
   `enableSameTenantRuntimeKeyVaultRoleAssignment=true` only when the customer
   vault should grant this UAMI read access. A future customer-side deployment
   can instead supply its customer-tenant service-principal object ID; WIF is
   outside this repository.
5. Resolve the customer and platform vault IDs and URIs from their respective
   deployment outputs. Pass each ID and URI together in the runtime's typed
   `keyVaultConfiguration` object.
6. Redeploy `infra/lyhyt-customer-runtime` with
   `keyVaultConfiguration.enabled=true`, the platform role-assignment flag
   enabled when applicable, and `requireKeyVault=false`. The runtime sets
   `AZURE_CLIENT_ID` from the UAMI client ID and application-level vault URIs;
   it does not create Container App `keyVaultUrl` references.
7. Populate the exact allowlisted secrets later using a secured workflow,
   restart the Container App, and validate startup and application behavior.
8. Set `requireKeyVault=true` only after successful validation. Keep it false
   in generic examples and during the bootstrap.

The first runtime deployment and the later redeployment are intentional: the
UAMI must exist before customer-side RBAC can be granted. The runtime's
platform-vault RBAC is also optional and is only deployed when both integration
and its role-assignment flag are enabled.

Bash or pipeline orchestration passes safe values between the independent
subscription-scoped deployments. Secret values never pass through Bicep
parameters, outputs, or what-if output.

## Deliberate limitations

The following remain outside this infrastructure change:

- `REQUIRE_KEY_VAULT=true` behavior and individual-secret fallback semantics
  still require application validation.
- Secret rotation requires a Container App restart.
- Function App startup hydration and `AzureWebJobsStorage` are not addressed.
- The application branch's direct API-key print must be fixed before real
  secrets are used.
- The current PowerShell secret writer passes values as command-line
  arguments and is not a production population workflow.
- Cross-tenant WIF, Private Endpoints, Private DNS, Front Door, model changes,
  embedding changes, Storage authentication changes, and application changes
  are not implemented.
