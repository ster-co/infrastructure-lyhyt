"""Parse and validate outputs from the customer-foundation apply deployment."""

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
