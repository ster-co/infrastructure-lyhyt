"""Validate the SDB application catalog and compose provider stamp inputs.

The application catalog owns code and product settings. Azure target names and
tenant placement come only from the infrastructure customer catalog.
"""

from __future__ import annotations

import copy
import re
import uuid
from collections.abc import Mapping
from typing import Any


class ProviderStampCatalogError(ValueError):
    """Raised when application settings and infrastructure targets do not align."""


_ID = re.compile(r"^[a-z][a-z0-9-]{1,30}[a-z0-9]$")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_VAULT_SECRET = re.compile(r"^[A-Za-z0-9-]{1,127}$")
_TIERS = {"lyhyt", "tst", "acc", "prd"}
_APP_FIELDS = {
    "id",
    "tier",
    "identity",
    "components",
    "data",
    "requiredKeyVaultSecretNames",
}
_APP_DATA_FIELDS = {
    "documentIndex",
    "projectIndex",
    "indexerName",
    "fullModel",
    "fastModel",
    "apiVersion",
    "parserEngine",
    "doclingEngineVersion",
    "doclingJobsQueue",
    "doclingJobsContainer",
    "diCacheContainer",
    "sharepointDomain",
    "sharepointSite",
    "sharepointFolder",
    "offersSubfolder",
    "mailboxes",
    "sharepointDriveId",
}
_FORBIDDEN_APP_TARGET_KEYS = {
    "tenantid",
    "subscriptionid",
    "resourcegroup",
    "resourcegroupname",
    "hostname",
    "endpoint",
    "resourceid",
    "location",
    "deployment",
    "storageaccountname",
    "sqlserver",
    "sqldatabase",
    "searchservice",
    "aiservices",
}


def _uuid(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ProviderStampCatalogError(f"{field} must be a UUID")
    try:
        uuid.UUID(value)
    except ValueError:
        raise ProviderStampCatalogError(f"{field} must be a UUID") from None
    return value


def _target_keys(value: Any, path: str = "app") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            if normalized in _FORBIDDEN_APP_TARGET_KEYS or any(
                part in normalized
                for part in ("subscriptionid", "tenantid", "resourcegroup", "endpoint", "resourceid")
            ):
                raise ProviderStampCatalogError(
                    f"{path}.{key} contains an Azure target; keep targets in infrastructure-lyhyt"
                )
            _target_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _target_keys(child, f"{path}[{index}]")


def validate_app_catalog_record(value: Any) -> dict[str, Any]:
    """Validate one target-free application configuration record."""
    if not isinstance(value, Mapping):
        raise ProviderStampCatalogError("app customer must be an object")
    _target_keys(value)
    if set(value) != _APP_FIELDS:
        missing = sorted(_APP_FIELDS - set(value))
        unknown = sorted(set(value) - _APP_FIELDS)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unknown:
            details.append("unexpected " + ", ".join(map(str, unknown)))
        raise ProviderStampCatalogError("app customer fields are invalid: " + "; ".join(details))

    customer_id = value["id"]
    if not isinstance(customer_id, str) or _ID.fullmatch(customer_id) is None:
        raise ProviderStampCatalogError("app.id must be a lowercase slug")
    tier = value["tier"]
    if tier not in _TIERS:
        raise ProviderStampCatalogError("app.tier is invalid")

    identity = value["identity"]
    if not isinstance(identity, Mapping) or set(identity) != {"clientId", "apiApplicationIdUri"}:
        raise ProviderStampCatalogError("app.identity fields are invalid")
    _uuid(identity["clientId"], "app.identity.clientId")
    if identity["apiApplicationIdUri"] != f"api://{identity['clientId']}":
        raise ProviderStampCatalogError("app.identity.apiApplicationIdUri must use its clientId")

    components = value["components"]
    if not isinstance(components, Mapping) or set(components) != {
        "documentParserRepository", "mailTriageRepository", "doclingWorkerRepository"
    }:
        raise ProviderStampCatalogError("app.components fields are invalid")
    if any(
        not isinstance(repo, str)
        or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) is None
        for repo in components.values()
    ):
        raise ProviderStampCatalogError("app.components contains an invalid repository")

    data = value["data"]
    if not isinstance(data, Mapping) or set(data) != _APP_DATA_FIELDS:
        raise ProviderStampCatalogError("app.data fields are invalid")
    for name, item in data.items():
        if name == "mailboxes":
            if not isinstance(item, list) or not item or any(
                not isinstance(mailbox, str) or not mailbox.strip() for mailbox in item
            ):
                raise ProviderStampCatalogError("app.data.mailboxes must be a non-empty string list")
        elif not isinstance(item, str) or not item.strip():
            raise ProviderStampCatalogError(f"app.data.{name} must be a non-empty string")

    names = value["requiredKeyVaultSecretNames"]
    if (
        not isinstance(names, list)
        or not names
        or any(not isinstance(name, str) or _VAULT_SECRET.fullmatch(name) is None for name in names)
        or len(names) != len(set(names))
    ):
        raise ProviderStampCatalogError("app.requiredKeyVaultSecretNames must be unique Key Vault names")
    return copy.deepcopy(dict(value))


