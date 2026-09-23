"""Publish safe customer-resource configuration to the customer Key Vault."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol


_OUTPUT_TO_SECRET = {
    "storageAccountName": "storage-account-name",
    "blobEndpoint": "storage-blob-endpoint",
    "sqlServerFqdn": "db-server-name",
    "sqlDatabaseName": "db-name",
    "searchServiceName": "azure-search-service-name",
    "searchEndpoint": "azure-search-service-endpoint",
    "aiEndpoint": "azure-openai-endpoint",
    "documentIntelligenceEndpoint": "document-intelligence-endpoint",
    "gpt5DeploymentName": "azure-openai-deployment-gpt5",
    "gpt54DeploymentName": "azure-openai-deployment-gpt54",
    "gpt5MiniDeploymentName": "azure-openai-deployment-gpt5-mini",
    "textEmbedding3LargeDeploymentName": "azure-openai-deployment-text-embedding-3-large",
}
_KEY_VAULT_NAME = re.compile(r"^[a-z0-9-]{3,24}$")


class SecretPublisher(Protocol):
    def list_names(self) -> Iterable[str]:
        """Return secret names only; never return values from this method."""

    def get_value(self, name: str) -> str | None:
        """Return one existing value without logging it."""

    def set_value(self, name: str, value: str) -> None:
        """Set one value without logging it."""


class ConfigurationDriftError(ValueError):
    """Raised when Key Vault contains a different operator-managed value."""

    def __init__(self, names: Iterable[str]):
        self.names = tuple(sorted(names))
        super().__init__(
            "customer Key Vault configuration drift detected for: "
            + ", ".join(self.names)
        )


@dataclass(frozen=True)
class PublicationResult:
    created: tuple[str, ...]
    unchanged: tuple[str, ...]
    updated: tuple[str, ...]


class InMemorySecretPublisher:
    """Small test publisher with the same semantics as the Azure adapter."""

    def __init__(self, values: dict[str, str] | None = None):
        self.values = dict(values or {})

    def list_names(self) -> Iterable[str]:
        return tuple(self.values)

    def get_value(self, name: str) -> str | None:
        return self.values.get(name)

    def set_value(self, name: str, value: str) -> None:
        self.values[name] = value


class AzureCliSecretPublisher:
    """Azure CLI adapter that keeps command output out of workflow logs."""

    def __init__(
        self,
        vault_name: str,
        *,
        runner: Callable[[list[str]], tuple[int, str, str]] | None = None,
    ):
        if _KEY_VAULT_NAME.fullmatch(vault_name) is None:
            raise ValueError("customer Key Vault name is not Azure-safe")
        self.vault_name = vault_name
        self._runner = runner or self._run_subprocess

    @staticmethod
    def _run_subprocess(arguments: list[str]) -> tuple[int, str, str]:
        result = subprocess.run(
            arguments,
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr

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
        return_code, stdout, _stderr = self._runner(command)
        if return_code != 0:
            raise RuntimeError(f"Azure Key Vault secret {operation} failed")
        return stdout

    def list_names(self) -> Iterable[str]:
        output = self._invoke("list", "--query", "[].name", "--output", "tsv")
        return tuple(line for line in output.splitlines() if line)

    def get_value(self, name: str) -> str | None:
        output = self._invoke(
            "show",
            "--name",
            name,
            "--query",
            "value",
            "--output",
            "tsv",
        )
        return output.rstrip("\n")

    def set_value(self, name: str, value: str) -> None:
        self._invoke(
            "set",
            "--name",
            name,
            "--value",
            value,
            "--output",
            "none",
        )


def _output_value(raw_outputs: dict[str, object], output_name: str) -> str:
    output = raw_outputs.get(output_name)
    if not isinstance(output, dict) or not isinstance(output.get("value"), str):
        raise ValueError(f"foundation output {output_name} must contain a string value")
    value = output["value"]
    if not value:
        raise ValueError(f"foundation output {output_name} must not be empty")
    return value


def extract_customer_configuration(raw_outputs: dict[str, object]) -> dict[str, str]:
    """Map only safe, resource-derived foundation outputs to vault secret names."""

    if not isinstance(raw_outputs, dict):
        raise ValueError("deployment outputs must be an object")
    return {
        secret_name: _output_value(raw_outputs, output_name)
        for output_name, secret_name in _OUTPUT_TO_SECRET.items()
    }


def publish_customer_configuration(
    values: dict[str, str],
    publisher: SecretPublisher,
    *,
    allow_updates: bool = False,
) -> PublicationResult:
    """Initialize missing values and reject drift unless updates are explicit."""

    if not isinstance(values, dict) or any(
        not isinstance(name, str)
        or not isinstance(value, str)
        or not value
        for name, value in values.items()
    ):
        raise ValueError("customer configuration must contain non-empty string values")
    if set(values) - set(_OUTPUT_TO_SECRET.values()):
        raise ValueError("customer configuration contains an unallowlisted secret name")

    existing_names = set(publisher.list_names())
    current_values = {
        name: publisher.get_value(name)
        for name in sorted(existing_names & values.keys())
    }
    drift = [
        name
        for name, current in current_values.items()
        if current != values[name]
    ]
    if drift and not allow_updates:
        raise ConfigurationDriftError(drift)

    created: list[str] = []
    unchanged: list[str] = []
    updated: list[str] = []
    for name in sorted(values):
        if name not in existing_names:
            publisher.set_value(name, values[name])
            created.append(name)
        elif name in drift:
            publisher.set_value(name, values[name])
            updated.append(name)
        else:
            unchanged.append(name)

    return PublicationResult(tuple(created), tuple(unchanged), tuple(updated))
