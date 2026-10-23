"""Apply Azure AI Search data-plane objects from the customer-foundation workflow."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


PORTAL_KEY_PLACEHOLDER = "__ENTER_IN_AZURE_PORTAL__"
SEARCH_TOKEN_RESOURCE = "https://search.azure.com/"
DEFAULT_API_VERSION = "2025-09-01"
AUTH_RETRY_COUNT = 12
AUTH_RETRY_SECONDS = 15
TEMPLATE_FILES = {
    "projectsIndex": "projects-index.json",
    "sharePointIndex": "sharepoint-index.json",
    "sqlDataSource": "sql-data-source.json",
    "sqlSkillset": "sql-vector-skillset.json",
    "sqlIndexer": "sql-indexer.json",
}
_SEARCH_RESOURCE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")


class SearchConfigurationError(RuntimeError):
    """Safe, non-sensitive error message for an unsuccessful apply."""


class SearchResponse:
    def __init__(self, status: int, message: str | None = None):
        self.status = status
        self.message = message


def _search_error_message(body: bytes) -> str | None:
    if not body:
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None

    messages: list[str] = []
    if isinstance(payload, Mapping):
        error = payload.get("error")
        if isinstance(error, Mapping):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                messages.append(message)
            details = error.get("details")
            if isinstance(details, list):
                for detail in details:
                    if isinstance(detail, Mapping):
                        detail_message = detail.get("message")
                        if isinstance(detail_message, str) and detail_message.strip():
                            messages.append(detail_message)
    if not messages:
        try:
            messages.append(body.decode("utf-8"))
        except UnicodeDecodeError:
            return None

    cleaned = " ".join(" ".join(messages).split())
    return cleaned[:1000] if cleaned else None


def _named_objects(configuration: Mapping[str, object], key: str) -> list[Mapping[str, object]]:
    value = configuration.get(key)
    if not isinstance(value, list):
        raise SearchConfigurationError(f"Search configuration is missing its {key} list")

    objects: list[Mapping[str, object]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise SearchConfigurationError(f"Search configuration has an invalid {key} object")
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise SearchConfigurationError(f"Search configuration has an unnamed {key} object")
        objects.append(item)
    return objects


def _validate_portal_key_placeholder(skillsets: list[Mapping[str, object]]) -> None:
    for skillset in skillsets:
        skills = skillset.get("skills")
        if not isinstance(skills, list):
            continue
        for skill in skills:
            if not isinstance(skill, Mapping) or "apiKey" not in skill:
                continue
            if skill.get("apiKey") != PORTAL_KEY_PLACEHOLDER:
                raise SearchConfigurationError(
                    "Search skillset JSON must keep the API key as the portal placeholder"
                )


def _run_az(arguments: list[str], failure_message: str) -> str:
    try:
        result = subprocess.run(
            ["az", *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        raise SearchConfigurationError(failure_message) from None
    return result.stdout.strip()


def _replace_placeholders(value: object, replacements: Mapping[str, str]) -> object:
    if isinstance(value, str):
        for placeholder, replacement in replacements.items():
            value = value.replace(placeholder, replacement)
        return value
    if isinstance(value, list):
        return [_replace_placeholders(item, replacements) for item in value]
    if isinstance(value, Mapping):
        return {
            key: _replace_placeholders(item, replacements)
            for key, item in value.items()
        }
    return value


def _deployment_output(outputs: Mapping[str, object], name: str) -> str:
    raw = outputs.get(name)
    if isinstance(raw, Mapping):
        raw = raw.get("value")
    if not isinstance(raw, str) or not raw.strip():
        raise SearchConfigurationError(
            f"Bicep deployment output {name!r} is missing or invalid"
        )
    return raw


def build_search_configuration(
    templates_dir: Path,
    customer_code: str,
    environment: str,
    deployment_outputs: Mapping[str, object],
) -> dict[str, object]:
    """Fill checked-in JSON templates with customer values and Bicep outputs."""
    if not isinstance(deployment_outputs, Mapping):
        raise SearchConfigurationError("Bicep deployment outputs must be an object")

    search_endpoint = _deployment_output(deployment_outputs, "searchEndpoint")
    sql_database_resource_id = _deployment_output(
        deployment_outputs, "sqlDatabaseResourceId"
    )
    azure_openai_endpoint = _deployment_output(deployment_outputs, "aiEndpoint").rstrip("/")
    embedding_deployment = _deployment_output(
        deployment_outputs, "textEmbedding3LargeDeploymentName"
    )
    replacements = {
        "__CUSTOMER_CODE__": customer_code.lower(),
        "__ENVIRONMENT__": environment,
        "__SQL_DATABASE_RESOURCE_ID__": sql_database_resource_id,
        "__AZURE_OPENAI_ENDPOINT__": azure_openai_endpoint,
        "__EMBEDDING_DEPLOYMENT__": embedding_deployment,
    }

    templates: dict[str, object] = {}
    for key, filename in TEMPLATE_FILES.items():
        try:
            template = json.loads((templates_dir / filename).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise SearchConfigurationError(
                f"Search JSON template {filename!r} could not be loaded"
            ) from None
        if not isinstance(template, Mapping):
            raise SearchConfigurationError(f"Search JSON template {filename!r} must be an object")
        templates[key] = _replace_placeholders(template, replacements)

    projects_index = templates["projectsIndex"]
    sharepoint_index = templates["sharePointIndex"]
    data_source = templates["sqlDataSource"]
    skillset = templates["sqlSkillset"]
    indexer = templates["sqlIndexer"]
    assert isinstance(projects_index, Mapping)
    assert isinstance(sharepoint_index, Mapping)
    assert isinstance(data_source, Mapping)
    assert isinstance(skillset, Mapping)
    assert isinstance(indexer, Mapping)

    if not search_endpoint.startswith("https://"):
        raise SearchConfigurationError("Search endpoint must use HTTPS")
    return {
        "indexes": [projects_index, sharepoint_index],
        "dataSources": [data_source],
        "skillsets": [skillset],
        "indexers": [indexer],
    }


def should_apply_search_configuration(
    environment: object,
    foundation_parameters: Mapping[str, object],
) -> bool:
    return (
        environment == "tst"
        and foundation_parameters.get("enableSearchService") is True
        and foundation_parameters.get("publicNetworkAccess") == "Enabled"
    )


def write_search_configuration_outputs(
    path: Path,
    *,
    applied: bool,
    configuration: Mapping[str, object] | None = None,
) -> None:
    """Publish only the names from a Search configuration that was applied."""
    values = {"search_configuration_applied": "true" if applied else "false"}
    if applied:
        if not isinstance(configuration, Mapping):
            raise SearchConfigurationError("applied Search configuration is missing")
        indexes = configuration.get("indexes")
        indexers = configuration.get("indexers")
        if not isinstance(indexes, list) or not isinstance(indexers, list):
            raise SearchConfigurationError("applied Search configuration is incomplete")
        if len(indexes) != 2 or len(indexers) != 1:
            raise SearchConfigurationError("applied Search configuration has an unexpected resource count")
        try:
            projects = next(
                item["name"] for item in indexes
                if isinstance(item, Mapping) and str(item.get("name", "")).endswith("-projects")
            )
            sharepoint = next(
                item["name"] for item in indexes
                if isinstance(item, Mapping) and "-sharepoint-" in str(item.get("name", ""))
            )
            indexer = indexers[0]["name"]
        except (KeyError, IndexError, StopIteration, TypeError):
            raise SearchConfigurationError("applied Search configuration names are missing") from None
        if any(
            not isinstance(name, str) or _SEARCH_RESOURCE_NAME.fullmatch(name) is None
            for name in (projects, sharepoint, indexer)
        ):
            raise SearchConfigurationError("applied Search configuration has an invalid resource name")
        values.update(
            {
                "projects_index_name": projects,
                "sharepoint_index_name": sharepoint,
                "indexer_name": indexer,
            }
        )
    with path.open("a", encoding="utf-8") as output:
        for name, value in values.items():
            output.write(f"{name}={value}\n")


def _require_success(response: SearchResponse, method: str, collection: str, name: str) -> None:
    if not 200 <= response.status < 300:
        detail = f": {response.message}" if response.message else ""
        raise SearchConfigurationError(
            f"Search REST {method} {collection}/{name} returned HTTP {response.status}{detail}"
        )


def _put(
    request: Callable[[str, str, str, Mapping[str, object] | None], SearchResponse],
    collection: str,
    resource: Mapping[str, object],
    emit: Callable[[str], None],
) -> None:
    name = str(resource["name"])
    response = request("PUT", collection, name, resource)
    _require_success(response, "PUT", collection, name)
    emit(f"Applied Search {collection}/{name}")


def _create_once(
    request: Callable[[str, str, str, Mapping[str, object] | None], SearchResponse],
    collection: str,
    resource: Mapping[str, object],
    emit: Callable[[str], None],
) -> None:
    name = str(resource["name"])
    response = request("GET", collection, name, None)
    if 200 <= response.status < 300:
        emit(f"Preserved existing Search {collection}/{name}")
        return
    if response.status != 404:
        _require_success(response, "GET", collection, name)
    _put(request, collection, resource, emit)


def apply_search_configuration(
    configuration: Mapping[str, object],
    request: Callable[[str, str, str, Mapping[str, object] | None], SearchResponse],
    *,
    emit: Callable[[str], None] = print,
) -> None:
    """Apply indexes and data sources on each run; preserve portal-owned objects."""
    if not isinstance(configuration, Mapping):
        raise SearchConfigurationError("Search configuration must be an object")

    indexes = _named_objects(configuration, "indexes")
    data_sources = _named_objects(configuration, "dataSources")
    skillsets = _named_objects(configuration, "skillsets")
    indexers = _named_objects(configuration, "indexers")
    _validate_portal_key_placeholder(skillsets)

    for index in indexes:
        _put(request, "indexes", index, emit)
    for data_source in data_sources:
        _put(request, "datasources", data_source, emit)
    for skillset in skillsets:
        _create_once(request, "skillsets", skillset, emit)
    for indexer in indexers:
        _create_once(request, "indexers", indexer, emit)


def _get_search_token() -> str:
    token = _run_az(
        [
            "account",
            "get-access-token",
            "--resource",
            SEARCH_TOKEN_RESOURCE,
            "--query",
            "accessToken",
            "--output",
            "tsv",
        ],
        "Azure CLI could not acquire a Search data-plane token",
    )
    if not token:
        raise SearchConfigurationError("Azure CLI returned an empty Search data-plane token")
    return token


class SearchRestClient:
    def __init__(
        self,
        endpoint: str,
        api_version: str,
        *,
        token_provider: Callable[[], str] = _get_search_token,
        retry_count: int = AUTH_RETRY_COUNT,
        retry_seconds: int = AUTH_RETRY_SECONDS,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_version = api_version
        self.token_provider = token_provider
        self.retry_count = retry_count
        self.retry_seconds = retry_seconds

    def request(
        self,
        method: str,
        collection: str,
        name: str,
        body: Mapping[str, object] | None = None,
    ) -> SearchResponse:
        url = (
            f"{self.endpoint}/{collection}/{quote(name, safe='-')}"
            f"?api-version={quote(self.api_version, safe='-')}"
        )
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else None

        for attempt in range(self.retry_count + 1):
            request = Request(
                url,
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.token_provider()}",
                    "Content-Type": "application/json",
                },
                method=method,
            )
            try:
                with urlopen(request, timeout=30) as response:
                    return SearchResponse(response.status)
            except HTTPError as error:
                if error.code in (401, 403) and attempt < self.retry_count:
                    time.sleep(self.retry_seconds)
                    continue
                return SearchResponse(error.code, _search_error_message(error.read(4096)))
            except (OSError, URLError, TimeoutError):
                raise SearchConfigurationError(
                    f"Search REST {method} {collection}/{name} could not reach the service"
                ) from None
        raise SearchConfigurationError("Search authorization retry limit was exceeded")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolved-file", required=True, type=Path)
    parser.add_argument("--deployment-outputs-file", required=True, type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    try:
        resolved = json.loads(args.resolved_file.read_text(encoding="utf-8"))
        if not isinstance(resolved, Mapping):
            raise SearchConfigurationError("Resolved customer configuration must be an object")
        foundation = resolved.get("foundationParameters")
        if not isinstance(foundation, Mapping):
            raise SearchConfigurationError("Resolved foundation parameters are missing")
        if not should_apply_search_configuration(resolved.get("environment"), foundation):
            print(
                "Skipping Search JSON apply; it is enabled only for TST with Search and public access enabled."
            )
            if args.github_output:
                write_search_configuration_outputs(args.github_output, applied=False)
            return 0

        customer_code = resolved.get("customerId")
        environment = resolved.get("environment")
        if not isinstance(customer_code, str) or not isinstance(environment, str):
            raise SearchConfigurationError("Resolved customer code or environment is missing")

        outputs = json.loads(
            args.deployment_outputs_file.read_text(encoding="utf-8")
        )
        configuration = build_search_configuration(
            Path("infra/customer-foundation/search"),
            customer_code,
            environment,
            outputs,
        )
        endpoint = _deployment_output(outputs, "searchEndpoint")
        client = SearchRestClient(endpoint, DEFAULT_API_VERSION)
        apply_search_configuration(configuration, client.request)
        if args.github_output:
            write_search_configuration_outputs(
                args.github_output,
                applied=True,
                configuration=configuration,
            )
    except (OSError, json.JSONDecodeError, SearchConfigurationError) as error:
        print(f"Search configuration apply failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
