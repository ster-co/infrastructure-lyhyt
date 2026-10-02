# LYHYT Per-Customer Runtime Key Vault Design

**Date:** 2026-10-02  
**Status:** Approved; implementation in progress

## Goal

Create exactly one LYHYT-owned runtime Key Vault for every customer/environment
runtime, populate its complete SDB configuration contract without inventing
secrets, and wire the existing application Key Vault bootstrap to that vault
without changing the SDB/application repository.

## Scope and boundaries

- Change only infrastructure Bicep, workflow orchestration, publishing scripts,
  infrastructure tests, and documentation in this repository.
- Do not modify SDB/application source code or Function App source code.
- Do not deploy Azure resources during implementation or verification.
- Keep the existing customer-foundation Key Vault resource and its tenant
  boundary. It must no longer receive runtime-owned configuration through the
  runtime publication workflow.
- Do not create a second LYHYT runtime or shared platform Key Vault.

## Contract discovery

The sibling SDB repository was inspected read-only. Its
`backend/app/key_vault.py` `SECRET_REGISTRY` is the authoritative loader
contract. It maps application environment variables to these exact Key Vault
names:

| Application variable | Runtime Key Vault name |
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
| `AzureWebJobsStorage` | `azure-web-jobs-storage` |
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

The application loader keeps `CLIENT_KEY_VAULT_URI`,
`PLATFORM_KEY_VAULT_URI`, `REQUIRE_KEY_VAULT`, and `AZURE_CLIENT_ID` as
bootstrap application settings. They are not runtime vault entries.

## Runtime infrastructure

`infra/lyhyt-customer-runtime/main.bicep` will deploy one
`Microsoft.KeyVault/vaults` resource through a focused module in the LYHYT
runtime resource group. The vault name will be deterministic, globally safe,
and derived from customer code, environment, region, and subscription identity.
The module will use:

- `tenantId: subscription().tenantId`, ensuring LYHYT-tenant ownership;
- the runtime subscription/resource-group deployment scope;
- RBAC authorization with empty access policies;
- soft delete and purge protection;
- the existing runtime public-network and Key Vault network-action settings.

The runtime entry point will grant the built-in Key Vault Secrets User role to
all four workload identities:

1. Container App identity;
2. document-parser Function App identity;
3. mailbox-sync Function App identity;
4. SDB Function App identity.

Role assignments will be deterministic, scoped to the new runtime vault, and
ordered before the application resources that receive Key Vault bootstrap
settings. The existing optional shared platform-vault role assignments remain
separate and do not create another vault.

The runtime deployment will output the runtime vault resource ID, name, and
URI, alongside the existing identity IDs and Function App hostnames. No secret
values will be outputs.

## Existing application wiring

The existing application settings contract is preserved. The final runtime
deployment will pass the new runtime vault URI through the current typed Key
Vault configuration mechanism:

- `CLIENT_KEY_VAULT_URI` points to the runtime vault;
- `PLATFORM_KEY_VAULT_URI` also points to the runtime vault.

The second assignment is intentional: the current SDB loader reads
`BRAVE_SEARCH_API_KEY` from its platform URI, while the requested design moves
that value into the per-customer runtime vault. Pointing both existing URI
settings at the single runtime vault achieves that move without application
source changes or a second vault.

`AZURE_CLIENT_ID` remains the existing user-assigned identity client ID for
each workload. Function App and Container App application settings retain
their existing names and behavior.

## Configuration publication

A focused runtime publisher will own the complete allowlist above. It will:

- initialize every missing entry to the literal `not-configured`;
- hydrate safe values from foundation and runtime deployment outputs where a
  stable mapping exists;
- never accept secret values through Bicep parameters, catalog JSON, outputs,
  or logs;
- list existing names without printing values;
- leave identical existing values unchanged;
- stop with a name-only drift error when an existing value differs;
- never silently overwrite operator-managed values;
- make repeated publication idempotent.

