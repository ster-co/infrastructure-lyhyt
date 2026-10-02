"""Build and publish the complete SDB runtime Key Vault configuration."""

from __future__ import annotations

import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Protocol
from urllib.parse import urlsplit


NOT_CONFIGURED = "not-configured"
_KEY_VAULT_NAME = re.compile(r"^[a-z0-9-]{3,24}$")
_KEY_VAULT_SECRET_NAME = re.compile(r"^[A-Za-z0-9-]{1,127}$")
_TRANSIENT_ERROR_MARKERS = (
    "429",
    "internalservererror",
    "serviceunavailable",
    "temporarilyunavailable",
    "timeout",
    "timed out",
    "throttl",
    "temporar",
    "forbidden",
)

# Environment-variable name -> exact Key Vault name from the SDB loader.
RUNTIME_SECRET_NAMES: tuple[tuple[str, str], ...] = (
    ("CORS_ALLOWED_ORIGINS", "cors-allowed-origins"),
    ("SESSION_SECRET", "session-secret"),
    ("DB_SERVER_NAME", "db-server-name"),
    ("DB_NAME", "db-name"),
    ("DB_USER_NAME", "db-user-name"),
    ("DB_PASSWORD", "db-password"),
    ("AZURE_OPENAI_ENDPOINT", "azure-openai-endpoint"),
    ("AZURE_OPENAI_API_KEY", "azure-openai-api-key"),
    ("AZURE_API_VERSION", "azure-api-version"),
    ("LLM_MODEL_FULL", "llm-model-full"),
    ("LLM_MODEL_FAST", "llm-model-fast"),
    ("AZURE_EMBEDDING_DEPLOYMENT", "azure-embedding-deployment"),
    ("AZURE_OPENAI_EMBEDDING_DIMENSIONS", "azure-openai-embedding-dimensions"),
    ("AZURE_SEARCH_SERVICE_ENDPOINT", "azure-search-service-endpoint"),
    ("AZURE_SEARCH_API_KEY", "azure-search-api-key"),
    ("AZURE_SEARCH_INDEX_NAME", "azure-search-index-name"),
    ("AZURE_SEARCH_PROJECT_INDEX_NAME", "azure-search-project-index-name"),
    ("AZURE_SEARCH_INDEXER_NAME", "azure-search-indexer-name"),
    ("SP_CLIENT_ID", "sp-client-id"),
    ("SP_TENANT_ID", "sp-tenant-id"),
    ("SP_SECRET_VALUE", "sp-secret-value"),
    ("SP_DOMAIN", "sp-domain"),
    ("SP_SITE_NAME", "sp-site-name"),
    ("SP_FOLDER", "sp-folder"),
    ("SP_OFFERS_SUBFOLDER", "sp-offers-subfolder"),
    ("AAD_APP_ID_URI", "aad-app-id-uri"),
    ("AAD_JWKS_URL", "aad-jwks-url"),
    ("EXTRACTION_ENDPOINT", "extraction-endpoint"),
    ("EXTRACTION_CODE", "extraction-code"),
    ("DOCUMENT_PARSER_ENDPOINT", "document-parser-endpoint"),
    ("DOCUMENT_PARSER_CODE", "document-parser-code"),
    ("AzureWebJobsStorage", "azure-web-jobs-storage"),
    ("EXTRACTION_QUEUE_NAME", "extraction-queue-name"),
    ("OFFERTE_FLOW_QUEUE_NAME", "offerte-flow-queue-name"),
    ("JOB_STATUS_CONTAINER_NAME", "job-status-container-name"),
    ("GRAPH_MAILBOX_USER", "graph-mailbox-user"),
    ("OFFERS_MAILBOX_USER", "offers-mailbox-user"),
    ("PARSER_DECISION_NOTIFY_TO", "parser-decision-notify-to"),
    ("PARSER_DECISION_NOTIFY_FROM", "parser-decision-notify-from"),
    ("MAIL_ATTACHMENTS_STORAGE_CONNECTION", "mail-attachments-storage-connection"),
    ("MAIL_ATTACHMENTS_CONTAINER", "mail-attachments-container"),
    ("REPLY_MAILBOX", "reply-mailbox"),
    ("BRAVE_SEARCH_API_KEY", "brave-search-api-key"),
    ("AFAS_API_KEY", "afas-api-key"),
    ("AFAS_API_VERSION", "afas-api-version"),
    ("AFAS_OMGEVINGS_NUMMER", "afas-omgevings-nummer"),
    ("AFAS_OMGEVINGS_TYPE", "afas-omgevings-type"),
    ("BASE_GROUP_NAME", "base-group-name"),
    ("BASE_GROUP_PERMISSIONS", "base-group-permissions"),
)

