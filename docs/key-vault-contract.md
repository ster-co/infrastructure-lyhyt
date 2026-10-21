# Key Vault and runtime identity contract

The LYHYT-owned runtime Key Vault is deployed in the LYHYT tenant and LYHYT
runtime subscription. The customer foundation does not create a Key Vault.
The combined foundation/runtime workflow publishes safe foundation metadata
to the LYHYT runtime vault along with the rest of the runtime configuration.

Each customer/environment has its own Key Vault in the LYHYT runtime tenant.

The resolved infrastructure environment uses `azure-identity 1.25.3`.
`DefaultAzureCredential` consumes `AZURE_CLIENT_ID`, so Bicep supplies each
workload identity's client ID while application code continues to use its
existing credential bootstrap.

The runtime vault name is deterministic and derived from customer code,
environment, region, and subscription identity:

```text
kvr<customer-code-prefix><environment><region-prefix><unique-suffix>
```

The generated name is lowercase, globally valid, and at most 24 characters.
The vault uses RBAC authorization, soft delete, purge protection, and the
runtime environment's configured network policy. No second runtime vault is
created.

## Typed runtime handoff

`infra/lyhyt-customer-runtime` accepts this non-secret object:

```bicep
type keyVaultConfigurationType = {
  enabled: bool
  runtimeKeyVaultResourceId: string
  runtimeKeyVaultUri: string
  platformKeyVaultResourceId: string
  platformKeyVaultUri: string
  requireKeyVault: bool
}
```

The runtime URI is passed through the existing application settings:

| Application setting | Value |
|---|---|
| `AZURE_CLIENT_ID` | Container App or Function App runtime UAMI client ID |
| `CLIENT_KEY_VAULT_URI` | `runtimeKeyVaultUri` |
| `PLATFORM_KEY_VAULT_URI` | `runtimeKeyVaultUri` |
| `REQUIRE_KEY_VAULT` | `requireKeyVault` |

Both existing vault URI settings intentionally point to the same runtime
vault. The SDB loader reads `BRAVE_SEARCH_API_KEY` from its platform-vault
path, while the application contract remains unchanged. No raw secret,
`secretRef`, or Container App `keyVaultUrl` is emitted by Bicep.

The runtime creates four workload identities: the Container App identity,
document-parser identity, mailbox-sync identity, and `sdb` identity. Each
receives `Key Vault Secrets User` on the runtime vault. The workflow's
publisher principal receives `Key Vault Secrets Officer` only at the runtime
vault scope. Customer foundation resources are deployed without a Key Vault.

## SDB runtime secret contract

These are the exact names expected by the documented URI-based SDB Key Vault
contract. The publisher creates all 48 entries. An unavailable value is
created as `not-configured`; this is never a password, token, API key,
Function key, OAuth secret, or connection string.

