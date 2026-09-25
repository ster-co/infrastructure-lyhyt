# Three Customer Function Apps on Flex Consumption

## Status

Approved design for the LYHYT customer runtime infrastructure.

## Goal

Provision three customer-scoped Azure Function Apps in the LYHYT customer
runtime: `document-parser`, `mailbox-sync` (the `getmail` application), and
`sdb`, each with a separate user-assigned managed identity, dedicated Flex
Consumption plan, identity-based Function host storage, Key Vault bootstrap,
Application Insights integration, and workload storage resources where needed.

## Scope

This change modifies only the infrastructure repository. It does not modify
the three application repositories, publish application packages, populate
secret values, grant customer-tenant permissions, or perform deployments.

The fourth Function App is outside this change.

## Architecture

All three Function Apps are deployed by `infra/lyhyt-customer-runtime` in the
LYHYT tenant. Each app receives its own user-assigned managed identity and its
own Flex Consumption plan. The apps share the runtime Function host storage
account for identity-based host storage; workload-specific Blob containers and
queues are created in that account for `document-parser` and `sdb`.

Each Function App also receives a dedicated deployment Blob container in the
same storage account. Flex `functionAppConfig.deployment.storage` points to
that container and authenticates with the app's own user-assigned identity.
CI/CD remains responsible for publishing the package into the configured
deployment container.

The host-storage role assignments are intentionally at storage-account scope.
Therefore each of the three identities can access the other apps' workload
queues and containers. Separate user-assigned identities do not provide
storage isolation under this shared-account design. A future isolation change
would require separate storage accounts or narrower scopes.

The existing platform and customer Key Vault resources are reused. Bicep
passes only Key Vault URIs, identity client IDs, host-storage settings, and
monitoring settings. Secret values are never supplied through Bicep. Existing
safe customer configuration, including resource endpoints, continues to be
published to the customer Key Vault by the established customer-side workflow.

Application code must later activate managed-identity Key Vault access and
replace incompatible connection-string-only storage SDK paths. API keys and
client secrets may remain valid authentication methods when their real values
are loaded securely from Key Vault; replacing every API-key path with managed
identity is not a prerequisite for this infrastructure change. The
infrastructure must document the confirmed blockers without claiming that the
applications are runnable after resource creation alone.

## Function App contracts

### `document-parser`

- Python 3.12 and Functions runtime v4.
- HTTP, Storage Queue, and Timer triggers.
- Uses `sync-jobs`, `di-cache`, and `sync-reports`.
- Docling queue/container resources are created only when the Docling path is
  explicitly enabled.
- Current code uses a storage connection string and API/client secrets; the
  storage path and inactive Key Vault loading are application migration
  blockers. API/client secrets remain valid if securely loaded from Key Vault.
- Current workload is not approved for Y1; the dedicated Flex plan is required.

### `mailbox-sync` / `getmail`

- Python 3.11 baseline; the repository does not pin Python or package versions.
- Hourly Timer trigger only; no application queues or Blob containers.
- Requires SQL connectivity, Microsoft Graph, and an outbound webhook.
- Requires ODBC Driver 18 for SQL Server. CI installation does not prove that
  the driver exists in the Flex runtime; deployment must perform a real
  runtime/SQL connectivity check.
- Current code expects `CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID`, SQL
  credentials, and a webhook URL. The user-assigned identity does not replace
  these credentials by itself.
- `MAX_MAILS_PER_RUN=0` remains an operational follow-up because it permits an
  unbounded run.

### `sdb`

- Python 3.12 and Functions runtime v4.
- HTTP, Storage Queue, and Timer triggers.
- Uses `extraction-jobs`, `offerte-flow-jobs`, both poison queues, and the
  `background-job-status` Blob container.
- Calls `document-parser` through its endpoint and function key during the
  current application contract.
- Current code uses `AzureWebJobsStorage` as a connection string and has a
  Key Vault bootstrap that is not activated by the Function App entry point.
- Current code uses client-secret, API-key, and SQL-authentication paths. These
  remain valid if securely loaded from Key Vault; the inactive Key Vault
  bootstrap and connection-string-only storage path remain blockers.

## Key Vault contract

The existing platform and customer Key Vault modules remain the source of
vaults. This change must not create duplicate vaults or placeholder secrets.

The Function App settings are limited to:

- `AZURE_CLIENT_ID`.
- `CLIENT_KEY_VAULT_URI`.
- `PLATFORM_KEY_VAULT_URI`.
- `REQUIRE_KEY_VAULT`.
- `APPLICATIONINSIGHTS_CONNECTION_STRING`.
- Functions host/runtime settings.
- Identity-based host-storage settings.

Existing safe customer endpoints and resource identifiers remain in the
customer Key Vault contract. They are not copied back into Function App
settings by this change.

The documented secret mapping must distinguish confirmed names from names that
still require agreement:

