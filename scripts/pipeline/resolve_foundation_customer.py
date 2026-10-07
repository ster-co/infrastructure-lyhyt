"""Resolve only the customer-foundation and SQL workflow configuration."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

from scripts.sql.migration_common import latest_manifest_release_version


_SAFE_NAME = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
_CUSTOMER_CODE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,10}[a-z0-9])")
_REQUIRED_FOUNDATION_PARAMETERS = frozenset(
    {
        "sqlEntraAdministratorLogin",
        "sqlEntraAdministratorObjectId",
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
    }
)


def _uuid(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a UUID string")
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ValueError(f"{field} must be a UUID string") from None
    return value


def _safe_name(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SAFE_NAME.fullmatch(value) is None:
        raise ValueError(f"{field} must use a lowercase Azure-safe name")
    return value


def _runner_label(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 100
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise ValueError("automation.customerSqlRunnerLabel must be a non-empty runner label")
    return value


def _selected_customer(catalog: Any, customer_id: str) -> dict[str, Any]:
    customers = catalog.get("customers") if isinstance(catalog, dict) else None
    if not isinstance(customers, list):
        raise ValueError("catalog must contain a customers array")
    matches = [
        customer
        for customer in customers
        if isinstance(customer, dict) and customer.get("id") == customer_id
    ]
    if len(matches) != 1:
        raise ValueError(
            f"catalog must contain exactly one record for customer {customer_id!r}"
        )
    customer = matches[0]
    if customer.get("enabled") is not True:
        raise ValueError(f"customer {customer_id!r} is disabled")
    return customer


def _validate_foundation_parameters(
    parameters: Any,
    customer_tenant_id: str,
) -> dict[str, Any]:
    if not isinstance(parameters, dict):
        raise ValueError("foundationParameters must be an object")
    missing = sorted(_REQUIRED_FOUNDATION_PARAMETERS - parameters.keys())
    if missing:
        raise ValueError("foundationParameters missing required keys: " + ", ".join(missing))

    for field in ("sqlEntraOnlyAuthentication", "keyVaultEnablePurgeProtection"):
        if type(parameters[field]) is not bool:
            raise ValueError(f"foundationParameters.{field} must be a JSON boolean")

    if not isinstance(parameters["sqlEntraAdministratorLogin"], str) or not parameters[
        "sqlEntraAdministratorLogin"
    ].strip():
        raise ValueError("foundationParameters.sqlEntraAdministratorLogin must be non-empty")
    admin_tenant = _uuid(
        parameters["sqlEntraAdministratorTenantId"],
        "foundationParameters.sqlEntraAdministratorTenantId",
    )
    if admin_tenant != customer_tenant_id:
        raise ValueError("sqlEntraAdministratorTenantId must equal customer tenantId")
    _uuid(
        parameters["sqlEntraAdministratorObjectId"],
        "foundationParameters.sqlEntraAdministratorObjectId",
    )

    containers = parameters["storageContainerNames"]
    if not isinstance(containers, list) or any(
        not isinstance(name, str) or not name for name in containers
    ):
        raise ValueError("foundationParameters.storageContainerNames must be an array of names")
    deployments = parameters["aiDeployments"]
    if not isinstance(deployments, list) or any(not isinstance(item, dict) for item in deployments):
        raise ValueError("foundationParameters.aiDeployments must be an array of objects")
    if not isinstance(parameters["additionalTags"], dict):
        raise ValueError("foundationParameters.additionalTags must be an object")
    retention = parameters["keyVaultSoftDeleteRetentionInDays"]
    if type(retention) is not int or not 7 <= retention <= 90:
        raise ValueError(
            "foundationParameters.keyVaultSoftDeleteRetentionInDays must be between 7 and 90"
        )
    if parameters["publicNetworkAccess"] not in ("Enabled", "Disabled"):
        raise ValueError("foundationParameters.publicNetworkAccess must be Enabled or Disabled")
    for field in ("storageNetworkDefaultAction", "keyVaultNetworkDefaultAction"):
        if parameters[field] not in ("Allow", "Deny"):
            raise ValueError(f"foundationParameters.{field} must be Allow or Deny")
    return parameters


def resolve_foundation_customer(
    catalog: dict[str, Any],
    customer_id: str,
    environment: str,
    ref_type: str,
    manifest_path: Path,
) -> dict[str, Any]:
    """Return only values needed to deploy customer foundation and SQL."""

    if ref_type != "branch":
        raise ValueError("customer foundation workflow must be run from a branch")
    release_version = latest_manifest_release_version(manifest_path)
    if not isinstance(customer_id, str) or _CUSTOMER_CODE.fullmatch(customer_id) is None:
        raise ValueError("customer_id must be a lowercase customer code of 2 to 12 characters")
    if environment not in ("tst", "acc", "prod"):
        raise ValueError("environment must be one of: tst, acc, prod")
    customer = _selected_customer(catalog, customer_id)
    customer_tenant_id = _uuid(customer.get("tenantId"), "customer tenantId")

    migration = customer.get("migration")
    if not isinstance(migration, dict):
        raise ValueError("customer migration identity is required")
    principal_object_id = _uuid(
        migration.get("principalObjectId"), "migration.principalObjectId"
    )
    application_client_id = _uuid(
        migration.get("applicationClientId"), "migration.applicationClientId"
    )

    automation = customer.get("automation")
    if not isinstance(automation, dict):
        raise ValueError("customer automation configuration is required")
    sql_runner_label = _runner_label(automation.get("customerSqlRunnerLabel"))

    environments = customer.get("environments")
    if not isinstance(environments, dict) or environment not in environments:
        raise ValueError(f"unknown environment {environment!r} for customer {customer_id!r}")
    selected = environments[environment]
    if not isinstance(selected, dict):
        raise ValueError("selected environment must be an object")
    subscription_id = _uuid(selected.get("subscriptionId"), "environment subscriptionId")
    location = _safe_name(selected.get("location"), "environment location")
    region_code = _safe_name(selected.get("regionCode"), "environment regionCode")

    foundation = _validate_foundation_parameters(
        selected.get("foundationParameters"), customer_tenant_id
    )
    foundation = dict(foundation)
    foundation.update(
        {
            "customerCode": customer_id,
            "environment": environment,
            "location": location,
            "regionCode": region_code,
            "customerTenantId": customer_tenant_id,
            "runtimeAccessPrincipalId": "",
            "enableSameTenantRuntimeKeyVaultRoleAssignment": False,
        }
    )

    return {
        "customerId": customer_id,
        "environment": environment,
        "customerTenantId": customer_tenant_id,
        "subscriptionId": subscription_id,
        "location": location,
        "regionCode": region_code,
        "releaseVersion": release_version,
        "migration": {
            "principalObjectId": principal_object_id,
            "applicationClientId": application_client_id,
        },
        "automation": {"customerSqlRunnerLabel": sql_runner_label},
        "foundationParameters": foundation,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--ref-type", required=True)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        resolved = resolve_foundation_customer(
            catalog,
            args.customer_id,
            args.environment,
            args.ref_type,
            args.manifest,
        )
        print(json.dumps(resolved, sort_keys=True))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"resolve_foundation_customer: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
