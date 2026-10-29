# Customer onboarding and application releases

Use [Customer lifecycle](../.github/workflows/customer-lifecycle.yml) as the
single entrypoint for new customers and later releases. The infrastructure
catalog owns customer and provider tenant placement, subscription IDs, regions,
resource names, runtime sizing, deployment identity, and the protected GitHub
Environment. The SDB app catalog owns product settings and repository names
under the same `customer_id`; it must not contain Azure deployment targets.

## Reference profiles

`rg-lyhyt-demo` is the configuration reference for customer foundation
resources, and `rg-lyhyt-demo-provider` is the provider stamp topology
reference. The provider-side `rg-lyhyt-demo` is not a deployment target for the
customer foundation. The infrastructure catalog remains authoritative for
tenant placement. The `lyhyt-demo` record is disabled and is retained as a
reference; it is not an onboarding or automatic migration target.

The foundation profile captures AI Services and its Foundry project, the five
model deployments, S0 Document Intelligence, Hyperscale SQL settings, Basic AI
Search, and GRS Storage. It preserves the observed regional split with
per-service regions. Model versions and capacity, SQL SKU and backup settings,
and network settings are parameterized and validated before deployment. The
paused timestamped SQL database is a recovery artifact and is not part of a
standard customer foundation.

The provider profile reproduces the 19-resource sample stamp: three Function
Apps with separate FC1 plans and Application Insights components; an API and
isolated Docling Worker with separate Container Apps environments and Log
Analytics workspaces; provider package Storage; Key Vault; a per-customer
deployment identity and scoped RBAC; and the managed hostname certificate and
binding. API and worker sizing, scaling, ingress, queue settings, and regional
placement are catalog parameters.

## Before onboarding

1. Add matching customer records to `config/customers.json` and the pinned
   SDB release's `deploy/app-customers.json`. Keep the infrastructure record
   disabled until tenant access, catalog values, and prerequisites are ready;
   enable it in the reviewed change that authorizes onboarding.
2. Configure customer-tenant and provider-tenant GitHub OIDC identities. The
   workflow fails closed if the active tenant or subscription differs from the
   catalog. The customer identity needs the roles required by the foundation
   Bicep and Entra SQL migrations. The provider identity needs the reviewed
   resource-group, deployment, and role-assignment rights used by the stamp.
3. Protect the `customer-foundation-apply`, `provider-stamp-apply`, and
   `provider-prerequisites-ready` environments with required reviewers. The
   first two require the matching OIDC environment subject as well as branch
   subjects for preflight jobs. The prerequisites environment is an operator
   checkpoint after the provider Key Vault and Container Apps environment
   exist. Configure the `LYHYT` environment in
   `SDB-Calculation-v2` for the per-customer deployment identity federation.
4. Configure these infrastructure repository secrets:
   `DEPLOYMENT_GITHUB_APP_ID`, `DEPLOYMENT_GITHUB_APP_PRIVATE_KEY`, and
   `CUSTOMER_SCHEMA_BASELINE_VERSION`. The schema baseline may be one migration
   version or a JSON object keyed by customer ID. For onboarding, the workflow
   checks that the selected value names a migration in the pinned SDB release
   before it provisions resources.
5. Configure repository variables `PROVIDER_ACR_NAME`,
   `PROVIDER_ACR_LOGIN_SERVER`, and `PROVIDER_ACR_RESOURCE_GROUP`. Install the
   GitHub App on `infrastructure-lyhyt`, `SDB-Calculation-v2`,
   `Document-parser`, `getmail`, and `Docling-worker`. Grant contents read on
   these repositories, Actions read on infrastructure and component repos for
   the handoff and release assets, and Actions write on SDB to dispatch the
   app-only workflow. Avoid write permissions to repository contents.
6. Configure `PARSER_PACKAGE_TOKEN` as a protected `LYHYT` environment secret
   in SDB. The app workflow uses it only for the extraction Function's remote
   package build and removes it afterward. Add required customer secrets to
   the provider Key Vault at the `provider-prerequisites-ready` checkpoint,
   after the provider foundation creates the vault. Preflight checks secret
   names only; it never reads or logs their values. The two generated Function host-key
   entries are initialized as non-secret placeholders and replaced after the
   Functions are deployed.
7. At the same checkpoint, create a customer DNS CNAME for the configured API
   hostname pointing to the new provider Container Apps environment default
   domain. Onboarding verifies the exact CNAME target before managed
   certificate provisioning. DNS and actual secret values are customer/operator
   prerequisites and are not workflow inputs.
8. Publish the immutable coordinated SDB release tag, such as
   `stamp-v2026.10.29.1-lyhyt`, with its `stamp-release.json` and all pinned
   workload artifacts available to the app workflow.

Never put secret values, SQL tokens, package tokens, or private keys in either
catalog, Bicep parameters, handoff artifacts, workflow inputs, or logs.

## Onboard a customer

Choose `operation: onboard` and the pinned `release_version`. The workflow runs
these stages in order:

1. Validate both catalogs, the release tag, OIDC availability, exact tenant and
   subscription targets, DNS, regional model availability and quota, required
   Key Vault secret names, and the SQL baseline migration.
2. Run customer-foundation Bicep lint/build/what-if. The protected
   `customer-foundation-apply` environment gates the apply in the customer
   tenant.
3. Apply SQL migrations with an Entra access token, then configure the customer
   Search indexes and data objects.
4. Run provider-stamp foundation what-if and gated apply. This creates the
   provider resource group, Key Vault, and customer deployment identity. The
   `provider-prerequisites-ready` environment pauses for operator DNS and secret
   hydration now that the Key Vault and Container Apps environment exist.
5. Check provider DNS and Key Vault prerequisites. Run provider runtime
   what-if and gated apply for Function Apps, Container Apps, monitoring,
   managed certificate, hostname binding, and scoped roles.
6. Verify Key Vault/certificate readiness and publish an allowlisted,
   versioned, non-secret handoff artifact containing only deployment targets,
   safe Bicep outputs, and approved runtime settings.
7. Dispatch the pinned SDB app-only workflow with a least-privilege GitHub App
   token and wait for its result. It deploys Document Parser, extraction, Mail
   Triage, API, and Docling Worker, then verifies Functions, ingress, scaling,
   health, certificate, and deployment identity access.

Each apply has its own protected GitHub Environment. A failed stage can be
rerun after correcting the prerequisite; the deployment names are stable for
the customer and environment.

## Release code to an onboarded customer

Choose `operation: release` and a new pinned release tag. This path reads the
existing customer foundation and provider runtime deployment outputs, validates
both Azure scopes, runs SQL migrations first, assembles the same safe handoff,
and dispatches the app-only workflow. It does not run foundation or runtime
Bicep. If an existing customer's resource names or deployment history do not
match this lifecycle contract, report drift and use a separately reviewed
migration run before enabling normal releases.

The paused timestamped SQL database requires a separate restore operation. It
must not be included in onboarding or regular releases.

## Validation

Run the repository tests and validate workflow YAML before publishing a
release. The onboarding workflow compiles and lints the customer and provider
Bicep templates and parameter files and runs `what-if` before either apply.
The first pilot must additionally verify the deployed customer service types,
five model deployments, SQL and Storage/Search settings, provider 19-resource
topology, role scopes, Key Vault readiness, and all workload health checks.
The current `lyhyt-demo` reference remains disabled; no pilot deployment is run
as part of this code change.