_SECRET_NAMES = {secret_name for _, secret_name in RUNTIME_SECRET_NAMES}
if len(_SECRET_NAMES) != len(RUNTIME_SECRET_NAMES):  # pragma: no cover - import guard
    raise RuntimeError("runtime Key Vault secret names must be unique")
if any(_KEY_VAULT_SECRET_NAME.fullmatch(name) is None for name in _SECRET_NAMES):  # pragma: no cover
    raise RuntimeError("runtime Key Vault secret names must be Azure-safe")


@dataclass(frozen=True)
class RuntimeValue:
    value: str
    hydrated: bool


@dataclass(frozen=True)
class PublicationResult:
    created: tuple[str, ...]
    unchanged: tuple[str, ...]
    updated: tuple[str, ...]


class ConfigurationDriftError(ValueError):
    """Raised when a populated operator-managed value conflicts with hydration."""

    def __init__(self, names: Iterable[str]):
        self.names = tuple(sorted(names))
        super().__init__(
            "runtime Key Vault configuration drift detected for: "
            + ", ".join(self.names)
        )


class SecretPublisher(Protocol):
    def list_names(self) -> Iterable[str]:
        """Return names only."""

    def get_value(self, name: str) -> str | None:
        """Return one value without logging it."""

    def set_value(self, name: str, value: str) -> None:
        """Set one value without logging it."""


class InMemorySecretPublisher:
    """Test publisher with the same reconciliation semantics as Azure."""

    def __init__(self, values: Mapping[str, str] | None = None):
        self.values = dict(values or {})
        self.set_calls: list[tuple[str, str]] = []

    def list_names(self) -> Iterable[str]:
        return tuple(self.values)

    def get_value(self, name: str) -> str | None:
        return self.values.get(name)

    def set_value(self, name: str, value: str) -> None:
        self.set_calls.append((name, value))
        self.values[name] = value