| SDB setting | Runtime Key Vault secret |
|---|---|
| `CORS_ALLOWED_ORIGINS` | `cors-allowed-origins` |
| `SESSION_SECRET` | `session-secret` |
| `DB_SERVER_NAME` | `db-server-name` |
| `DB_NAME` | `db-name` |
| `DB_USER_NAME` | `db-user-name` |
| `DB_PASSWORD` | `db-password` |
| `AZURE_OPENAI_ENDPOINT` | `azure-openai-endpoint` |
| `AZURE_OPENAI_API_KEY` | `azure-openai-api-key` |
| `AZURE_API_VERSION` | `azure-api-version` |
| `LLM_MODEL_FULL` | `llm-model-full` |
| `LLM_MODEL_FAST` | `llm-model-fast` |
| `AZURE_EMBEDDING_DEPLOYMENT` | `azure-embedding-deployment` |
| `AZURE_OPENAI_EMBEDDING_DIMENSIONS` | `azure-openai-embedding-dimensions` |
| `AZURE_SEARCH_SERVICE_ENDPOINT` | `azure-search-service-endpoint` |
| `AZURE_SEARCH_API_KEY` | `azure-search-api-key` |
| `AZURE_SEARCH_INDEX_NAME` | `azure-search-index-name` |
| `AZURE_SEARCH_PROJECT_INDEX_NAME` | `azure-search-project-index-name` |
| `AZURE_SEARCH_INDEXER_NAME` | `azure-search-indexer-name` |
| `SP_CLIENT_ID` | `sp-client-id` |
| `SP_TENANT_ID` | `sp-tenant-id` |
| `SP_SECRET_VALUE` | `sp-secret-value` |
| `SP_DOMAIN` | `sp-domain` |
| `SP_SITE_NAME` | `sp-site-name` |
| `SP_FOLDER` | `sp-folder` |
| `SP_OFFERS_SUBFOLDER` | `sp-offers-subfolder` |
| `AAD_APP_ID_URI` | `aad-app-id-uri` |
| `AAD_JWKS_URL` | `aad-jwks-url` |
| `EXTRACTION_ENDPOINT` | `extraction-endpoint` |
| `EXTRACTION_CODE` | `extraction-code` |
| `DOCUMENT_PARSER_ENDPOINT` | `document-parser-endpoint` |
| `DOCUMENT_PARSER_CODE` | `document-parser-code` |
| `EXTRACTION_QUEUE_NAME` | `extraction-queue-name` |
| `OFFERTE_FLOW_QUEUE_NAME` | `offerte-flow-queue-name` |
| `JOB_STATUS_CONTAINER_NAME` | `job-status-container-name` |
| `GRAPH_MAILBOX_USER` | `graph-mailbox-user` |
| `OFFERS_MAILBOX_USER` | `offers-mailbox-user` |
| `PARSER_DECISION_NOTIFY_TO` | `parser-decision-notify-to` |
| `PARSER_DECISION_NOTIFY_FROM` | `parser-decision-notify-from` |
| `MAIL_ATTACHMENTS_STORAGE_CONNECTION` | `mail-attachments-storage-connection` |
| `MAIL_ATTACHMENTS_CONTAINER` | `mail-attachments-container` |
| `REPLY_MAILBOX` | `reply-mailbox` |
| `BRAVE_SEARCH_API_KEY` | `brave-search-api-key` |
| `AFAS_API_KEY` | `afas-api-key` |
| `AFAS_API_VERSION` | `afas-api-version` |
| `AFAS_OMGEVINGS_NUMMER` | `afas-omgevings-nummer` |
| `AFAS_OMGEVINGS_TYPE` | `afas-omgevings-type` |
| `BASE_GROUP_NAME` | `base-group-name` |
| `BASE_GROUP_PERMISSIONS` | `base-group-permissions` |

## Safe hydration and publication

The workflow passes only safe deployment facts between jobs. The publisher
hydrates these values when outputs are present:

| Secret | Safe source |
|---|---|
| `db-server-name` | SQL server FQDN |
| `db-name` | SQL database name |
| `azure-openai-endpoint` | AI endpoint |
| `azure-search-service-endpoint` | Search endpoint |
| `llm-model-full` | GPT-5.4 deployment output |
| `llm-model-fast` | GPT-5-mini deployment output |
| `azure-embedding-deployment` | text-embedding-3-large deployment output |
| `sp-tenant-id` | selected customer configuration |
| `extraction-endpoint` | SDB Function App hostname plus `/api/extraction` |
| `document-parser-endpoint` | document-parser Function App hostname plus `/api/http_trigger` |

No current safe source exists for the remaining entries. They remain
`not-configured`, including `db-password`, all API keys and secrets,
mailbox values, queue/index names that are not deployment outputs, and all
other unavailable settings. The runtime uses identity-based Azure Functions
host storage; it does not publish a host storage connection string.

The retired `azure-web-jobs-storage` entry is no longer created or required.
If it already exists in a vault, publication leaves it untouched.

The three Function Apps share one host-storage account with account-level
storage RBAC. Separate managed identities therefore do not isolate the
workload queues and containers in that account; narrower scopes or separate
accounts would be required for storage isolation.

Publication is idempotent and drift-aware:

