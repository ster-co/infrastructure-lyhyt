# Customer foundation onboarding

> For new customers and coordinated application releases, use the
> [Customer lifecycle workflow](../../.github/workflows/customer-lifecycle.yml)
> and its [end-to-end guide](../customer-lifecycle.md). This standalone
> foundation workflow is retained for reviewed maintenance and migration runs.

This guide covers the customer-side identity, permissions, configuration, and
deployment steps for
[`.github/workflows/customer-foundation.yml`](../../.github/workflows/customer-foundation.yml).
The workflow deploys
[`infra/customer-foundation/main.bicep`](../../infra/customer-foundation/main.bicep)
to the selected customer tenant and subscription.

## What the workflow deploys

The subscription-scoped Bicep entry point creates a customer foundation
resource group containing:

- a Storage account and the configured blob containers;
- an Azure SQL logical server and database with the configured customer Entra
  administrator;
- Azure AI Search when enabled;
- Azure AI Services model deployments; and
- a Document Intelligence resource.

The customer foundation does not create a Key Vault. The standalone foundation
workflow does not publish resource metadata or run SQL migrations or seed
data. It runs Bicep lint, build, parameter build, and a subscription-level
what-if before the protected apply, then completes after a successful apply.
The SQL server and database are still created. SQL migrations remain in the
combined foundation/runtime workflow; see the
[database migration guide](../database/migrations/README.md).

## Customer identity and permissions

The workflow signs in to the customer tenant with GitHub Actions OIDC and
workload identity federation (WIF). Configure the multitenant deployment
application so its enterprise application exists in the customer tenant,
then set `migration.applicationClientId` in the catalog. That client ID is
used by `azure/login` for the foundation what-if and apply.

Configure an exact GitHub OIDC federated credential for each permitted branch,
for example:

```text
repo:ster-co/infrastructure-lyhyt:ref:refs/heads/main
```

The apply job uses the protected GitHub Environment and needs this separate
subject:

```text
repo:ster-co/infrastructure-lyhyt:environment:customer-foundation-apply
```

Do not use a broad repository-wide subject. `migration.principalObjectId` is
the customer-tenant service principal object ID. The standalone workflow passes
it to Bicep, which grants that identity Search Service Contributor on the
Search service for TST when Search is enabled and public network access is
enabled. The combined SQL migration workflow also uses this catalog value for
its SQL permissions.

Grant the customer-tenant deployment service principal `Contributor` and
`Role Based Access Control Administrator` at the customer subscription (or
equivalent scopes covering the resources being deployed). Bicep uses the
deployment service principal's role-assignment permission to grant the workflow
identity `Search Service Contributor` on the newly created TST Search service
when public network access is enabled. Any conditions on the RBAC Administrator
assignment must allow this role assignment. Protect the
`customer-foundation-apply` GitHub Environment and require approval from the
customer deployment reviewers.

## Customer catalog parameters

Add an enabled customer record to [`config/customers.json`](../../config/customers.json)
once the tenant identity and permissions are ready. For each environment,
provide the subscription ID, location, region code, and foundation parameters.
The resolver requires:

| Foundation parameter | Value |
| --- | --- |
| `sqlEntraAdministratorLogin` | Customer-approved Entra administrator login name. |
| `sqlEntraAdministratorObjectId` | Tenant-local object ID of that administrator. |
| `sqlEntraAdministratorTenantId` | Must match the customer's tenant ID. |
| `sqlEntraOnlyAuthentication` | Boolean; normally `true`. |
| `storageContainerNames` | Array of approved blob container names. |
| `aiDeployments` | Approved model deployment configurations and capacities. |
| `restoreAiServices` | Optional boolean; set to `true` only when restoring a recoverable soft-deleted Azure AI Services account. Defaults to `false` for normal creation. |
| `additionalTags` | Customer and environment metadata for Azure resource tags. |
| `publicNetworkAccess` | `Enabled` or `Disabled`, consistent with the network design. |
| `storageNetworkDefaultAction` | `Allow` or `Deny`, consistent with the Storage network design. |