def build_stamp_customer(
    infrastructure_customer: Mapping[str, Any],
    environment: str,
    application_customer: Mapping[str, Any],
) -> dict[str, Any]:
    """Create the SDB Bicep parameter input by joining the two authoritative records."""
    app = validate_app_catalog_record(application_customer)
    customer_id = infrastructure_customer.get("id")
    if customer_id != app["id"]:
        raise ProviderStampCatalogError("catalog records must use the same customer id")
    environments = infrastructure_customer.get("environments")
    selected = environments.get(environment) if isinstance(environments, Mapping) else None
    if not isinstance(selected, Mapping):
        raise ProviderStampCatalogError(f"infrastructure customer has no {environment} environment")
    stamp = selected.get("providerStamp")
    if not isinstance(stamp, Mapping):
        raise ProviderStampCatalogError("infrastructure environment.providerStamp is required")

    provider_tenant = _uuid(stamp.get("tenantId"), "providerStamp.tenantId")
    provider_subscription = _uuid(stamp.get("subscriptionId"), "providerStamp.subscriptionId")
    automation = infrastructure_customer.get("automation")
    if not isinstance(automation, Mapping):
        raise ProviderStampCatalogError("infrastructure customer automation is required")
    if provider_tenant.casefold() != str(automation.get("lyhytAzureTenantId", "")).casefold():
        raise ProviderStampCatalogError("provider stamp tenant does not match the configured OIDC tenant")
    if provider_subscription.casefold() != str(automation.get("lyhytRuntimeSubscriptionId", "")).casefold():
        raise ProviderStampCatalogError("provider stamp subscription does not match the runtime subscription")
    provider_principal_id = _uuid(
        automation.get("lyhytAzurePrincipalObjectId"),
        "automation.lyhytAzurePrincipalObjectId",
    )
    provider_client_id = _uuid(
        automation.get("lyhytAzureClientId"), "automation.lyhytAzureClientId"
    )

    resource_group = stamp.get("resourceGroupName")
    location = stamp.get("location")
    hostname = stamp.get("hostname")
    deployment = stamp.get("deployment")
    required_deployment = {
        "functionDeploymentStorageName",
        "containerAppName",
        "containerName",
        "functionAppName",
        "doclingWorkerAppName",
        "doclingWorkerContainerName",
        "doclingWorkerManagedEnvironmentName",
        "doclingWorkerLogWorkspaceName",
        "containerAppsLocation",
        "externalFunctionApps",
        "keyVaultName",
        "managedEnvironmentName",
        "logWorkspaceName",
        "functionPlanName",
        "deploymentIdentityName",
        "managedCertificateName",
    }
    if (
        not isinstance(resource_group, str)
        or _NAME.fullmatch(resource_group) is None
        or not isinstance(location, str)
        or not location.strip()
        or not isinstance(hostname, str)
        or "." not in hostname
        or not isinstance(deployment, Mapping)
        or set(deployment) != required_deployment
    ):
        raise ProviderStampCatalogError("infrastructure environment.providerStamp targets are incomplete")
    container = stamp.get("container")
    worker = stamp.get("doclingWorker")
    function = stamp.get("function")
    if not isinstance(container, Mapping) or not isinstance(worker, Mapping) or not isinstance(function, Mapping):
        raise ProviderStampCatalogError("providerStamp runtime settings are incomplete")
    if set(container) != {
        "minReplicas", "maxReplicas", "concurrentRequests", "cpu", "memory",
        "ephemeralStorage", "ingressExternal", "targetPort",
    }:
        raise ProviderStampCatalogError("providerStamp.container settings are invalid")
    if set(worker) != {
        "minReplicas", "maxReplicas", "queueLength", "cpu", "memory", "ephemeralStorage",
    }:
        raise ProviderStampCatalogError("providerStamp.doclingWorker settings are invalid")
    if set(function) != {"runtime", "version", "instanceMemoryMB", "maximumInstanceCount"}:
        raise ProviderStampCatalogError("providerStamp.function settings are invalid")
    github_environment = stamp.get("githubEnvironment")
    if not isinstance(github_environment, str) or github_environment != github_environment.upper():
        raise ProviderStampCatalogError("providerStamp.githubEnvironment must be an uppercase environment")

    external_apps = deployment["externalFunctionApps"]
    if not isinstance(external_apps, list) or len(external_apps) != 2:
        raise ProviderStampCatalogError("providerStamp must define Document Parser and Mail Triage")
    profiles = {item.get("profile") for item in external_apps if isinstance(item, Mapping)}
    if profiles != {"document-parser", "mailtriage"}:
        raise ProviderStampCatalogError("providerStamp external Function Apps do not match app profiles")
    normalized_apps = []
    for app_target in external_apps:
        if not isinstance(app_target, Mapping) or set(app_target) != {
            "id", "profile", "functionAppName", "functionPlanName"
        }:
            raise ProviderStampCatalogError("providerStamp external Function App fields are invalid")
        if any(
            not isinstance(app_target[field], str) or not app_target[field].strip()
            for field in ("id", "profile", "functionAppName", "functionPlanName")
        ):
            raise ProviderStampCatalogError("providerStamp external Function App values are invalid")
        repository_key = (
            "documentParserRepository"
            if app_target["profile"] == "document-parser"
            else "mailTriageRepository"
        )
        normalized_apps.append({
            **dict(app_target),
            "repository": app["components"][repository_key],
            "functionResourceGroup": resource_group,
        })

    deployment_target = dict(deployment)
    deployment_target.update({
        "containerResourceGroup": resource_group,
        "functionResourceGroup": resource_group,
        "externalFunctionApps": normalized_apps,
        "deploymentIdentityFederatedSubject": (
            f"repo:ster-co/SDB-Calculation-v2:environment:{github_environment}"
        ),
    })
    workspace_id = stamp.get("applicationInsightsWorkspaceResourceId")
    workspace_match = re.match(r"^/subscriptions/([^/]+)/", str(workspace_id or ""), re.IGNORECASE)
    if not workspace_match or workspace_match.group(1).casefold() != provider_subscription.casefold():
        raise ProviderStampCatalogError(
            "providerStamp Application Insights workspace must be in the provider subscription"
        )
    return {
        "id": customer_id,
        "tier": app["tier"],
        "hostname": hostname,
        "customerTenantId": _uuid(infrastructure_customer.get("tenantId"), "customer.tenantId"),
        "resourceGroup": resource_group,
        "location": location,
        "deployment": deployment_target,
        "identity": app["identity"],
        "container": dict(container),
        "doclingWorker": dict(worker),
        "function": dict(function),
        "data": app["data"],
        "deploymentContext": {
            "providerTenantId": provider_tenant,
            "providerSubscriptionId": provider_subscription,
            "providerAutomationClientId": provider_client_id,
            "providerDeploymentPrincipalObjectId": provider_principal_id,
            "githubEnvironment": github_environment,
            "applicationInsightsWorkspaceResourceId": workspace_id,
            "requiredKeyVaultSecretNames": app["requiredKeyVaultSecretNames"],
        },
    }