- missing entries are created with their hydrated value or `not-configured`;
- an existing `not-configured` entry may be replaced by a hydrated value;
- existing populated values are preserved when no safe hydrated value exists;
- a populated value conflicting with a hydrated value stops the run before
  any write; and
- matching values are left unchanged.

The publisher reports names and operation counts only. It never prints secret
values. It uses bounded retries for transient Azure CLI failures and has no
blanket overwrite switch. Operator-managed values must be rotated through an
explicit, separately controlled process.

## Customer foundation Key Vault boundary

The `.github/workflows/customer-foundation.yml` workflow applies customer
foundation resources without creating or publishing to a customer Key Vault.
It creates the SQL server and database but does not run SQL migrations or
seed data. SQL migrations remain in the combined foundation/runtime workflow.

## Standalone runtime-only sequence

The standalone `.github/workflows/lyhyt-runtime.yml` path requires the named
shared-platform deployment to exist first. It reads the safe ACR and optional
platform Key Vault outputs, but does not redeploy the shared platform. Its
manual inputs are the enabled catalog `customer_id` and `environment`; the
workflow must run from a branch.

The sequence is:

1. **Bootstrap:** log in only to the LYHYT tenant and runtime subscription and
   deploy or update the LYHYT runtime resources, identities, and exactly one
   runtime Key Vault.
2. **Runtime-only publication:** publish the complete contract using runtime
   outputs and catalog-safe values. With no customer-foundation outputs,
   foundation-derived entries remain `not-configured`; the publisher does not
   synthesize SQL, AI, Search, or model deployment values. Runtime-derived
   endpoints and other safe values are hydrated when available.
3. **Final wiring:** redeploy the runtime with the runtime vault resource ID
   and URI so both application vault settings point to that vault.

This path never deploys, queries, or authenticates to the customer foundation
or customer tenant and does not run SQL migrations. A catalog customer tenant
ID may be retained as the non-secret `sp-tenant-id` value, but it is not used
for Azure login or resource access. The standalone workflow is safe to rerun;
it preserves populated operator-managed values and the active runtime Key
Vault settings.

## Combined customer-foundation sequence and operations

The combined customer-foundation/runtime workflow remains the path for SQL
migrations and runtime deployment. It follows this sequence:

1. Apply the customer foundation in the customer tenant and collect safe
   endpoints and deployment names.
2. Complete the customer SQL gates: preflight, migration plan, and exactly
   one approved migration path.
3. In the LYHYT tenant and runtime subscription, bootstrap the runtime
   resources and identities, or discover the existing runtime and its safe
   outputs.
4. Publish the complete 48-entry configuration to the runtime vault.
5. Deploy or restart the runtime with the completed runtime vault URI and
   `REQUIRE_KEY_VAULT` setting.

Reruns preserve the active runtime URI and existing application Key Vault
settings. The workflow validates that runtime resource IDs belong to the
selected LYHYT runtime subscription. Local tests and documentation validation
do not deploy Azure resources.

The runtime vault's network policy is inherited from environment
configuration. Production should use private endpoints and private DNS as
required by the platform network design. Soft-delete retention and purge
protection are enabled by default.

Secret rotation requires updating the runtime vault and restarting or
revising workloads when the application caches values at startup. Validate
Key Vault RBAC propagation before requiring Key Vault access at startup.

## SQL authentication limitation

The current infrastructure configures Entra-only SQL authentication and does
not create a SQL password. In the SDB runtime contract, `db-server-name` and
`db-name` can be hydrated, but `db-password` remains `not-configured`. SDB SQL
access remains blocked until the application supports Entra/managed-identity
SQL authentication or the authentication design is explicitly changed. This
infrastructure change does not invent a SQL password or alter the database
authentication model.

Cross-tenant customer-enterprise-application and workload-identity
federation details remain a customer-tenant boundary. A LYHYT identity must
not be assumed to receive customer-tenant RBAC directly.

Mailbox-sync's Graph application permission names and the customer-tenant
consent owner are not yet agreed. Confirm the least-privilege Graph
application permission names from the application behavior before granting
customer-tenant consent.
