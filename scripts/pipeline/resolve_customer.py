"""Validate the non-secret customer catalog and resolve a deployment."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_FOUNDATION_PARAMETERS = frozenset({
    "sqlEntraAdministratorLogin",
    "sqlEntraAdministratorObjectId",
    "sqlEntraAdministratorPrincipalType",
    "sqlEntraAdministratorTenantId",
    "sqlEntraOnlyAuthentication",
    "storageContainerNames",
    "aiDeployments",
    "additionalTags",
    "keyVaultEnablePurgeProtection",
    "keyVaultSoftDeleteRetentionInDays",
    "publicNetworkAccess",
    "storageNetworkDefaultAction",
    "keyVaultNetworkDefaultAction",
    "runtimeAccessPrincipalId",
    "enableSameTenantRuntimeKeyVaultRoleAssignment",
})
REQUIRED_RUNTIME_PARAMETERS = frozenset({
    "vnetAddressPrefix",
    "publicNetworkAccess",
    "zoneRedundant",
    "functionHostStorageNetworkDefaultAction",
    "functionPlanSkuName",
    "functionPlanSkuTier",
    "functionPlanCapacity",
    "functionWorkerRuntime",
    "functionWorkerRuntimeVersion",
    "functionConfiguration",
    "containerRegistryReference",
    "containerImage",
    "keyVaultConfiguration",
    "enablePlatformKeyVaultRoleAssignment",
    "additionalTags",
})
REQUIRED_FOUNDATION_BOOLEAN_PARAMETERS = frozenset({
    "sqlEntraOnlyAuthentication",
    "keyVaultEnablePurgeProtection",
    "enableSameTenantRuntimeKeyVaultRoleAssignment",
})
REQUIRED_RUNTIME_BOOLEAN_PARAMETERS = frozenset({
    "zoneRedundant",
    "enablePlatformKeyVaultRoleAssignment",
})
REQUIRED_KEY_VAULT_BOOLEAN_PARAMETERS = frozenset({
    "enabled",
    "requireKeyVault",
})
AZURE_SAFE_CATALOG_VALUE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def _uuid(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a UUID string")
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ValueError(f"{field} must be a UUID string") from None
    return value


def _azure_safe_catalog_value(value: Any, field: str) -> str:
    if not isinstance(value, str) or AZURE_SAFE_CATALOG_VALUE.fullmatch(value) is None:
        raise ValueError(f"{field} must use a lowercase Azure-safe name")
    return value


def release_version_from_ref(ref_type: str, ref_name: str) -> str:
    if ref_type != "tag" or not isinstance(ref_name, str) or not ref_name.startswith("v") or len(ref_name) == 1:
        raise ValueError("release_version requires a Git tag whose name starts with v")
    return ref_name[1:]


def _require_parameter_keys(parameters: dict, required: frozenset[str], name: str) -> None:
    missing = sorted(required - parameters.keys())
    if missing:
        raise ValueError(f"{name} missing required keys: {', '.join(missing)}")


def _require_boolean_parameters(
    parameters: dict, required: frozenset[str], name: str
) -> None:
    for field in sorted(required):
        if field not in parameters:
            raise ValueError(f"{name} missing required boolean key: {field}")
        if type(parameters[field]) is not bool:
            raise ValueError(f"{name}.{field} must be a JSON boolean")


@dataclass(frozen=True)
class ResolvedDeployment:
    customer_id: str
    environment: str
    tenant_id: str
    subscription_id: str
    location: str
    region_code: str
    release_version: str
    migration_principal_object_id: str
    migration_application_client_id: str
    foundation_parameters: dict[str, object]
    runtime_parameters: dict[str, object]

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "customerId": self.customer_id,
            "environment": self.environment,
            "customerTenantId": self.tenant_id,
            "subscriptionId": self.subscription_id,
            "location": self.location,
            "regionCode": self.region_code,
            "releaseVersion": self.release_version,
            "migration": {
                "principalObjectId": self.migration_principal_object_id,
                "applicationClientId": self.migration_application_client_id,
            },
            "foundationParameters": copy.deepcopy(self.foundation_parameters),
            "runtimeParameters": copy.deepcopy(self.runtime_parameters),
        }


def resolve_customer(
    catalog: dict,
    customer_id: str,
    environment: str,
    ref_type: str,
    ref_name: str,
) -> ResolvedDeployment:
    release_version = release_version_from_ref(ref_type, ref_name)
    customers = catalog.get("customers") if isinstance(catalog, dict) else None
    if not isinstance(customers, list):
        raise ValueError("catalog must contain a customers array")

    records = [customer for customer in customers if isinstance(customer, dict) and customer.get("id") == customer_id]
    if len(records) != 1:
        raise ValueError(f"catalog must contain exactly one record for customer {customer_id!r}")
    customer = records[0]
    if customer.get("enabled") is not True:
        raise ValueError(f"customer {customer_id!r} is disabled")

    tenant_id = _uuid(customer.get("tenantId"), "customer tenantId")
    migration = customer.get("migration")
    if not isinstance(migration, dict):
        raise ValueError("customer migration identity is required")
    principal_id = _uuid(migration.get("principalObjectId"), "migration principalObjectId")
    client_id = _uuid(migration.get("applicationClientId"), "migration applicationClientId")

    environments = customer.get("environments")
    if not isinstance(environments, dict) or environment not in environments:
        raise ValueError(f"unknown environment {environment!r} for customer {customer_id!r}")
    selected = environments[environment]
    if not isinstance(selected, dict):
        raise ValueError("selected environment must be an object")
    subscription_id = _uuid(selected.get("subscriptionId"), "environment subscriptionId")
    location = _azure_safe_catalog_value(selected.get("location"), "environment location")
    region_code = _azure_safe_catalog_value(selected.get("regionCode"), "environment regionCode")

    foundation = selected.get("foundationParameters")
    runtime = selected.get("runtimeParameters")
    if not isinstance(foundation, dict) or not isinstance(runtime, dict):
        raise ValueError("foundationParameters and runtimeParameters are required objects")
    _require_parameter_keys(foundation, REQUIRED_FOUNDATION_PARAMETERS, "foundationParameters")
    _require_parameter_keys(runtime, REQUIRED_RUNTIME_PARAMETERS, "runtimeParameters")
    _require_boolean_parameters(
        foundation, REQUIRED_FOUNDATION_BOOLEAN_PARAMETERS, "foundationParameters"
    )
    _require_boolean_parameters(
        runtime, REQUIRED_RUNTIME_BOOLEAN_PARAMETERS, "runtimeParameters"
    )
    key_vault = runtime.get("keyVaultConfiguration")
    if not isinstance(key_vault, dict):
        raise ValueError("runtimeParameters.keyVaultConfiguration must be an object")
    _require_boolean_parameters(
        key_vault,
        REQUIRED_KEY_VAULT_BOOLEAN_PARAMETERS,
        "runtimeParameters.keyVaultConfiguration",
    )
    foundation = copy.deepcopy(foundation)
    runtime = copy.deepcopy(runtime)
    if foundation.get("sqlEntraAdministratorTenantId") != tenant_id:
        raise ValueError("sqlEntraAdministratorTenantId must equal customer tenantId")
    _uuid(
        foundation.get("sqlEntraAdministratorObjectId"),
        "foundationParameters.sqlEntraAdministratorObjectId",
    )

    foundation.update({
        "customerCode": customer_id,
        "environment": environment,
        "location": location,
        "regionCode": region_code,
        "customerTenantId": tenant_id,
    })
    runtime.update({
        "customerCode": customer_id,
        "environment": environment,
        "location": location,
        "regionCode": region_code,
        "functionConfiguration": {
            **runtime.get("functionConfiguration", {}),
            "customerTenantId": tenant_id,
        },
    })
    return ResolvedDeployment(
        customer_id, environment, tenant_id, subscription_id, location, region_code,
        release_version, principal_id, client_id, foundation, runtime,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--ref-type", required=True)
    parser.add_argument("--ref-name", required=True)
    args = parser.parse_args()
    try:
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        resolved = resolve_customer(catalog, args.customer_id, args.environment, args.ref_type, args.ref_name)
        print(json.dumps(resolved.to_safe_dict(), sort_keys=True))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"resolve_customer: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
