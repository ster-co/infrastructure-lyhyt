"""Resolve one customer across the authoritative infrastructure and app catalogs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from scripts.pipeline.provider_stamp_customer import (
    ProviderStampCatalogError,
    build_stamp_customer,
    validate_app_catalog_record,
)
from scripts.pipeline.resolve_foundation_customer import resolve_foundation_customer


class LifecycleRequestError(ValueError):
    """Raised when a lifecycle request is ambiguous, unpinned, or mis-targeted."""


_PINNED_RELEASE = re.compile(r"^stamp-v[A-Za-z0-9][A-Za-z0-9._-]*$")
_ENVIRONMENTS = {"tst", "acc", "prod"}
_OPERATIONS = {"onboard", "release"}


def _one_customer(catalog: Any, customer_id: str) -> dict[str, Any]:
    customers = catalog.get("customers") if isinstance(catalog, dict) else None
    if not isinstance(customers, list):
        raise LifecycleRequestError("catalog must contain a customers array")
    matches = [
        item for item in customers
        if isinstance(item, dict) and item.get("id") == customer_id
    ]
    if len(matches) != 1:
        raise LifecycleRequestError(
            f"catalog must contain exactly one record for {customer_id!r}"
        )
    return matches[0]


def resolve_lifecycle_request(
    infrastructure_catalog: dict[str, Any],
    app_catalog: dict[str, Any],
    *,
    customer_id: str,
    environment: str,
    operation: str,
    release_version: str,
    ref_type: str,
) -> dict[str, Any]:
    """Validate matching customer records and return safe deployment inputs."""
    if environment not in _ENVIRONMENTS:
        raise LifecycleRequestError("environment must be tst, acc, or prod")
    if operation not in _OPERATIONS:
        raise LifecycleRequestError("operation must be onboard or release")
    if not isinstance(release_version, str) or _PINNED_RELEASE.fullmatch(release_version) is None:
        raise LifecycleRequestError("release_version must be a pinned release tag matching stamp-v...")
    if not isinstance(app_catalog, dict) or app_catalog.get("schemaVersion") != 1:
        raise LifecycleRequestError("app catalog schemaVersion is unsupported")

    infrastructure_customer = _one_customer(infrastructure_catalog, customer_id)
    application_customer = validate_app_catalog_record(_one_customer(app_catalog, customer_id))
    if infrastructure_customer.get("enabled") is not True:
        raise LifecycleRequestError(f"customer {customer_id!r} is disabled")

    try:
        foundation = resolve_foundation_customer(
            infrastructure_catalog, customer_id, environment, ref_type
        )
        stamp_customer = build_stamp_customer(
            infrastructure_customer, environment, application_customer
        )
    except (ProviderStampCatalogError, ValueError) as error:
        raise LifecycleRequestError(str(error)) from error

    return {
        "schemaVersion": 1,
        "customerId": customer_id,
        "environment": environment,
        "operation": operation,
        "releaseVersion": release_version,
        "foundation": foundation,
        "providerStamp": stamp_customer,
        "application": application_customer,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--app-catalog", required=True, type=Path)
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--release-version", required=True)
    parser.add_argument("--ref-type", required=True)
    args = parser.parse_args()
    try:
        resolved = resolve_lifecycle_request(
            json.loads(args.catalog.read_text(encoding="utf-8")),
            json.loads(args.app_catalog.read_text(encoding="utf-8")),
            customer_id=args.customer_id,
            environment=args.environment,
            operation=args.operation,
            release_version=args.release_version,
            ref_type=args.ref_type,
        )
    except (OSError, json.JSONDecodeError, LifecycleRequestError) as error:
        print(f"resolve_lifecycle_request: {error}", file=sys.stderr)
        return 1
    print(json.dumps(resolved, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
