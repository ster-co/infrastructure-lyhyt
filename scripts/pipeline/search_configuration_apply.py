"""Apply Azure AI Search data-plane objects from a Bicep deployment script."""

from __future__ import annotations

import json
import os
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


class SearchConfigurationError(RuntimeError):
    """Safe, non-sensitive error message for an unsuccessful apply."""


class SearchResponse:
    def __init__(self, status: int):
        self.status = status


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


def _require_success(response: SearchResponse, method: str, collection: str, name: str) -> None:
    if not 200 <= response.status < 300:
        raise SearchConfigurationError(
            f"Search REST {method} {collection}/{name} returned HTTP {response.status}"
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


def _login_with_user_assigned_identity(client_id: str) -> None:
    if not client_id:
        raise SearchConfigurationError("Search configuration identity client ID is missing")
    _run_az(
        [
            "login",
            "--identity",
            "--username",
            client_id,
            "--allow-no-subscriptions",
            "--only-show-errors",
            "--output",
            "none",
        ],
        "Azure CLI could not log in with the Search configuration identity",
    )


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
                return SearchResponse(error.code)
            except (OSError, URLError, TimeoutError):
                raise SearchConfigurationError(
                    f"Search REST {method} {collection}/{name} could not reach the service"
                ) from None
        raise SearchConfigurationError("Search authorization retry limit was exceeded")


def main() -> int:
    try:
        endpoint = os.environ["SEARCH_ENDPOINT"]
        configuration_json = os.environ.get("SEARCH_CONFIGURATION_JSON")
        if configuration_json is None:
            configuration_path = Path(os.environ["SEARCH_CONFIGURATION_FILE"])
            configuration_json = configuration_path.read_text(encoding="utf-8")
        configuration = json.loads(configuration_json)
        api_version = os.environ.get("SEARCH_API_VERSION", DEFAULT_API_VERSION)
        identity_client_id = os.environ["SEARCH_CONFIG_IDENTITY_CLIENT_ID"]
        if not endpoint.startswith("https://"):
            raise SearchConfigurationError("Search endpoint must use HTTPS")

        _login_with_user_assigned_identity(identity_client_id)
        client = SearchRestClient(endpoint, api_version)
        apply_search_configuration(configuration, client.request)
    except (KeyError, json.JSONDecodeError, SearchConfigurationError) as error:
        print(f"Search configuration apply failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