Desired-value reconciliation is calculated for every entry before any write:

| Existing entry | Hydration available | Action |
|---|---|---|
| Missing | Yes | Create the hydrated value |
| Missing | No | Create literal `not-configured` |
| `not-configured` | Yes | Replace with the hydrated value |
| Existing entry | No | Preserve unchanged |
| Matches hydrated value | Yes | Skip |
| Populated value differs from hydration | Yes | Fail with a name-only drift error |

`not-configured` is an initialization marker, never a desired replacement for
a populated value. The publisher preflights every entry and reports all
conflicts before making any write. It does not create new versions for
unchanged values and has no blanket overwrite switch. A legitimate
infrastructure change is reconciled per entry: an operator verifies the new
safe output, reads the name-only conflict report, and explicitly updates only
that Key Vault secret through the approved operator secret-management path
before rerunning publication. Real credentials are never supplied to this
publisher through Bicep or workflow outputs.

### Hydration sources and formats

The publisher accepts deployment output JSON from the customer foundation and
LYHYT runtime deployments. Every hydrated value has a fixed source and format:

| Runtime entry | Source | Transformation and format | Ownership |
|---|---|---|---|
| `db-server-name` | Foundation `sqlServerFqdn` | Copy the non-empty SQL FQDN; hostname only, not a connection string | Infrastructure |
| `db-name` | Foundation `sqlDatabaseName` | Copy the non-empty database name | Infrastructure |
| `azure-openai-endpoint` | Foundation `aiEndpoint` | Copy the absolute HTTPS endpoint URL | Infrastructure |
| `azure-search-service-endpoint` | Foundation `searchEndpoint` | Copy the absolute HTTPS endpoint URL | Infrastructure |
| `llm-model-full` | Foundation `gpt54DeploymentName`, when present | Copy the deployment name, not a model secret or API key | Infrastructure |
| `llm-model-fast` | Foundation `gpt5MiniDeploymentName`, when present | Copy the deployment name | Infrastructure |
| `azure-embedding-deployment` | Foundation `textEmbedding3LargeDeploymentName`, when present | Copy the deployment name | Infrastructure |
| `sp-tenant-id` | Selected customer configuration `tenantId` | Copy a validated UUID | Configuration |
| `extraction-endpoint` | Runtime `sdbFunctionAppHostname`, when a route contract is available | Build `https://<hostname>/api/extraction`; never use a bare hostname | Infrastructure |
| `document-parser-endpoint` | Runtime document-parser hostname only when its application route is explicitly known | Build an absolute HTTPS route; otherwise leave `not-configured` | Infrastructure |
| `azure-web-jobs-storage` | No valid secret-bearing output | Keep `not-configured`; identity-based Function host storage remains in app settings | Operator/application |

Search index names, project index names, indexer names, storage container and
queue names, endpoint paths, and all other values without a verified output
contract remain `not-configured`. `azure-web-jobs-storage` is deliberately
separate from Function host storage: the Functions host continues using its
existing identity-based `AzureWebJobsStorage__*` settings, and the publisher
does not add `AzureWebJobsStorage=not-configured` to Function App settings.

Credentials and operator-managed configuration, including API keys, OAuth
secrets, Function keys, connection strings, CORS policy, mailboxes, SharePoint
paths, AFAS values, session secrets, Brave credentials, and group permissions,
remain `not-configured` unless supplied through a separate approved operator
secret-management process. Secret names alone are never treated as evidence
that a valid value can be synthesized.

The workflow principal is the catalog-selected LYHYT automation application
used by `azure/login`. It receives a narrowly scoped Key Vault data-plane
writer role on the runtime vault, such as `Key Vault Secrets Officer`, only
for the publication step and only at that vault scope. The four workload
identities retain the read-only `Key Vault Secrets User` role and do not gain
write access. Publication retries transient RBAC/network failures with a
bounded attempt count and backoff; authentication, authorization, validation,
and drift failures stop immediately. The publisher runner must have network
reachability to the vault, and production private-endpoint vaults require the
runner to resolve and reach the private DNS zone. Workloads have the analogous
private network and DNS requirements.

