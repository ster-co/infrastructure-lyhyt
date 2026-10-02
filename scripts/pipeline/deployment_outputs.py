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
_OPTIONAL_FOUNDATION_OUTPUT_NAMES = (
    "storageAccountName",
    "blobEndpoint",
    "searchServiceName",
    "documentIntelligenceEndpoint",
    "gpt5DeploymentName",
    "gpt54DeploymentName",
    "gpt5MiniDeploymentName",
    "textEmbedding3LargeDeploymentName",
)
_PLATFORM_OUTPUT_NAMES = (
    "containerRegistryName",
    "containerRegistryLoginServer",
    "containerRegistryId",
    "platformKeyVaultResourceId",
    "platformKeyVaultName",
    "platformKeyVaultUri",
)
_RUNTIME_OUTPUT_NAMES = (
    "runtimeKeyVaultResourceId",
    "runtimeKeyVaultName",
    "runtimeKeyVaultUri",
    "identityClientId",
    "identityPrincipalId",
    "documentParserIdentityClientId",
    "documentParserIdentityPrincipalId",
    "mailboxSyncIdentityClientId",
    "mailboxSyncIdentityPrincipalId",
    "sdbIdentityClientId",
    "sdbIdentityPrincipalId",
    "documentParserFunctionAppHostname",
    "mailboxSyncFunctionAppHostname",
    "sdbFunctionAppHostname",
    "functionHostStorageAccountName",
)
_REQUIRED_RUNTIME_OUTPUT_NAMES = _RUNTIME_OUTPUT_NAMES[:11]
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
    storage_account_name: str = ""
    blob_endpoint: str = ""
    search_service_name: str = ""
    document_intelligence_endpoint: str = ""
    gpt5_deployment_name: str = ""
    gpt54_deployment_name: str = ""
    gpt5_mini_deployment_name: str = ""
    text_embedding3_large_deployment_name: str = ""

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
            "storageAccountName": self.storage_account_name,
            "blobEndpoint": self.blob_endpoint,
            "searchServiceName": self.search_service_name,
            "documentIntelligenceEndpoint": self.document_intelligence_endpoint,
            "gpt5DeploymentName": self.gpt5_deployment_name,
            "gpt54DeploymentName": self.gpt54_deployment_name,
            "gpt5MiniDeploymentName": self.gpt5_mini_deployment_name,
            "textEmbedding3LargeDeploymentName": self.text_embedding3_large_deployment_name,
        }


def _optional_output_value(raw_outputs: dict[str, object], name: str) -> str:
    output = raw_outputs.get(name)
    if output is None:
        return ""
    if not isinstance(output, dict) or not isinstance(output.get("value"), str):
        raise ValueError(f"foundation output {name} must contain a string value")
    return output["value"]


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
        storage_account_name=_optional_output_value(raw_outputs, "storageAccountName"),
        blob_endpoint=_optional_output_value(raw_outputs, "blobEndpoint"),
        search_service_name=_optional_output_value(raw_outputs, "searchServiceName"),
        document_intelligence_endpoint=_optional_output_value(
            raw_outputs, "documentIntelligenceEndpoint"
        ),
        gpt5_deployment_name=_optional_output_value(raw_outputs, "gpt5DeploymentName"),
        gpt54_deployment_name=_optional_output_value(raw_outputs, "gpt54DeploymentName"),
        gpt5_mini_deployment_name=_optional_output_value(raw_outputs, "gpt5MiniDeploymentName"),
        text_embedding3_large_deployment_name=_optional_output_value(
            raw_outputs, "textEmbedding3LargeDeploymentName"
        ),
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


@dataclass(frozen=True)
class RuntimeOutputs:
    runtime_key_vault_resource_id: str
    runtime_key_vault_name: str
    runtime_key_vault_uri: str
    identity_client_id: str
    identity_principal_id: str
    document_parser_identity_client_id: str
    document_parser_identity_principal_id: str
    mailbox_sync_identity_client_id: str
    mailbox_sync_identity_principal_id: str
    sdb_identity_client_id: str
    sdb_identity_principal_id: str
    document_parser_function_app_hostname: str
    mailbox_sync_function_app_hostname: str
    sdb_function_app_hostname: str
    function_host_storage_account_name: str

    def to_safe_dict(self) -> dict[str, str]:
        return {
            "runtimeKeyVaultResourceId": self.runtime_key_vault_resource_id,
            "runtimeKeyVaultName": self.runtime_key_vault_name,
            "runtimeKeyVaultUri": self.runtime_key_vault_uri,
            "identityClientId": self.identity_client_id,
            "identityPrincipalId": self.identity_principal_id,
            "documentParserIdentityClientId": self.document_parser_identity_client_id,
            "documentParserIdentityPrincipalId": self.document_parser_identity_principal_id,
            "mailboxSyncIdentityClientId": self.mailbox_sync_identity_client_id,
            "mailboxSyncIdentityPrincipalId": self.mailbox_sync_identity_principal_id,
            "sdbIdentityClientId": self.sdb_identity_client_id,
            "sdbIdentityPrincipalId": self.sdb_identity_principal_id,
            "documentParserFunctionAppHostname": self.document_parser_function_app_hostname,
            "mailboxSyncFunctionAppHostname": self.mailbox_sync_function_app_hostname,
            "sdbFunctionAppHostname": self.sdb_function_app_hostname,
            "functionHostStorageAccountName": self.function_host_storage_account_name,
        }


def extract_runtime_outputs(raw_outputs: dict[str, object]) -> RuntimeOutputs:
    if not isinstance(raw_outputs, dict):
        raise ValueError("deployment outputs must be an object")
    values: dict[str, str] = {}
    for name in _REQUIRED_RUNTIME_OUTPUT_NAMES:
        output = raw_outputs.get(name)
        if not isinstance(output, dict) or not isinstance(output.get("value"), str):
            raise ValueError(f"runtime output {name} must contain a string value")
        if not output["value"]:
            raise ValueError(f"runtime output {name} must not be empty")
        values[name] = output["value"]
    for name in _RUNTIME_OUTPUT_NAMES[len(_REQUIRED_RUNTIME_OUTPUT_NAMES):]:
        output = raw_outputs.get(name)
        if output is None:
            values[name] = ""
        elif not isinstance(output, dict) or not isinstance(output.get("value"), str):
            raise ValueError(f"runtime output {name} must contain a string value")
        else:
            values[name] = output["value"]
    return RuntimeOutputs(
        runtime_key_vault_resource_id=values["runtimeKeyVaultResourceId"],
        runtime_key_vault_name=values["runtimeKeyVaultName"],
        runtime_key_vault_uri=values["runtimeKeyVaultUri"],
        identity_client_id=values["identityClientId"],
        identity_principal_id=values["identityPrincipalId"],
        document_parser_identity_client_id=values["documentParserIdentityClientId"],
        document_parser_identity_principal_id=values["documentParserIdentityPrincipalId"],
        mailbox_sync_identity_client_id=values["mailboxSyncIdentityClientId"],
        mailbox_sync_identity_principal_id=values["mailboxSyncIdentityPrincipalId"],
        sdb_identity_client_id=values["sdbIdentityClientId"],
        sdb_identity_principal_id=values["sdbIdentityPrincipalId"],
        document_parser_function_app_hostname=values["documentParserFunctionAppHostname"],
        mailbox_sync_function_app_hostname=values["mailboxSyncFunctionAppHostname"],
        sdb_function_app_hostname=values["sdbFunctionAppHostname"],
        function_host_storage_account_name=values["functionHostStorageAccountName"],
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
