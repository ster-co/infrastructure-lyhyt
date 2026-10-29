"""Resolve the configuration needed to deploy the customer foundation."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

_SAFE_NAME = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
_CUSTOMER_CODE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,10}[a-z0-9])")
_REQUIRED_FOUNDATION_PARAMETERS = frozenset(
    {
        "customerResourceGroupName",
        "resourceNames",
        "sqlEntraAdministratorLogin",
        "sqlEntraAdministratorObjectId",
        "sqlEntraAdministratorTenantId",
        "sqlEntraOnlyAuthentication",
        "serviceLocations",
        "storageContainerNames",
        "aiDeployments",
        "aiSkuName",
        "documentIntelligenceSkuName",
        "searchSkuName",
        "searchReplicaCount",
        "searchPartitionCount",
        "searchSemanticSearch",
        "storageSkuName",
        "sqlDatabaseSku",
        "sqlDatabaseBackupRedundancy",
        "sqlDatabaseZoneRedundant",
        "sqlDatabaseReadScale",
        "networkSettings",
        "additionalTags",
        "publicNetworkAccess",
        "storageNetworkDefaultAction",
    }
)
_EXPECTED_AI_DEPLOYMENTS = (
    ("gpt-5", "gpt-5"),
    ("gpt-5.4", "gpt-5.4"),
    ("gpt-4.1-mini", "gpt-4.1-mini"),
    ("gpt-4.1-nano", "gpt-4.1-nano"),
    ("text-embedding-3-large", "text-embedding-3-large"),
)
_SERVICE_LOCATIONS = ("ai", "documentIntelligence", "search", "sql", "storage")
_NETWORK_SERVICES = ("ai", "documentIntelligence", "sql", "search", "storage")


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

    for field in ("sqlEntraOnlyAuthentication",):
        if type(parameters[field]) is not bool:
            raise ValueError(f"foundationParameters.{field} must be a JSON boolean")
    if "enableSearchService" in parameters and type(parameters["enableSearchService"]) is not bool:
        raise ValueError("foundationParameters.enableSearchService must be a JSON boolean")

    if not isinstance(parameters["sqlEntraAdministratorLogin"], str) or not parameters[
        "sqlEntraAdministratorLogin"
    ].strip():
        raise ValueError("foundationParameters.sqlEntraAdministratorLogin must be non-empty")
    _safe_name(
        parameters["customerResourceGroupName"],
        "foundationParameters.customerResourceGroupName",
    )
    resource_names = parameters["resourceNames"]
    required_resource_names = {
        "aiServices",
        "aiProject",
        "documentIntelligence",
        "search",
        "sqlServer",
        "sqlDatabase",
        "storageAccount",
    }
    if not isinstance(resource_names, dict) or set(resource_names) != required_resource_names:
        raise ValueError("foundationParameters.resourceNames must contain the seven named foundation resources")
    for key, value in resource_names.items():
        if key == "storageAccount":
            if not isinstance(value, str) or re.fullmatch(r"[a-z0-9]{3,24}", value) is None:
                raise ValueError("foundationParameters.resourceNames.storageAccount must be 3-24 lowercase alphanumeric characters")
        else:
            _safe_name(value, f"foundationParameters.resourceNames.{key}")
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
    if len(deployments) != len(_EXPECTED_AI_DEPLOYMENTS):
        raise ValueError(
            "foundationParameters.aiDeployments must contain exactly the five deployments "
            "required by the Bicep output aliases"
        )
    for index, (expected_name, expected_model) in enumerate(_EXPECTED_AI_DEPLOYMENTS):
        deployment = deployments[index]
        if deployment.get("name") != expected_name:
            raise ValueError(
                f"foundationParameters.aiDeployments[{index}].name must be {expected_name!r} "
                "because main.bicep maps outputs by deployment order"
            )
        if deployment.get("model") != expected_model:
            raise ValueError(
                f"foundationParameters.aiDeployments[{index}].model must be {expected_model!r}"
            )
        if not isinstance(deployment.get("version"), str) or not deployment["version"].strip():
            raise ValueError(f"foundationParameters.aiDeployments[{index}].version must be non-empty")
        if not isinstance(deployment.get("skuName"), str) or not deployment["skuName"].strip():
            raise ValueError(f"foundationParameters.aiDeployments[{index}].skuName must be non-empty")
        if type(deployment.get("capacity")) is not int or deployment["capacity"] < 1:
            raise ValueError(f"foundationParameters.aiDeployments[{index}].capacity must be a positive integer")

    locations = parameters["serviceLocations"]
    if not isinstance(locations, dict):
        raise ValueError("foundationParameters.serviceLocations must be an object")
    missing_locations = sorted(set(_SERVICE_LOCATIONS) - locations.keys())
    if missing_locations:
        raise ValueError("foundationParameters.serviceLocations missing: " + ", ".join(missing_locations))
    for service in _SERVICE_LOCATIONS:
        _safe_name(locations[service], f"foundationParameters.serviceLocations.{service}")

    for field in ("aiSkuName", "documentIntelligenceSkuName", "searchSkuName", "storageSkuName"):
        if not isinstance(parameters[field], str) or not parameters[field].strip():
            raise ValueError(f"foundationParameters.{field} must be non-empty")
    for field in ("searchReplicaCount", "searchPartitionCount"):
        if type(parameters[field]) is not int or parameters[field] < 1:
            raise ValueError(f"foundationParameters.{field} must be a positive integer")
    if parameters["searchSemanticSearch"] not in ("free", "standard"):
        raise ValueError("foundationParameters.searchSemanticSearch must be free or standard")

    sql_sku = parameters["sqlDatabaseSku"]
    if not isinstance(sql_sku, dict):
        raise ValueError("foundationParameters.sqlDatabaseSku must be an object")
    for field in ("name", "tier", "family"):
        if not isinstance(sql_sku.get(field), str) or not sql_sku[field].strip():
            raise ValueError(f"foundationParameters.sqlDatabaseSku.{field} must be non-empty")
    if type(sql_sku.get("capacity")) is not int or sql_sku["capacity"] < 1:
        raise ValueError("foundationParameters.sqlDatabaseSku.capacity must be a positive integer")
    if parameters["sqlDatabaseBackupRedundancy"] not in ("Local", "Zone", "Geo", "GeoZone"):
        raise ValueError("foundationParameters.sqlDatabaseBackupRedundancy is not supported")
    if type(parameters["sqlDatabaseZoneRedundant"]) is not bool:
        raise ValueError("foundationParameters.sqlDatabaseZoneRedundant must be a JSON boolean")
    if parameters["sqlDatabaseReadScale"] not in ("Enabled", "Disabled"):
        raise ValueError("foundationParameters.sqlDatabaseReadScale must be Enabled or Disabled")

    network = parameters["networkSettings"]
    if not isinstance(network, dict):
        raise ValueError("foundationParameters.networkSettings must be an object")
    missing_network = sorted(set(_NETWORK_SERVICES) - network.keys())
    if missing_network:
        raise ValueError("foundationParameters.networkSettings missing: " + ", ".join(missing_network))
    for service in _NETWORK_SERVICES:
        settings = network[service]
        if not isinstance(settings, dict):
            raise ValueError(f"foundationParameters.networkSettings.{service} must be an object")
        if settings.get("publicNetworkAccess") not in ("Enabled", "Disabled"):
            raise ValueError(f"foundationParameters.networkSettings.{service}.publicNetworkAccess must be Enabled or Disabled")
        if service in ("ai", "documentIntelligence", "storage") and settings.get("defaultAction") not in ("Allow", "Deny"):
            raise ValueError(f"foundationParameters.networkSettings.{service}.defaultAction must be Allow or Deny")
    if not isinstance(parameters["additionalTags"], dict):
        raise ValueError("foundationParameters.additionalTags must be an object")
    if parameters["publicNetworkAccess"] not in ("Enabled", "Disabled"):
        raise ValueError("foundationParameters.publicNetworkAccess must be Enabled or Disabled")
    if parameters["storageNetworkDefaultAction"] not in ("Allow", "Deny"):
        raise ValueError("foundationParameters.storageNetworkDefaultAction must be Allow or Deny")
    if parameters["networkSettings"]["storage"]["defaultAction"] != parameters["storageNetworkDefaultAction"]:
        raise ValueError("storageNetworkDefaultAction must match networkSettings.storage.defaultAction")
    return parameters


def resolve_foundation_customer(
    catalog: dict[str, Any],
    customer_id: str,
    environment: str,
    ref_type: str,
) -> dict[str, Any]:
    """Return only values needed to deploy the customer foundation."""

    if ref_type != "branch":
        raise ValueError("customer foundation workflow must be run from a branch")
    if not isinstance(customer_id, str) or _CUSTOMER_CODE.fullmatch(customer_id) is None:
        raise ValueError("customer_id must be a lowercase customer code of 2 to 12 characters")
    if environment not in ("tst", "acc", "prod"):
        raise ValueError("environment must be one of: tst, acc, prod")
    customer = _selected_customer(catalog, customer_id)
    customer_tenant_id = _uuid(customer.get("tenantId"), "customer tenantId")

    migration = customer.get("migration")
    if not isinstance(migration, dict):
        raise ValueError("customer foundation deployment identity is required")
    application_client_id = _uuid(
        migration.get("applicationClientId"), "migration.applicationClientId"
    )
    principal_object_id = _uuid(
        migration.get("principalObjectId"), "migration.principalObjectId"
    )

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
            "searchConfigurationPrincipalObjectId": principal_object_id,
        }
    )

    return {
        "customerId": customer_id,
        "environment": environment,
        "customerTenantId": customer_tenant_id,
        "subscriptionId": subscription_id,
        "location": location,
        "regionCode": region_code,
        "migration": {
            "applicationClientId": application_client_id,
            "principalObjectId": principal_object_id,
        },
        "foundationParameters": foundation,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--ref-type", required=True)
    args = parser.parse_args()
    try:
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        resolved = resolve_foundation_customer(
            catalog,
            args.customer_id,
            args.environment,
            args.ref_type,
        )
        print(json.dumps(resolved, sort_keys=True))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"resolve_foundation_customer: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
