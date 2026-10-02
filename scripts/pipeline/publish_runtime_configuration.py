"""Publish safe runtime configuration to the per-customer runtime vault."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.pipeline.runtime_configuration import (
    AzureCliSecretPublisher,
    build_runtime_configuration,
    publish_runtime_configuration,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--foundation-outputs", required=True, type=Path)
    parser.add_argument("--runtime-outputs", required=True, type=Path)
    parser.add_argument("--customer-tenant-id", required=True)
    parser.add_argument("--vault-name", required=True)
    args = parser.parse_args()

    try:
        foundation_outputs = json.loads(
            args.foundation_outputs.read_text(encoding="utf-8")
        )
        runtime_outputs = json.loads(args.runtime_outputs.read_text(encoding="utf-8"))
        values = build_runtime_configuration(
            foundation_outputs, runtime_outputs, args.customer_tenant_id
        )
        result = publish_runtime_configuration(
            values, AzureCliSecretPublisher(args.vault_name)
        )
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as error:
        print(f"publish_runtime_configuration: {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "created": result.created,
                "updated": result.updated,
                "unchanged": result.unchanged,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