The existing customer-foundation publication step will no longer publish
runtime-owned values, including `BRAVE_SEARCH_API_KEY`, to the customer
foundation vault. The customer-foundation vault resource and unrelated
customer-side RBAC implementation remain outside this change.

## Workflow sequence

The workflow will use the following safe ordering:

1. Deploy the LYHYT runtime bootstrap with application Key Vault integration
   disabled. This creates the runtime vault, workload identities, role
   assignments, and runtime resources needed for safe output capture.
2. Deploy/apply the customer foundation as currently required, without using
   its Key Vault as the runtime configuration store.
3. Publish the complete runtime configuration to the runtime vault using safe
   foundation/runtime outputs and `not-configured` placeholders.
4. Deploy the final runtime with the runtime vault URI wired into the existing
   application settings. The deployment must use the completed vault
   configuration and preserve the existing application identity contract.

The bootstrap-only disabled setting is permitted only when the runtime is new
or has no active Key Vault integration. On reruns, the workflow reads the
existing runtime configuration and preserves active `CLIENT_KEY_VAULT_URI`,
`PLATFORM_KEY_VAULT_URI`, and `REQUIRE_KEY_VAULT` settings; it never renders a
temporary disabled configuration over an already configured runtime. The
workflow must still publish before applying final application wiring.

The workflow will continue using temporary rendered `.bicepparam` files,
delete them on exit, avoid secret-bearing workflow outputs, and never print
secret values. No Azure deployment is run as part of repository verification.

## Publisher operations and readiness

Operators securely populate real credentials through the approved Key Vault
operator path or a separately protected secret-management workflow. The path
must write directly to the runtime vault, avoid command-line and log exposure,
and restrict updates to the intended customer/environment vault. This applies
to `BRAVE_SEARCH_API_KEY`, `SESSION_SECRET`, Function keys, API keys, OAuth
secrets, and connection strings. Rotation is performed by writing a new secret
value in the vault, verifying the vault audit trail, and restarting the
affected workload so the application's one-time loader reads the new value.

Registry creation, RBAC assignment, placeholder publication, and final URI
wiring prove infrastructure completion only. They do not prove application
readiness: placeholders intentionally cause missing or invalid application
configuration, RBAC propagation may require a restart, and each workload must
be validated after real operator values are populated.

## SQL limitation

The implementation will explicitly document and test that:

- `DB_SERVER_NAME` and `DB_NAME` are hydrated from foundation outputs;
- `DB_PASSWORD` is `not-configured`;
- no SQL password is generated or stored;
- SDB SQL access remains blocked until the application supports
  Entra/managed-identity SQL authentication or the authentication design is
  explicitly changed.

## Verification

Tests will cover:

- one runtime Key Vault resource per runtime entry point;
- LYHYT tenant and runtime-subscription scope;
- all four runtime identities receiving Key Vault Secrets User;
- exact complete secret-name creation;
- deployment-output hydration and placeholder behavior;
- idempotency and name-only drift detection;
- removal of runtime-owned foundation-vault publication;
- absence of secrets in parameters, outputs, source, and logs.

Required commands:

```text
python3 -m unittest discover -s tests -v
az bicep lint --file infra/lyhyt-platform/main.bicep
az bicep lint --file infra/customer-foundation/main.bicep
az bicep lint --file infra/lyhyt-customer-runtime/main.bicep
az bicep build --file infra/lyhyt-platform/main.bicep --stdout > /dev/null
az bicep build --file infra/customer-foundation/main.bicep --stdout > /dev/null
az bicep build --file infra/lyhyt-customer-runtime/main.bicep --stdout > /dev/null
git diff --check
```
