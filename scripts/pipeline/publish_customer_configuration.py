"""Publish safe customer-foundation outputs to a customer Key Vault."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.pipeline.customer_configuration import (
    AzureCliSecretPublisher,
    extract_customer_configuration,
    publish_customer_configuration,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outputs", required=True, type=Path)
    parser.add_argument("--vault-name", required=True)
    parser.add_argument(
        "--allow-update",
        action="store_true",
        help="explicitly approve replacing operator-managed drift",
    )
    args = parser.parse_args()

    try:
        raw_outputs = json.loads(args.outputs.read_text(encoding="utf-8"))
        values = extract_customer_configuration(raw_outputs)
        result = publish_customer_configuration(
            values,
            AzureCliSecretPublisher(args.vault_name),
            allow_updates=args.allow_update,
        )
    except (OSError, json.JSONDecodeError, ValueError, RuntimeError) as error:
        print(f"publish_customer_configuration: {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "created": result.created,
                "unchanged": result.unchanged,
                "updated": result.updated,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
