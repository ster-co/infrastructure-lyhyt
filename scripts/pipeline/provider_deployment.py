"""Strict helpers shared by customer lifecycle provider-stage jobs."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence
from typing import Any


class ProviderDeploymentError(ValueError):
    """Raised for a misdirected deployment or incomplete provider readiness."""


_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_GENERATED_SECRET_NAMES = {"document-parser-code", "extraction-code"}


def validate_target(
    actual_tenant_id: str,
    actual_subscription_id: str,
    expected_tenant_id: str,
    expected_subscription_id: str,
) -> None:
    """Require Azure CLI to be in the exact expected tenant and subscription."""
    for name, value in (
        ("actual tenant", actual_tenant_id),
        ("actual subscription", actual_subscription_id),
        ("expected tenant", expected_tenant_id),
        ("expected subscription", expected_subscription_id),
    ):
        try:
            uuid.UUID(value)
        except (ValueError, TypeError, AttributeError):
            raise ProviderDeploymentError(f"{name} must be a UUID") from None
    if actual_tenant_id.casefold() != expected_tenant_id.casefold():
        raise ProviderDeploymentError("Azure CLI tenant does not match the resolved deployment target")
    if actual_subscription_id.casefold() != expected_subscription_id.casefold():
        raise ProviderDeploymentError("Azure CLI subscription does not match the resolved deployment target")


def validate_required_secret_names(
    required_names: Sequence[str],
    available_names: Sequence[str],
    *,
    allow_generated_missing: bool = True,
) -> list[str]:
    """Return missing names and reject before runtime Bicep if values are unseeded."""
    if (
        not isinstance(required_names, Sequence)
        or isinstance(required_names, (str, bytes))
        or not isinstance(available_names, Sequence)
        or isinstance(available_names, (str, bytes))
    ):
        raise ProviderDeploymentError("Key Vault secret name collections must be string arrays")
    if any(not isinstance(name, str) or not name for name in (*required_names, *available_names)):
        raise ProviderDeploymentError("Key Vault secret names must be non-empty strings")
    required = set(required_names)
    if len(required) != len(required_names):
        raise ProviderDeploymentError("duplicate required Key Vault secret names are not allowed")
    allowed = _GENERATED_SECRET_NAMES if allow_generated_missing else set()
    return sorted(required - set(available_names) - allowed)


def wrap_stamp_parameters(
    stamp_parameter_document: Mapping[str, Any],
    *,
    resource_group_name: str,
    location: str,
    customer_id: str,
) -> dict[str, Any]:
    """Wrap stamp.bicep parameters for its subscription-scope resource-group module."""
    if not isinstance(stamp_parameter_document, Mapping):
        raise ProviderDeploymentError("stamp parameters must be an object")
    parameters = stamp_parameter_document.get("parameters")
    if not isinstance(parameters, Mapping):
        raise ProviderDeploymentError("stamp parameter document is invalid")
    values: dict[str, Any] = {}
    for name, item in parameters.items():
        if not isinstance(item, Mapping) or set(item) != {"value"}:
            raise ProviderDeploymentError(f"stamp parameter {name} is invalid")
        values[name] = item["value"]
    if values.get("customerId") != customer_id:
        raise ProviderDeploymentError("stamp customer id does not match the lifecycle request")
    if not isinstance(resource_group_name, str) or _NAME.fullmatch(resource_group_name) is None:
        raise ProviderDeploymentError("provider resource group name is invalid")
    if not isinstance(location, str) or not location.strip():
        raise ProviderDeploymentError("provider region is missing")
    return {
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {
            "resourceGroupName": {"value": resource_group_name},
            "location": {"value": location},
            "tags": {"value": {"customerId": customer_id, "stampId": customer_id}},
            "stampParameters": {"value": values},
        },
    }
