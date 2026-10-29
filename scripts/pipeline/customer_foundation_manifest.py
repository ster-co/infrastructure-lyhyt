"""Build the safe customer-foundation handoff shown in the workflow summary."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse


class FoundationManifestError(ValueError):
    """Raised when deployment outputs cannot form a safe handoff manifest."""


_DEPLOYMENT_OUTPUTS = (
    "createdCustomerResourceGroupName",
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
)
_SEARCH_OUTPUTS = {
    "sharepointIndexName": "sharePointIndex",
    "projectsIndexName": "projectsIndex",
    "indexerName": "indexer",
}
_PLACEHOLDERS = {"not-configured", "__enter_in_azure_portal__"}
_SAFE_SEARCH_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")
_SQL_FQDN = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.database\.windows\.net$",
    re.IGNORECASE,
)
_AZURE_ENDPOINT_HOSTS = {
    "searchEndpoint": re.compile(
        r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.search\.windows\.net$",
        re.IGNORECASE,
    ),
    "aiEndpoint": re.compile(
        r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.(?:openai\.azure\.com|cognitiveservices\.azure\.com)$",
        re.IGNORECASE,
    ),
    "documentIntelligenceEndpoint": re.compile(
        r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.cognitiveservices\.azure\.com$",
        re.IGNORECASE,
    ),
}
_RESOURCE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_DATABASE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def _deployment_value(outputs: Mapping[str, object], name: str) -> str | None:
    raw = outputs.get(name)
    if not isinstance(raw, Mapping):
        return None
    value = raw.get("value")
    if (
        not isinstance(value, str)
        or not value.strip()
        or value.strip().casefold() in _PLACEHOLDERS
    ):
        return None
    return value.strip()


def _https_endpoint(value: str, field: str) -> None:
    try:
        parsed = urlparse(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        hostname = None
        port = None
        parsed = None
    if (
        parsed is None
        or parsed.scheme != "https"
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
        or port not in (None, 443)
        or parsed.netloc.casefold() not in {hostname.casefold(), f"{hostname}:443".casefold()}
        or _AZURE_ENDPOINT_HOSTS[field].fullmatch(hostname) is None
    ):
        raise FoundationManifestError(
            f"Bicep deployment output {field!r} must be an HTTPS Azure endpoint"
        )


def _search_names(configuration: Mapping[str, object]) -> dict[str, str]:
    indexes = configuration.get("indexes")
    indexers = configuration.get("indexers")
    if not isinstance(indexes, list) or not isinstance(indexers, list):
        raise FoundationManifestError("applied Search configuration is missing indexes or indexers")
    if len(indexes) != 2 or len(indexers) != 1:
        raise FoundationManifestError("applied Search configuration has an unexpected resource count")

    names: dict[str, str] = {}
    for key, role in _SEARCH_OUTPUTS.items():
        resources = indexers if role == "indexer" else indexes
        matches = [resource for resource in resources if isinstance(resource, Mapping)]
        if role == "indexer":
            resource = matches[0] if len(matches) == 1 else None
        else:
            suffix = "-sharepoint-" if role == "sharePointIndex" else "-projects"
            matching = [
                item for item in matches
                if isinstance(item.get("name"), str)
                and (item["name"].find(suffix) >= 0 if role == "sharePointIndex" else item["name"].endswith(suffix))
            ]
            resource = matching[0] if len(matching) == 1 else None
        value = resource.get("name") if isinstance(resource, Mapping) else None
        if not isinstance(value, str) or _SAFE_SEARCH_NAME.fullmatch(value) is None:
            raise FoundationManifestError(f"applied Search configuration has an invalid {key}")
        names[key] = value
    return names


def build_customer_foundation_manifest(
    resolved: Mapping[str, object],
    deployment_outputs: Mapping[str, object],
    *,
    search_configuration_applied: bool,
    search_configuration: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Map applied deployment values into the versioned, credential-free handoff."""
    if not isinstance(resolved, Mapping) or not isinstance(deployment_outputs, Mapping):
        raise FoundationManifestError("resolved customer and deployment outputs must be objects")
    if type(search_configuration_applied) is not bool:
        raise FoundationManifestError("searchConfigurationApplied must be a JSON boolean")

    customer_id = resolved.get("customerId")
    environment = resolved.get("environment")
    foundation = resolved.get("foundationParameters")
    if not isinstance(customer_id, str) or not customer_id.strip():
        raise FoundationManifestError("resolved customerId is missing")
    if environment not in {"tst", "acc", "prod"}:
        raise FoundationManifestError("resolved environment is invalid")
    if not isinstance(foundation, Mapping):
        raise FoundationManifestError("resolved foundationParameters are missing")

    sql_entra_only = foundation.get("sqlEntraOnlyAuthentication")
    public_network = foundation.get("publicNetworkAccess")
    storage_network = foundation.get("storageNetworkDefaultAction")
    if type(sql_entra_only) is not bool:
        raise FoundationManifestError("sqlEntraOnlyAuthentication must be an explicit boolean")
    if "enableSearchService" in foundation and type(foundation["enableSearchService"]) is not bool:
        raise FoundationManifestError("enableSearchService must be an explicit boolean when set")
    if public_network not in {"Enabled", "Disabled"}:
        raise FoundationManifestError("publicNetworkAccess must be explicitly configured")
    if storage_network not in {"Allow", "Deny"}:
        raise FoundationManifestError("storageNetworkDefaultAction must be explicitly configured")

    outputs: dict[str, str] = {}
    for name in _DEPLOYMENT_OUTPUTS:
        if name == "searchEndpoint" and foundation.get("enableSearchService") is not True:
            continue
        value = _deployment_value(deployment_outputs, name)
        if value is not None:
            outputs[name] = value
    if "sqlServerFqdn" in outputs and _SQL_FQDN.fullmatch(outputs["sqlServerFqdn"]) is None:
        raise FoundationManifestError("sqlServerFqdn must be an Azure SQL server FQDN")
    if "sqlDatabaseName" in outputs and _DATABASE_NAME.fullmatch(outputs["sqlDatabaseName"]) is None:
        raise FoundationManifestError("sqlDatabaseName is invalid")
    for field in (
        "gpt5DeploymentName",
        "gpt54DeploymentName",
        "gpt41MiniDeploymentName",
        "gpt41NanoDeploymentName",
        "textEmbedding3LargeDeploymentName",
    ):
        if field in outputs and _RESOURCE_NAME.fullmatch(outputs[field]) is None:
            raise FoundationManifestError(f"{field} is invalid")
    for field in ("searchEndpoint", "aiEndpoint", "documentIntelligenceEndpoint"):
        if field in outputs:
            _https_endpoint(outputs[field], field)
    if (
        "createdCustomerResourceGroupName" in outputs
        and _RESOURCE_NAME.fullmatch(outputs["createdCustomerResourceGroupName"]) is None
    ):
        raise FoundationManifestError("createdCustomerResourceGroupName is invalid")

    if search_configuration_applied:
        if (
            environment != "tst"
            or foundation.get("enableSearchService") is not True
            or public_network != "Enabled"
        ):
            raise FoundationManifestError(
                "Search configuration cannot be marked applied outside the supported public TST setup"
            )
        if not isinstance(search_configuration, Mapping):
            raise FoundationManifestError("applied Search configuration is required")
        outputs.update(_search_names(search_configuration))
    elif search_configuration is not None:
        raise FoundationManifestError("Search names may be included only after Search configuration was applied")

    return {
        "schemaVersion": 1,
        "customerId": customer_id,
        "environment": environment,
        "sqlEntraOnlyAuthentication": sql_entra_only,
        "publicNetworkAccess": public_network,
        "storageNetworkDefaultAction": storage_network,
        "searchConfigurationApplied": search_configuration_applied,
        "outputs": outputs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolved-file", required=True, type=Path)
    parser.add_argument("--deployment-outputs-file", required=True, type=Path)
    parser.add_argument("--search-configuration-applied", required=True, choices=("true", "false"))
    parser.add_argument("--search-index-names-file", type=Path)
    args = parser.parse_args()
    try:
        resolved = json.loads(args.resolved_file.read_text(encoding="utf-8"))
        deployment_outputs = json.loads(args.deployment_outputs_file.read_text(encoding="utf-8"))
        names = (
            json.loads(args.search_index_names_file.read_text(encoding="utf-8"))
            if args.search_index_names_file
            else None
        )
        if names is not None:
            if not isinstance(names, Mapping) or set(names) != set(_SEARCH_OUTPUTS):
                raise FoundationManifestError("Search index names file has unexpected fields")
            search_configuration: Mapping[str, object] | None = {
                "indexes": [
                    {"name": names["projectsIndexName"]},
                    {"name": names["sharepointIndexName"]},
                ],
                "indexers": [{"name": names["indexerName"]}],
            }
        else:
            search_configuration = None
        manifest = build_customer_foundation_manifest(
            resolved,
            deployment_outputs,
            search_configuration_applied=args.search_configuration_applied == "true",
            search_configuration=search_configuration,
        )
    except (OSError, json.JSONDecodeError, FoundationManifestError) as error:
        print(f"Customer foundation handoff failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, separators=(",", ":"), sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
