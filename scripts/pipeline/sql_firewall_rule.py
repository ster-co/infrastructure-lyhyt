"""Manage a run-scoped Azure SQL firewall rule for GitHub-hosted SQL jobs."""

from __future__ import annotations

import argparse
import ipaddress
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from scripts.pipeline.deployment_outputs import validate_resource_id_subscription


_RULE_NAME = re.compile(r"^lyhyt-gha-[0-9]+-[0-9]+-[a-z0-9_-]+$")


def _parse_sql_server_resource_id(
    resource_id: str, subscription_id: str
) -> tuple[str, str]:
    validate_resource_id_subscription(resource_id, subscription_id, "Microsoft.Sql")
    segments = resource_id.strip("/").split("/")
    if (
        len(segments) != 8
        or segments[0].casefold() != "subscriptions"
        or segments[2].casefold() != "resourcegroups"
        or segments[4].casefold() != "providers"
        or segments[5].casefold() != "microsoft.sql"
        or segments[6].casefold() != "servers"
        or not segments[3]
        or not segments[7]
    ):
        raise ValueError("resource ID must identify one SQL server")
    return segments[3], segments[7]


def _rule_name(run_id: str, run_attempt: str, job: str) -> str:
    if not run_id.isdigit() or not run_attempt.isdigit():
        raise ValueError("GitHub run ID and attempt must be numeric")
    if not re.fullmatch(r"[a-z0-9_-]{1,64}", job):
        raise ValueError("GitHub job name contains unsupported characters")
    name = f"lyhyt-gha-{run_id}-{run_attempt}-{job}"
    if len(name) > 128:
        raise ValueError("generated SQL firewall rule name is too long")
    return name


def _runner_public_ip() -> str:
    try:
        with urlopen("https://api.ipify.org", timeout=15) as response:
            value = response.read(64).decode("ascii").strip()
        address = ipaddress.ip_address(value)
    except (OSError, UnicodeDecodeError, ValueError, URLError):
        raise RuntimeError("could not determine the GitHub runner public IPv4 address") from None
    if not isinstance(address, ipaddress.IPv4Address):
        raise RuntimeError("the GitHub runner did not return a public IPv4 address")
    return str(address)


def _run_az(arguments: list[str]) -> None:
    operation = arguments[3] if len(arguments) > 3 else "manage"
    permission = "write" if operation == "create" else "delete"
    try:
        subprocess.run(
            ["az", *arguments, "--only-show-errors"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        raise RuntimeError(
            f"Azure CLI could not {operation} the temporary SQL firewall rule; "
            f"verify Microsoft.Sql/servers/firewallRules/{permission} access on the SQL server"
        ) from None


def _write_rule_name(output_file: Path, name: str) -> None:
    with output_file.open("a", encoding="utf-8") as output:
        output.write(f"rule_name={name}\n")


def open_temporary_firewall_rule(
    resource_id: str,
    subscription_id: str,
    public_network_access: str,
    output_file: Path,
) -> str | None:
    resource_group, server_name = _parse_sql_server_resource_id(resource_id, subscription_id)
    if public_network_access not in ("Enabled", "Disabled"):
        raise ValueError("public network access must be Enabled or Disabled")

    if os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        _write_rule_name(output_file, "")
        print("Skipping temporary firewall rule for non-hosted SQL runner.")
        return None
    if os.environ.get("SQL_ENVIRONMENT") == "prod":
        _write_rule_name(output_file, "")
        print("Skipping temporary public firewall rule for production SQL.")
        return None
    if public_network_access == "Disabled":
        _write_rule_name(output_file, "")
        print("Skipping temporary firewall rule because SQL public access is disabled.")
        return None

    name = _rule_name(
        os.environ.get("GITHUB_RUN_ID", ""),
        os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        os.environ.get("GITHUB_JOB", ""),
    )
    address = _runner_public_ip()
    # Record the deterministic name before the ARM call so the always-run cleanup
    # step can remove a rule even if the create request times out after succeeding.
    _write_rule_name(output_file, name)
    _run_az(
        [
            "sql",
            "server",
            "firewall-rule",
            "create",
            "--resource-group",
            resource_group,
            "--server",
            server_name,
            "--name",
            name,
            "--start-ip-address",
            address,
            "--end-ip-address",
            address,
            "--subscription",
            subscription_id,
            "--output",
            "none",
        ]
    )
    print(f"Opened temporary SQL firewall rule {name} for this job.")
    return name


def remove_temporary_firewall_rule(
    resource_id: str, subscription_id: str, rule_name: str
) -> None:
    if not rule_name:
        return
    if not _RULE_NAME.fullmatch(rule_name):
        raise ValueError("refusing to remove a SQL firewall rule outside the workflow namespace")
    resource_group, server_name = _parse_sql_server_resource_id(resource_id, subscription_id)
    _run_az(
        [
            "sql",
            "server",
            "firewall-rule",
            "delete",
            "--resource-group",
            resource_group,
            "--server",
            server_name,
            "--name",
            rule_name,
            "--subscription",
            subscription_id,
            "--output",
            "none",
        ]
    )
    print(f"Removed temporary SQL firewall rule {rule_name}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("open", help="open a firewall rule for this hosted job")
    close_parser = subparsers.add_parser("close", help="remove this job's firewall rule")
    close_parser.add_argument("--rule-name", required=True)
    args = parser.parse_args(argv)

    resource_id = os.environ.get("SQL_SERVER_RESOURCE_ID", "")
    subscription_id = os.environ.get("CUSTOMER_SUBSCRIPTION_ID", "")
    try:
        if args.command == "open":
            output = os.environ.get("GITHUB_OUTPUT", "")
            if not output:
                raise ValueError("GITHUB_OUTPUT is required")
            open_temporary_firewall_rule(
                resource_id,
                subscription_id,
                os.environ.get("SQL_PUBLIC_NETWORK_ACCESS", ""),
                Path(output),
            )
        else:
            remove_temporary_firewall_rule(resource_id, subscription_id, args.rule_name)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"sql_firewall_rule: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
