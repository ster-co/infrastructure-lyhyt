"""Validate the non-secret customer catalog for a runtime-only deployment."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.pipeline.resolve_customer import (
    REQUIRED_RUNTIME_BOOLEAN_PARAMETERS,
    REQUIRED_RUNTIME_PARAMETERS,
    REQUIRED_KEY_VAULT_BOOLEAN_PARAMETERS,
    _azure_safe_catalog_value,
    _require_boolean_parameters,
    _require_parameter_keys,
    _uuid,
    _validate_function_runtime_configuration,
)


@dataclass(frozen=True)
class ResolvedRuntimeDeployment:
    customer_id: str
    tenant_id: str
    subscription_id: str
    location: str
    region_code: str
    lyhyt_azure_client_id: str
    lyhyt_azure_tenant_id: str
    lyhyt_platform_subscription_id: str
    runtime_parameters: dict[str, object]

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "customerId": self.customer_id,
            "customerTenantId": self.tenant_id,
            "subscriptionId": self.subscription_id,
            "location": self.location,
            "regionCode": self.region_code,
            "automation": {
                "lyhytAzureClientId": self.lyhyt_azure_client_id,
                "lyhytAzureTenantId": self.lyhyt_azure_tenant_id,
                "lyhytPlatformSubscriptionId": self.lyhyt_platform_subscription_id,
                "lyhytRuntimeSubscriptionId": self.subscription_id,
            },
            "runtimeParameters": copy.deepcopy(self.runtime_parameters),
        }


def _validate_runtime_parameters(runtime: Any) -> dict[str, object]:
    if not isinstance(runtime, dict):
        raise ValueError("runtimeParameters must be an object")
    _require_parameter_keys(runtime, REQUIRED_RUNTIME_PARAMETERS, "runtimeParameters")
    unexpected_runtime = sorted(set(runtime) - REQUIRED_RUNTIME_PARAMETERS)
    if unexpected_runtime:
        raise ValueError(
            "runtimeParameters contains unexpected keys: "
            + ", ".join(unexpected_runtime)
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
    unexpected_key_vault = sorted(set(key_vault) - REQUIRED_KEY_VAULT_BOOLEAN_PARAMETERS)
    if unexpected_key_vault:
        raise ValueError(
            "runtimeParameters.keyVaultConfiguration contains unexpected keys: "
            + ", ".join(unexpected_key_vault)
        )
    _validate_function_runtime_configuration(runtime.get("functionRuntimeConfiguration"))
    return copy.deepcopy(runtime)


def resolve_runtime_customer(
    catalog: dict, customer_id: str, environment: str
) -> ResolvedRuntimeDeployment:
    customers = catalog.get("customers") if isinstance(catalog, dict) else None
    if not isinstance(customers, list):
        raise ValueError("catalog must contain a customers array")

    records = [
        customer
        for customer in customers
        if isinstance(customer, dict) and customer.get("id") == customer_id
    ]
    if len(records) != 1:
        raise ValueError(f"catalog must contain exactly one record for customer {customer_id!r}")
    customer = records[0]
    if customer.get("enabled") is not True:
        raise ValueError(f"customer {customer_id!r} is disabled")

    tenant_id = _uuid(customer.get("tenantId"), "customer tenantId")
    automation = customer.get("automation")
    if not isinstance(automation, dict):
        raise ValueError("customer automation configuration is required")
    lyhyt_azure_client_id = _uuid(
        automation.get("lyhytAzureClientId"), "automation.lyhytAzureClientId"
    )
    lyhyt_azure_tenant_id = _uuid(
        automation.get("lyhytAzureTenantId"), "automation.lyhytAzureTenantId"
    )
    lyhyt_platform_subscription_id = _uuid(
        automation.get("lyhytPlatformSubscriptionId"),
        "automation.lyhytPlatformSubscriptionId",
    )
    subscription_id = _uuid(
        automation.get("lyhytRuntimeSubscriptionId"),
        "automation.lyhytRuntimeSubscriptionId",
    )

    environments = customer.get("environments")
    if not isinstance(environments, dict) or environment not in environments:
        raise ValueError(f"unknown environment {environment!r} for customer {customer_id!r}")
    selected = environments[environment]
    if not isinstance(selected, dict):
        raise ValueError("selected environment must be an object")
    location = _azure_safe_catalog_value(selected.get("location"), "environment location")
    region_code = _azure_safe_catalog_value(selected.get("regionCode"), "environment regionCode")
    runtime = _validate_runtime_parameters(selected.get("runtimeParameters"))
    runtime.update({
        "customerCode": customer_id,
        "environment": environment,
        "location": location,
        "regionCode": region_code,
    })
    return ResolvedRuntimeDeployment(
        customer_id,
        tenant_id,
        subscription_id,
        location,
        region_code,
        lyhyt_azure_client_id,
        lyhyt_azure_tenant_id,
        lyhyt_platform_subscription_id,
        runtime,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--environment", required=True)
    args = parser.parse_args()
    try:
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        resolved = resolve_runtime_customer(catalog, args.customer_id, args.environment)
        print(json.dumps(resolved.to_safe_dict(), sort_keys=True))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"resolve_runtime_customer: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
