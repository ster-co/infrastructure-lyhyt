"""Build and validate the credential-free customer application deployment handoff."""

from __future__ import annotations

import re
import uuid
import copy
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit


class HandoffError(ValueError):
    """Raised when a lifecycle handoff is incomplete, unsafe, or mis-targeted."""


_CUSTOMER_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,10}[a-z0-9])$")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_RESOURCE_ID = re.compile(r"^/subscriptions/([^/]+)/", re.IGNORECASE)
_HOSTNAME = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]+$", re.IGNORECASE)
_PINNED_RELEASE = re.compile(r"^stamp-v[A-Za-z0-9][A-Za-z0-9._-]*$")
_ENVIRONMENTS = {"tst", "acc", "prod"}
_OPERATIONS = {"onboard", "release"}
_PROFILE_FIELDS = {"api", "doclingWorker", "function"}
_FOUNDATION_OUTPUTS = {
    "storageAccountName",
    "sqlServerFqdn",
    "sqlDatabaseName",
    "sqlServerResourceId",
    "sqlDatabaseResourceId",
    "searchEndpoint",
    "aiEndpoint",
    "documentIntelligenceEndpoint",
    "gpt5DeploymentName",
    "gpt54DeploymentName",
    "gpt41MiniDeploymentName",
    "gpt41NanoDeploymentName",
    "textEmbedding3LargeDeploymentName",
}
_REQUIRED_FOUNDATION_OUTPUTS = {
    "sqlServerFqdn",
    "sqlDatabaseName",
    "searchEndpoint",
    "aiEndpoint",
    "documentIntelligenceEndpoint",
    "gpt5DeploymentName",
    "gpt54DeploymentName",
    "gpt41MiniDeploymentName",
    "gpt41NanoDeploymentName",
    "textEmbedding3LargeDeploymentName",
}
_RUNTIME_OUTPUTS = {
    "runtimeKeyVaultUri",
    "containerAppName",
    "containerAppFqdn",
    "containerAppHostname",
    "managedCertificateResourceId",
    "deploymentIdentityClientId",
    "deploymentIdentityName",
    "functionAppName",
    "functionAppHost",
    "documentParserFunctionAppName",
    "documentParserFunctionAppHostname",
    "mailTriageFunctionAppName",
    "mailTriageFunctionAppHostname",
    "doclingWorkerAppName",
    "deploymentGitHubEnvironment",
}
_REQUIRED_RUNTIME_OUTPUTS = {
    "runtimeKeyVaultUri",
    "containerAppName",
    "containerAppFqdn",
    "containerAppHostname",
    "managedCertificateResourceId",
    "deploymentIdentityClientId",
    "deploymentIdentityName",
    "functionAppName",
    "functionAppHost",
    "documentParserFunctionAppName",
    "documentParserFunctionAppHostname",
    "mailTriageFunctionAppName",
    "mailTriageFunctionAppHostname",
    "doclingWorkerAppName",
    "deploymentGitHubEnvironment",
}
_PLACEHOLDERS = {"", "not-configured", "__enter_in_azure_portal__"}


