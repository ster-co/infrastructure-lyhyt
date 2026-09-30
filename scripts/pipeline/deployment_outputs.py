"""Parse and validate outputs from the platform and customer deployments."""

from __future__ import annotations

import re
from dataclasses import dataclass


_OUTPUT_NAMES = (
    "sqlServerFqdn",
    "sqlDatabaseName",
    "sqlServerResourceId",
    "sqlDatabaseResourceId",
    "customerKeyVaultResourceId",
    "customerKeyVaultName",
    "customerKeyVaultUri",
    "searchEndpoint",
    "aiEndpoint",
)
_PLATFORM_OUTPUT_NAMES = (
    "containerRegistryName",
    "containerRegistryLoginServer",
    "containerRegistryId",
    "platformKeyVaultResourceId",
    "platformKeyVaultName",
    "platformKeyVaultUri",
)
_REQUIRED_PLATFORM_OUTPUT_NAMES = (
    "containerRegistryName",
    "containerRegistryLoginServer",
    "containerRegistryId",
)
_RESOURCE_ID = re.compile(
    r"^/subscriptions/([^/]+)/resourceGroups/[^/]+/providers/([^/]+)/.+$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FoundationOutputs:
    sql_server_fqdn: str
    sql_database_name: str
    sql_server_resource_id: str
    sql_database_resource_id: str
    customer_key_vault_resource_id: str
    customer_key_vault_name: str
    customer_key_vault_uri: str
    search_endpoint: str
    ai_endpoint: str

    def to_safe_dict(self) -> dict[str, str]:
        return {
            "sqlServerFqdn": self.sql_server_fqdn,
            "sqlDatabaseName": self.sql_database_name,
            "sqlServerResourceId": self.sql_server_resource_id,
            "sqlDatabaseResourceId": self.sql_database_resource_id,
            "customerKeyVaultResourceId": self.customer_key_vault_resource_id,
            "customerKeyVaultName": self.customer_key_vault_name,
            "customerKeyVaultUri": self.customer_key_vault_uri,
            "searchEndpoint": self.search_endpoint,
            "aiEndpoint": self.ai_endpoint,
        }


def extract_foundation_outputs(raw_outputs: dict[str, object]) -> FoundationOutputs:
    if not isinstance(raw_outputs, dict):
        raise ValueError("deployment outputs must be an object")
    values: dict[str, str] = {}
    for name in _OUTPUT_NAMES:
        output = raw_outputs.get(name)
        if not isinstance(output, dict) or not isinstance(output.get("value"), str):
            raise ValueError(f"foundation output {name} must contain a string value")
        values[name] = output["value"]
    return FoundationOutputs(
        sql_server_fqdn=values["sqlServerFqdn"],
        sql_database_name=values["sqlDatabaseName"],
        sql_server_resource_id=values["sqlServerResourceId"],
        sql_database_resource_id=values["sqlDatabaseResourceId"],
        customer_key_vault_resource_id=values["customerKeyVaultResourceId"],
        customer_key_vault_name=values["customerKeyVaultName"],
        customer_key_vault_uri=values["customerKeyVaultUri"],
        search_endpoint=values["searchEndpoint"],
        ai_endpoint=values["aiEndpoint"],
    )


@dataclass(frozen=True)
class PlatformOutputs:
    container_registry_name: str
    container_registry_login_server: str
    container_registry_id: str
    platform_key_vault_resource_id: str
    platform_key_vault_name: str
    platform_key_vault_uri: str

    def to_safe_dict(self) -> dict[str, str]:
        return {
            "containerRegistryName": self.container_registry_name,
            "containerRegistryLoginServer": self.container_registry_login_server,
            "containerRegistryId": self.container_registry_id,
            "platformKeyVaultResourceId": self.platform_key_vault_resource_id,
            "platformKeyVaultName": self.platform_key_vault_name,
            "platformKeyVaultUri": self.platform_key_vault_uri,
        }


def extract_platform_outputs(raw_outputs: dict[str, object]) -> PlatformOutputs:
    if not isinstance(raw_outputs, dict):
        raise ValueError("deployment outputs must be an object")
    values: dict[str, str] = {}
    for name in _REQUIRED_PLATFORM_OUTPUT_NAMES:
        output = raw_outputs.get(name)
        if not isinstance(output, dict) or not isinstance(output.get("value"), str):
            raise ValueError(f"platform output {name} must contain a string value")
        if not output["value"]:
            raise ValueError(f"platform output {name} must not be empty")
        values[name] = output["value"]
    for name in set(_PLATFORM_OUTPUT_NAMES) - set(_REQUIRED_PLATFORM_OUTPUT_NAMES):
        output = raw_outputs.get(name)
        if output is None:
            values[name] = ""
        elif not isinstance(output, dict) or not isinstance(output.get("value"), str):
            raise ValueError(f"platform output {name} must contain a string value")
        else:
            values[name] = output["value"]
    return PlatformOutputs(
        container_registry_name=values["containerRegistryName"],
        container_registry_login_server=values["containerRegistryLoginServer"],
        container_registry_id=values["containerRegistryId"],
        platform_key_vault_resource_id=values["platformKeyVaultResourceId"],
        platform_key_vault_name=values["platformKeyVaultName"],
        platform_key_vault_uri=values["platformKeyVaultUri"],
    )


def validate_resource_id_subscription(
    resource_id: str, subscription_id: str, expected_provider: str
) -> None:
    if not isinstance(resource_id, str) or not isinstance(subscription_id, str):
        raise ValueError("resource ID and subscription ID must be strings")
    if not isinstance(expected_provider, str) or not expected_provider:
        raise ValueError("expected provider must be a non-empty string")
    match = _RESOURCE_ID.fullmatch(resource_id)
    if not match:
        raise ValueError("invalid Azure resource ID")
    if match.group(1).casefold() != subscription_id.casefold():
        raise ValueError("resource ID belongs to a different subscription")
    if match.group(2).casefold() != expected_provider.casefold():
        raise ValueError("resource ID has an unexpected resource provider")