class AzureCliSecretPublisher:
    """Azure CLI adapter with bounded retries and value-free errors."""

    def __init__(
        self,
        vault_name: str,
        *,
        runner: Callable[[list[str]], tuple[int, str, str]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
    ):
        if _KEY_VAULT_NAME.fullmatch(vault_name) is None:
            raise ValueError("runtime Key Vault name is not Azure-safe")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.vault_name = vault_name
        self._runner = runner or self._run_subprocess
        self._sleep = sleep
        self._max_attempts = max_attempts

    @staticmethod
    def _run_subprocess(arguments: list[str]) -> tuple[int, str, str]:
        result = subprocess.run(
            arguments,
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr

    @staticmethod
    def _is_transient(stderr: str) -> bool:
        lowered = stderr.casefold()
        return any(marker in lowered for marker in _TRANSIENT_ERROR_MARKERS)

    def _invoke(self, operation: str, *arguments: str) -> str:
        command = [
            "az",
            "keyvault",
            "secret",
            operation,
            *arguments,
            "--vault-name",
            self.vault_name,
            "--only-show-errors",
        ]
        for attempt in range(self._max_attempts):
            return_code, stdout, stderr = self._runner(command)
            if return_code == 0:
                return stdout
            if attempt + 1 >= self._max_attempts or not self._is_transient(stderr):
                raise RuntimeError(f"Azure Key Vault secret {operation} failed")
            self._sleep(2**attempt)
        raise RuntimeError(f"Azure Key Vault secret {operation} failed")

    def list_names(self) -> Iterable[str]:
        output = self._invoke("list", "--query", "[].name", "--output", "tsv")
        return tuple(line for line in output.splitlines() if line)

    def get_value(self, name: str) -> str | None:
        output = self._invoke(
            "show", "--name", name, "--query", "value", "--output", "tsv"
        )
        return output.rstrip("\n")

    def set_value(self, name: str, value: str) -> None:
        self._invoke("set", "--name", name, "--value", value, "--output", "none")


def _output_value(outputs: Mapping[str, object], name: str) -> str | None:
    candidate = outputs.get(name)
    if not isinstance(candidate, Mapping):
        return None
    value = candidate.get("value")
    return value if isinstance(value, str) and value else None


def _absolute_https(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        return None
    return value


def _hostname_route(outputs: Mapping[str, object], output_name: str, route: str) -> str | None:
    hostname = _output_value(outputs, output_name)
    if not hostname or "/" in hostname or "://" in hostname or any(char.isspace() for char in hostname):
        return None
    return _absolute_https(f"https://{hostname}{route}")


def _uuid_value(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError):
        return None


def build_runtime_configuration(
    foundation_outputs: Mapping[str, object],
    runtime_outputs: Mapping[str, object],
    customer_tenant_id: str,
) -> dict[str, RuntimeValue]:
    """Build all desired values without accepting secret-bearing inputs."""

    if not isinstance(foundation_outputs, Mapping) or not isinstance(runtime_outputs, Mapping):
        raise ValueError("deployment outputs must be objects")
    tenant_id = _uuid_value(customer_tenant_id)
    values = {
        secret_name: RuntimeValue(NOT_CONFIGURED, False)
        for _, secret_name in RUNTIME_SECRET_NAMES
    }

    def set_output(secret_name: str, output_name: str, *, endpoint: bool = False) -> None:
        value = _output_value(foundation_outputs, output_name)
        if endpoint:
            value = _absolute_https(value)
        if value is not None:
            values[secret_name] = RuntimeValue(value, True)

    set_output("db-server-name", "sqlServerFqdn")
    set_output("db-name", "sqlDatabaseName")
    set_output("azure-openai-endpoint", "aiEndpoint", endpoint=True)
    set_output("azure-search-service-endpoint", "searchEndpoint", endpoint=True)
    set_output("llm-model-full", "gpt54DeploymentName")
    set_output("llm-model-fast", "gpt5MiniDeploymentName")
    set_output("azure-embedding-deployment", "textEmbedding3LargeDeploymentName")
    if tenant_id is not None:
        values["sp-tenant-id"] = RuntimeValue(tenant_id, True)

    extraction_endpoint = _hostname_route(
        runtime_outputs, "sdbFunctionAppHostname", "/api/extraction"
    )
    if extraction_endpoint is not None:
        values["extraction-endpoint"] = RuntimeValue(extraction_endpoint, True)
    parser_endpoint = _hostname_route(
        runtime_outputs, "documentParserFunctionAppHostname", "/api/http_trigger"
    )
    if parser_endpoint is not None:
        values["document-parser-endpoint"] = RuntimeValue(parser_endpoint, True)
    return values


def publish_runtime_configuration(
    values: Mapping[str, RuntimeValue], publisher: SecretPublisher
) -> PublicationResult:
    """Preflight and reconcile without overwriting populated operator values."""

    expected_names = {secret_name for _, secret_name in RUNTIME_SECRET_NAMES}
    if set(values) != expected_names:
        raise ValueError("runtime configuration must contain the complete allowlist")
    if any(
        not isinstance(item, RuntimeValue)
        or not isinstance(item.value, str)
        or not item.value
        for item in values.values()
    ):
        raise ValueError("runtime configuration values must be non-empty RuntimeValue objects")

    existing_names = set(publisher.list_names())
    current = {
        name: publisher.get_value(name)
        for name in sorted(existing_names & expected_names)
    }
    drift = [
        name
        for name, current_value in current.items()
        if values[name].hydrated
        and current_value not in (None, NOT_CONFIGURED, values[name].value)
    ]
    if drift:
        raise ConfigurationDriftError(drift)

    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    actions: list[tuple[str, str, str]] = []
    for name in sorted(expected_names):
        item = values[name]
        if name not in existing_names:
            actions.append(("create", name, item.value))
        elif current[name] == NOT_CONFIGURED and item.hydrated:
            actions.append(("update", name, item.value))
        else:
            unchanged.append(name)

    for action, name, value in actions:
        publisher.set_value(name, value)
        if action == "create":
            created.append(name)
        else:
            updated.append(name)
    return PublicationResult(tuple(created), tuple(unchanged), tuple(updated))
