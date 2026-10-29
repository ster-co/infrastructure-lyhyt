# Staged customer and provider onboarding

**Date:** 2026-10-29  
**Status:** Approved design; pending written-spec review

## Goal

Make first-time onboarding two independently dispatched stages. The customer
foundation and all customer-side setup complete in Stage 1. Stage 2 starts with
the provider foundation and completes provider runtime deployment and the
pinned application release. Keep releases to already-onboarded customers on the
existing release path.

## Current behavior

`.github/workflows/customer-lifecycle.yml` exposes `onboard` and `release`.
The onboarding operation currently applies the customer foundation, waits for
the customer SQL access checkpoint, runs SQL migrations and Search
configuration, applies provider foundation and runtime, then dispatches the
pinned SDB app deployment. The working tree already contains an uncommitted
`customer-sql-ready` checkpoint in that workflow and matching documentation;
the split preserves that checkpoint.

`.github/workflows/customer-foundation.yml` is already a standalone customer
foundation workflow, but it currently ends after Bicep apply and Search
configuration. It does not run the SQL setup required by the combined
onboarding path.

## Workflow design

### Stage 1: Customer foundation

Extend `.github/workflows/customer-foundation.yml` to accept the pinned SDB
`release_version` in addition to `customer_id` and `environment`. Keep its
customer-only OIDC target resolution, Bicep what-if/apply, and Search
configuration. Move the onboarding SQL migration work from
`customer-lifecycle.yml` into this workflow:

1. Validate the selected release and customer migration baseline before
   provisioning.
2. Apply the customer foundation behind `customer-foundation-apply`.
3. Pause at `customer-sql-ready` until the customer Entra migration principal
   has the documented database access.
4. Run migrations with the pinned SDB release and apply Search configuration.
5. Complete only when all customer-side jobs succeed.

The stage authenticates only to the customer tenant. It does not deploy
provider resources or application code.

### Stage 2: Provider onboarding

Add a manually dispatched provider onboarding workflow. Inputs identify the
customer, environment, pinned release, and successful Stage 1 run ID. Before
any provider apply, verify that the supplied run succeeded in the customer
foundation workflow and that its run title matches the customer, environment,
and release inputs. Re-resolve the authoritative catalogs and read the stable
customer foundation deployment outputs from Azure; do not pass secrets or rely
on cross-run output artifacts.

After the preflight, continue the existing provider-side sequence:

1. Run provider foundation what-if and gated apply at
   `provider-stamp-apply`.
2. Pause at `provider-prerequisites-ready` for DNS and Key Vault hydration.
3. Run provider runtime preflight, what-if, and gated apply.
4. Validate the resulting stamp, publish the allowlisted non-secret handoff,
   and dispatch the pinned SDB app-only onboarding workflow.

The provider workflow does not apply customer Bicep or rerun customer SQL
migrations and Search configuration. A failed or mismatched Stage 1 run blocks
the provider apply.

### Existing-customer releases

Keep `.github/workflows/customer-lifecycle.yml` as the release entrypoint for
customers whose foundations and runtime are already present. Remove the
`onboard` option and onboarding-only jobs from this workflow while preserving
its existing release behavior and cross-tenant target validation.

Use one customer/environment concurrency group across the customer foundation,
provider onboarding, and release workflows so their deployments cannot race.

## Catalogs, identity, and deployment contracts

- `config/customers.json` remains authoritative for customer and provider
  tenants, subscriptions, locations, resource names, and deployment identities.
- The pinned SDB app catalog remains authoritative for workload repositories
  and product settings.
- Customer foundation and SQL jobs continue using the customer Entra identity.
- Provider foundation/runtime jobs continue using the provider identity and
  protected provider environments.
- Stable deployment names and current Bicep templates remain unchanged.
- The Stage 2 handoff uses existing safe deployment outputs; secrets remain in
  their current protected stores and never enter workflow inputs or artifacts.

## Failure handling and operator flow

Operators finish Stage 1 and record its run ID before dispatching Stage 2 with
the same customer, environment, and release. Stage 2 fails before provider
changes if the run is missing, failed, belongs to another workflow, or does not
match those inputs. Stable Azure deployment names and idempotent apply steps
allow a failed stage to be rerun after its prerequisite is corrected.

Update `docs/customer-lifecycle.md` to describe the two dispatches, required
inputs, approval checkpoints, and release-only lifecycle path. Do not change
the SDB release workflow or other sibling repositories as part of this split.

## Validation

Inspect both onboarding workflows' job dependencies, target checks, approval
environments, and handoff boundaries. Validate the workflow YAML and confirm
that the release path no longer dispatches onboarding applies. Do not run an
Azure deployment.