def _uuid(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise HandoffError(f"{field} must be a UUID")
    try:
        uuid.UUID(value)
    except ValueError:
        raise HandoffError(f"{field} must be a UUID") from None
    return value


def _safe_name(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SAFE_NAME.fullmatch(value) is None:
        raise HandoffError(f"{field} is invalid")
    return value


def _outputs(value: Any, field: str, allowed: set[str], required: set[str]) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise HandoffError(f"{field} must be an object")
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise HandoffError(f"unexpected {field} output: {', '.join(unknown)}")
    missing = sorted(required - set(value))
    if missing:
        raise HandoffError(f"{field} is missing required outputs: {', '.join(missing)}")
    result: dict[str, str] = {}
    for key, raw in value.items():
        if not isinstance(raw, str) or raw.strip().casefold() in _PLACEHOLDERS:
            raise HandoffError(f"{field}.{key} must be a non-empty applied value")
        result[key] = raw.strip()
    return result


def validate_lifecycle_handoff(payload: Any) -> dict[str, Any]:
    """Validate the exact versioned contract accepted by the app-only workflow."""
    if not isinstance(payload, Mapping):
        raise HandoffError("handoff must be an object")
    expected = {
        "schemaVersion",
        "customerId",
        "environment",
        "operation",
        "releaseVersion",
        "targets",
        "providerProfile",
        "foundation",
        "runtime",
    }
    if set(payload) != expected:
        raise HandoffError("handoff fields do not match schema version 1")
    if payload.get("schemaVersion") != 1:
        raise HandoffError("unsupported handoff schemaVersion")
    customer_id = payload.get("customerId")
    if not isinstance(customer_id, str) or _CUSTOMER_ID.fullmatch(customer_id) is None:
        raise HandoffError("customerId is invalid")
    if payload.get("environment") not in _ENVIRONMENTS:
        raise HandoffError("environment is invalid")
    if payload.get("operation") not in _OPERATIONS:
        raise HandoffError("operation must be onboard or release")
    release_version = payload.get("releaseVersion")
    if not isinstance(release_version, str) or _PINNED_RELEASE.fullmatch(release_version) is None:
        raise HandoffError("releaseVersion must be a pinned release tag matching stamp-v...")

    profile = payload.get("providerProfile")
    if not isinstance(profile, Mapping) or set(profile) != _PROFILE_FIELDS:
        raise HandoffError("providerProfile must contain API, Docling worker, and Function settings")
    api = profile["api"]
    api_fields = {
        "minReplicas", "maxReplicas", "concurrentRequests", "cpu", "memory",
        "ephemeralStorage", "ingressExternal", "targetPort",
    }
    if not isinstance(api, Mapping) or set(api) != api_fields:
        raise HandoffError("providerProfile.api fields are invalid")
    if (
        any(type(api[name]) is not int or api[name] < 1 for name in ("minReplicas", "maxReplicas", "concurrentRequests", "targetPort"))
        or api["minReplicas"] > api["maxReplicas"]
        or type(api["ingressExternal"]) is not bool
        or not isinstance(api["cpu"], (int, float))
        or isinstance(api["cpu"], bool)
        or api["cpu"] <= 0
        or any(not isinstance(api[name], str) or not api[name] for name in ("memory", "ephemeralStorage"))
    ):
        raise HandoffError("providerProfile.api values are invalid")
    worker = profile["doclingWorker"]
    worker_fields = {"minReplicas", "maxReplicas", "queueLength", "queueName", "cpu", "memory", "ephemeralStorage"}
    if not isinstance(worker, Mapping) or set(worker) != worker_fields:
        raise HandoffError("providerProfile.doclingWorker fields are invalid")
    if (
        any(type(worker[name]) is not int or worker[name] < 0 for name in worker_fields - {"memory", "ephemeralStorage", "queueName"})
        or worker["minReplicas"] > worker["maxReplicas"]
        or worker["queueLength"] < 1
        or worker["cpu"] < 1
        or not isinstance(worker["queueName"], str)
        or not worker["queueName"]
        or any(not isinstance(worker[name], str) or not worker[name] for name in ("memory", "ephemeralStorage"))
    ):
        raise HandoffError("providerProfile.doclingWorker values are invalid")
    function = profile["function"]
    if not isinstance(function, Mapping) or set(function) != {"runtime", "version", "instanceMemoryMB", "maximumInstanceCount"}:
        raise HandoffError("providerProfile.function fields are invalid")
    if (
        function["runtime"] != "python"
        or not isinstance(function["version"], str)
        or not function["version"]
        or type(function["instanceMemoryMB"]) is not int
        or function["instanceMemoryMB"] not in {512, 2048, 4096}
        or type(function["maximumInstanceCount"]) is not int
        or not 1 <= function["maximumInstanceCount"] <= 1000
    ):
        raise HandoffError("providerProfile.function values are invalid")

    targets = payload.get("targets")
    if not isinstance(targets, Mapping) or set(targets) != {"customer", "provider"}:
        raise HandoffError("targets must contain customer and provider scopes")
    target_result: dict[str, dict[str, str]] = {}
    for scope in ("customer", "provider"):
        target = targets[scope]
        expected_target_fields = {"tenantId", "subscriptionId"}
        if scope == "provider":
            expected_target_fields.add("resourceGroup")
        if not isinstance(target, Mapping) or set(target) != expected_target_fields:
            raise HandoffError(f"targets.{scope} fields are invalid")
        target_result[scope] = {
            "tenantId": _uuid(target["tenantId"], f"targets.{scope}.tenantId"),
            "subscriptionId": _uuid(target["subscriptionId"], f"targets.{scope}.subscriptionId"),
        }
        if scope == "provider":
            target_result[scope]["resourceGroup"] = _safe_name(
                target["resourceGroup"], "targets.provider.resourceGroup"
            )

    blocks: dict[str, dict[str, Any]] = {}
    for block_name, allowed, required in (
        ("foundation", _FOUNDATION_OUTPUTS, _REQUIRED_FOUNDATION_OUTPUTS),
        ("runtime", _RUNTIME_OUTPUTS, _REQUIRED_RUNTIME_OUTPUTS),
    ):
        block = payload.get(block_name)
        if not isinstance(block, Mapping) or set(block) != {"deploymentName", "outputs"}:
            raise HandoffError(f"{block_name} fields are invalid")
        outputs = _outputs(block["outputs"], block_name, allowed, required)
        blocks[block_name] = {
            "deploymentName": _safe_name(block["deploymentName"], f"{block_name}.deploymentName"),
            "outputs": outputs,
        }

    certificate_id = blocks["runtime"]["outputs"]["managedCertificateResourceId"]
    match = _RESOURCE_ID.match(certificate_id)
    if not match or match.group(1).casefold() != target_result["provider"]["subscriptionId"].casefold():
        raise HandoffError("runtime managed certificate is outside the provider subscription")

    runtime_outputs = blocks["runtime"]["outputs"]
    _uuid(runtime_outputs["deploymentIdentityClientId"], "runtime.deploymentIdentityClientId")
    _safe_name(runtime_outputs["deploymentIdentityName"], "runtime.deploymentIdentityName")
    if not re.fullmatch(r"[A-Z][A-Z0-9_-]{1,24}", runtime_outputs["deploymentGitHubEnvironment"]):
        raise HandoffError("runtime.deploymentGitHubEnvironment is invalid")
    vault = urlsplit(runtime_outputs["runtimeKeyVaultUri"])
    if (
        vault.scheme != "https"
        or not vault.hostname
        or not vault.hostname.endswith(".vault.azure.net")
        or vault.username
        or vault.password
        or vault.path not in ("", "/")
        or vault.query
        or vault.fragment
    ):
        raise HandoffError("runtimeKeyVaultUri must be an HTTPS Key Vault root URI")
    if not _HOSTNAME.fullmatch(runtime_outputs["containerAppFqdn"]):
        raise HandoffError("containerAppFqdn is invalid")
    for field in (
        "functionAppHost",
        "documentParserFunctionAppHostname",
        "mailTriageFunctionAppHostname",
    ):
        if not _HOSTNAME.fullmatch(runtime_outputs[field]) or not runtime_outputs[field].casefold().endswith(".azurewebsites.net"):
            raise HandoffError(f"runtime.{field} is not an Azure Functions hostname")

    return {
        "schemaVersion": 1,
        "customerId": customer_id,
        "environment": payload["environment"],
        "operation": payload["operation"],
        "releaseVersion": release_version,
        "targets": target_result,
        "providerProfile": copy.deepcopy(dict(profile)),
        "foundation": blocks["foundation"],
        "runtime": blocks["runtime"],
    }


def build_lifecycle_handoff(
    *,
    customer_id: str,
    environment: str,
    operation: str,
    release_version: str,
    customer_tenant_id: str,
    customer_subscription_id: str,
    provider_tenant_id: str,
    provider_subscription_id: str,
    provider_resource_group: str,
    foundation_deployment_name: str,
    runtime_deployment_name: str,
    foundation_outputs: Mapping[str, object],
    runtime_outputs: Mapping[str, object],
    provider_profile: Mapping[str, Any],
) -> dict[str, Any]:
    """Construct the allowlisted, credential-free handoff sent to the app workflow."""
    payload = {
        "schemaVersion": 1,
        "customerId": customer_id,
        "environment": environment,
        "operation": operation,
        "releaseVersion": release_version,
        "targets": {
            "customer": {
                "tenantId": customer_tenant_id,
                "subscriptionId": customer_subscription_id,
            },
            "provider": {
                "tenantId": provider_tenant_id,
                "subscriptionId": provider_subscription_id,
                "resourceGroup": provider_resource_group,
            },
        },
        "providerProfile": dict(provider_profile),
        "foundation": {
            "deploymentName": foundation_deployment_name,
            "outputs": dict(foundation_outputs),
        },
        "runtime": {
            "deploymentName": runtime_deployment_name,
            "outputs": dict(runtime_outputs),
        },
    }
    return validate_lifecycle_handoff(payload)


def _arm_outputs(value: Any, allowed: set[str], field: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise HandoffError(f"{field} deployment outputs must be an object")
    result: dict[str, str] = {}
    for name, raw in value.items():
        if name not in allowed:
            continue
        if not isinstance(raw, Mapping) or "value" not in raw:
            raise HandoffError(f"{field}.{name} is not a standard ARM output")
        output = raw["value"]
        if not isinstance(output, str):
            raise HandoffError(f"{field}.{name} must be a string output")
        result[name] = output
    return result


def build_lifecycle_handoff_from_deployments(
    resolved: Mapping[str, Any],
    foundation_arm_outputs: Mapping[str, Any],
    runtime_arm_outputs: Mapping[str, Any],
    *,
    operation: str,
    release_version: str,
) -> dict[str, Any]:
    """Map ARM deployment outputs into the allowlisted app handoff contract."""
    foundation = resolved.get("foundation")
    stamp = resolved.get("providerStamp")
    if not isinstance(foundation, Mapping) or not isinstance(stamp, Mapping):
        raise HandoffError("resolved lifecycle request is missing foundation or provider stamp")
    context = stamp.get("deploymentContext")
    if not isinstance(context, Mapping):
        raise HandoffError("resolved lifecycle request is missing provider deployment context")
    customer_id = resolved.get("customerId")
    environment = resolved.get("environment")
    return build_lifecycle_handoff(
        customer_id=customer_id,
        environment=environment,
        operation=operation,
        release_version=release_version,
        customer_tenant_id=foundation["customerTenantId"],
        customer_subscription_id=foundation["subscriptionId"],
        provider_tenant_id=context["providerTenantId"],
        provider_subscription_id=context["providerSubscriptionId"],
        provider_resource_group=stamp["resourceGroup"],
        foundation_deployment_name=f"customer-foundation-{customer_id}-{environment}",
        runtime_deployment_name=f"provider-stamp-{customer_id}-{environment}-runtime",
        foundation_outputs=_arm_outputs(
            foundation_arm_outputs, _FOUNDATION_OUTPUTS, "foundation"
        ),
        runtime_outputs=_arm_outputs(runtime_arm_outputs, _RUNTIME_OUTPUTS, "runtime"),
        provider_profile={
            "api": dict(stamp["container"]),
            "doclingWorker": {
                **dict(stamp["doclingWorker"]),
                "queueName": stamp["data"]["doclingJobsQueue"],
            },
            "function": dict(stamp["function"]),
        },
    )


def main() -> int:
    import argparse
    import json
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolved-file", required=True, type=Path)
    parser.add_argument("--foundation-outputs-file", required=True, type=Path)
    parser.add_argument("--runtime-outputs-file", required=True, type=Path)
    parser.add_argument("--operation", required=True, choices=sorted(_OPERATIONS))
    parser.add_argument("--release-version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        handoff = build_lifecycle_handoff_from_deployments(
            json.loads(args.resolved_file.read_text(encoding="utf-8")),
            json.loads(args.foundation_outputs_file.read_text(encoding="utf-8")),
            json.loads(args.runtime_outputs_file.read_text(encoding="utf-8")),
            operation=args.operation,
            release_version=args.release_version,
        )
        args.output.write_text(
            json.dumps(handoff, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError, KeyError, HandoffError) as error:
        print(f"lifecycle_handoff: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