`enableSearchService` is optional and defaults to `true`.
`sqlEntraAdministratorPrincipalType` defaults to `User`; set it to
`ServicePrincipal` when the selected SQL administrator is a service principal.
Keep credentials, API keys, access tokens, and connection strings out of the
catalog and Bicep parameters.

The foundation does not create a virtual network, private endpoints, or
private DNS zones. Provide those through the customer's network design where
required. Choose `publicNetworkAccess` and the Storage network action to match
that design.

## Dispatch the workflow

1. Review the catalog entry, IDs, resource values, and model quota. The
   workflow renders a temporary `.bicepparam` file; do not commit a
   customer-specific local parameter file.
2. Select **Customer foundation** in GitHub Actions, choose an allowed branch,
   and enter the catalog `customer_id` and environment (`tst`, `acc`, or
   `prod`). The workflow rejects tag refs.
3. Review the subscription-scoped what-if output.
4. Approve the `customer-foundation-apply` Environment when the resource
   changes are authorized.
5. Check the SQL server and database, Storage account, Search service, AI
   resources, and Document Intelligence resource in the generated foundation
   resource group.

## Resource values

- **Storage:** The account name and Blob endpoint are deployment outputs.
  Container names come from `storageContainerNames`. The template currently
  enables account-key access; resource keys are not deployment outputs.
- **SQL:** The server FQDN and database name are deployment outputs. The
  configured Entra administrator appears under the SQL server's **Microsoft
  Entra ID** settings. Entra-only authentication is enabled by default; the
  deployment does not create a SQL password or application database user.
  The standalone foundation workflow creates the server and database without
  applying migrations. Use the combined workflow for SQL migrations and
  Stabu reference-data import.
- **Azure AI Search:** The service is created when `enableSearchService` is
  true. Bicep configures API-key or Entra authentication, enables the service's
  system-assigned identity. For TST with public network access enabled, Bicep
  grants the workflow identity Search Service Contributor. After Bicep
  succeeds, the GitHub Actions runner uses its Entra token to apply the
  Projects and SharePoint indexes, SQL data source, embedding skillset, and a
  disabled SQL indexer. The deployment returns the endpoint and service name,
  but not service keys.
- **Azure AI Services:** The deployment returns the account endpoint and
  configured model deployment names. It does not return resource keys.
- **Document Intelligence:** The deployment returns the endpoint, not resource
  keys.

## Azure AI Search TST setup

The customer-foundation workflow applies Search data-plane configuration after
the Bicep deployment only when the environment is `tst`, Search is enabled,
and `publicNetworkAccess` is `Enabled`. The runner calls the Search REST API
using the same customer deployment identity after Bicep grants it Search
Service Contributor. ACC and PROD Search objects are deferred until the
deployment path can reach their private endpoints. The SharePoint index is
only a schema; no SharePoint data source, skillset, or indexer is defined.

The SQL data source uses the Search service's system-assigned identity and the
database resource ID. After the SQL baseline migration creates
`dbo.vw_projects`, a customer SQL administrator must run
[`search/grant-search-view-access.sql`](../../infra/customer-foundation/search/grant-search-view-access.sql)
in that database. Replace `__SEARCH_SERVICE_NAME__` with the deployed Search
service name. This creates the external database user and grants it `SELECT`
on the view. SQL Entra-only authentication remains enabled by default.

The workflow creates the embedding skillset with the explicit
`__ENTER_IN_AZURE_PORTAL__` placeholder as its API key, and the indexer is
created disabled. Before enabling the indexer:

1. Open the Search service in Azure Portal, open `sql-vector-skillset`, and
   replace the placeholder API key with the Azure OpenAI key for the configured
   embedding deployment. Do not put this key in repository files, Bicep
   parameters, outputs, or deployment logs.
2. Complete the SQL view grant above.
3. Open `sql-<customerCode>-indexer`, enable it, and run it.

On later workflow runs, indexes and the SQL data source are updated. An
existing skillset or indexer is left as-is, preserving the portal-entered key
and the indexer's enabled state. Make later changes to those two objects in the
portal. The first apply creates the indexer disabled, so it cannot run before
the API key and SQL permission are ready. The workflow retries Search
authorization briefly after the RBAC assignment to allow permission
propagation.
