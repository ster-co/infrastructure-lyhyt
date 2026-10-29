"""Fail closed unless each configured model is available with enough regional quota."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote


class ModelCapacityError(ValueError):
    """Raised when configured model capacity cannot be confirmed."""


def validate_model_capacity(
    resolved: Mapping[str, Any],
    query: Callable[[str, Mapping[str, Any]], Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Check every exact model, version, SKU, and requested capacity."""
    foundation = resolved.get("foundationParameters")
    subscription_id = resolved.get("subscriptionId")
    if not isinstance(foundation, Mapping) or not isinstance(subscription_id, str):
        raise ModelCapacityError("resolved customer foundation target is incomplete")
    locations = foundation.get("serviceLocations")
    region = locations.get("ai") if isinstance(locations, Mapping) else None
    if not isinstance(region, str) or not region:
        raise ModelCapacityError("configured AI region is missing")
    deployments = foundation.get("aiDeployments")
    if not isinstance(deployments, list) or len(deployments) != 5:
        raise ModelCapacityError("exactly five configured model deployments are required")

    results = []
    for deployment in deployments:
        if not isinstance(deployment, Mapping):
            raise ModelCapacityError("model deployment configuration is invalid")
        model = {
            "format": deployment.get("format", "OpenAI"),
            "name": deployment.get("model"),
            "version": deployment.get("version"),
        }
        sku = {"name": deployment.get("skuName")}
        capacity = deployment.get("capacity")
        name = deployment.get("name")
        if (
            not all(isinstance(model[key], str) and model[key] for key in model)
            or not isinstance(sku["name"], str)
            or not isinstance(capacity, int)
            or isinstance(capacity, bool)
            or capacity < 1
            or not isinstance(name, str)
        ):
            raise ModelCapacityError("model deployment name, version, SKU, or capacity is invalid")
        response = query(region, {"model": model, "sku": sku})
        properties = response.get("properties") if isinstance(response, Mapping) else None
        available = properties.get("availableCapacity") if isinstance(properties, Mapping) else None
        if available is None and isinstance(response, Mapping):
            available = response.get("availableCapacity")
        if not isinstance(available, int) or isinstance(available, bool) or available < capacity:
            raise ModelCapacityError(
                f"model {name} in {region} needs capacity {capacity}; Azure reports insufficient or unconfirmed capacity"
            )
        results.append({"name": name, "region": region, "capacity": capacity})
    return results


def _azure_query(subscription_id: str, region: str, model: Mapping[str, Any]) -> Mapping[str, Any]:
    endpoint = (
        "https://management.azure.com/subscriptions/"
        f"{quote(subscription_id, safe='')}/providers/Microsoft.CognitiveServices/locations/"
        f"{quote(region, safe='')}/modelCapacities?api-version=2023-05-01"
    )
    body = json.dumps({"model": model["model"], "sku": model["sku"]}, separators=(",", ":"))
    result = subprocess.run(
        ["az", "rest", "--method", "post", "--url", endpoint, "--body", body, "--output", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ModelCapacityError("Azure model availability request failed; confirm SKU, region, and quota")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ModelCapacityError("Azure returned an invalid model capacity response") from error
    if not isinstance(value, Mapping):
        raise ModelCapacityError("Azure returned an invalid model capacity response")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolved-file", required=True, type=Path)
    args = parser.parse_args()
    try:
        resolved = json.loads(args.resolved_file.read_text(encoding="utf-8"))
        results = validate_model_capacity(
            resolved,
            lambda region, model: _azure_query(resolved["subscriptionId"], region, model),
        )
    except (OSError, json.JSONDecodeError, KeyError, ModelCapacityError) as error:
        print(f"model capacity validation failed: {error}", file=sys.stderr)
        return 1
    for result in results:
        print(f"Confirmed {result['name']} capacity {result['capacity']} in {result['region']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