| Application | Setting | Secret name/status |
| --- | --- | --- |
| document-parser | Document Intelligence key | Secret name not yet agreed |
| document-parser | `AZURE_SEARCH_KEY` | `azure-search-api-key` is existing |
| document-parser | `AZURE_OPENAI_KEY` | `azure-openai-api-key` is existing |
| document-parser | `SP_SECRET_VALUE` | `sp-secret-value` is existing |
| document-parser | parser function key | `document-parser-code` is existing |
| mailbox-sync | `DB_USER` | `db-user-name` is existing |
| mailbox-sync | `DB_PASSWORD` | `db-password` is existing |
| mailbox-sync | `CLIENT_SECRET` | Secret name not yet agreed |
| mailbox-sync | webhook token, if present | Secret name not yet agreed |
| sdb | `SP_SECRET_VALUE` | `sp-secret-value` is existing |
| sdb | `DOCUMENT_PARSER_CODE` | `document-parser-code` is existing |
| sdb | `AZURE_OPENAI_API_KEY` | `azure-openai-api-key` is existing |
| sdb | `AZURE_SEARCH_API_KEY` | `azure-search-api-key` is existing |
| sdb | `DB_USER_NAME` | `db-user-name` is existing |
| sdb | `DB_PASSWORD` | `db-password` is existing |
| sdb | `SESSION_SECRET` | `session-secret` is existing |

The legacy `azure-web-jobs-storage` secret is not used by the infrastructure
host-storage contract. The `from_connection_string()` application calls must
be migrated before identity-only storage is functional. API keys and client
secrets may remain in use if the application retrieves their real values from
Key Vault through an activated bootstrap and the required permissions exist.

## Flex and deployment contract

Each Function App receives a separate Flex Consumption plan. The Function App
resource uses the Flex-compatible configuration supported by the selected API
version and does not set `WEBSITE_RUN_FROM_PACKAGE=1`. Package publication
uses that app's deployment container and managed identity. Package publication
remains a separate CI/CD operation using each application's existing package
workflow.

The Bicep entry point must expose the runtime versions explicitly and must not
retain the Y1/Dynamic default for this deployment path. It must not claim that
an app is ready until its package is published, secrets are populated, required
permissions exist, and the application-code migration blockers are resolved.

## Storage and RBAC

The runtime host storage account is shared by the three apps, but storage
resources are explicitly named and created:

- Three dedicated deployment Blob containers, one per Function App, used by
  Flex deployment storage.

- `document-parser`: `sync-jobs`, `di-cache`, and `sync-reports`; Docling
  resources are conditional on the Docling feature flag.
- `mailbox-sync`: no application Blob containers or queues.
- `sdb`: `extraction-jobs`, `offerte-flow-jobs`, their poison queues, and
  `background-job-status`.

Each app identity receives the existing host-storage roles at the storage
account scope, including access needed for its own deployment container. This
also grants each identity access to the other apps' workload queues and
containers. Application-code RBAC changes for customer SQL, Search, OpenAI,
Document Intelligence, Graph, or customer-tenant resources are documented but
not invented in this infrastructure change.

## Monitoring

Create one Application Insights component per customer runtime environment and
pass its connection string as a non-secret Function App setting to all three
apps. The existing Log Analytics workspace remains available for the broader
runtime. Diagnostic settings and operational alerting remain explicit
infrastructure outputs or follow-up work where Azure resource requirements
cannot be safely inferred from the audits.

## Validation and handoff

Validation must verify:

- Three Function App names and three distinct identity resource IDs.
- Three Flex plan resources and no Y1 default in the active runtime contract.
- No `WEBSITE_RUN_FROM_PACKAGE` setting on Flex apps.
- Required storage containers/queues and per-identity host-storage RBAC.
- Three dedicated Flex deployment containers, deployment-storage identity
  references, and storage dependencies.
- Explicit validation/documentation that storage-account RBAC is shared across
  all three identities and does not isolate workloads.
- Key Vault URI/client-ID bootstrap settings and optional vault RBAC.
- Application Insights settings.
- No secret values in Bicep parameters, outputs, app settings, or generated
  deployment artifacts.
- `az bicep lint`, `az bicep build`, and `az bicep build-params` for the changed
  entry points.
- Existing Python pipeline tests and configuration validation.

The handoff must separate:

1. Resources and safe settings provisioned by Bicep.
2. Package publication and SQL setup performed by controlled CI/CD/migration.
3. Application changes required for Key Vault, managed identity, storage SDK,
   external authentication, and runtime compatibility.
4. Unresolved deployment blockers, including ODBC Driver 18 availability,
   unpinned `mailbox-sync` dependencies, secret names still requiring agreement,
   Graph permissions, customer-tenant access, application Key Vault bootstrap
   activation, connection-string-only storage SDK calls, missing secrets, and
   missing permissions. API-key/client-secret use is not itself a blocker when
   values are securely loaded from Key Vault.
