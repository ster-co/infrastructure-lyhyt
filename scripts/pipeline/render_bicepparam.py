"""Render deployment parameters as a temporary Bicep parameter file."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def bicep_literal(value: object) -> str:
    """Return a Bicep literal for supported JSON-like values."""
    if value is None:
        raise ValueError("null is not a supported Bicep parameter value")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("non-finite numbers are not supported in Bicep literals")
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(bicep_literal(item) for item in value) + "]"
    if isinstance(value, dict):
        members = []
        for key in value:
            if not isinstance(key, str) or not _IDENTIFIER.fullmatch(key):
                raise ValueError(f"object key must be a Bicep identifier: {key!r}")
        for key in sorted(value):
            members.append(f"{key}: {bicep_literal(value[key])}")
        return "{ " + ", ".join(members) + " }"
    raise TypeError(f"unsupported Bicep parameter value: {type(value).__name__}")


def render_bicepparam(
    output_path: Path, using_path: str, parameters: dict[str, object]
) -> Path:
    """Write sorted parameters to a temporary ``.bicepparam`` file."""
    if not isinstance(using_path, str) or not using_path:
        raise ValueError("using_path must be a non-empty string")
    if not isinstance(parameters, dict):
        raise TypeError("parameters must be a dictionary")
    lines = [f"using {bicep_literal(using_path)}"]
    for name in sorted(parameters):
        if not isinstance(name, str) or not _IDENTIFIER.fullmatch(name):
            raise ValueError(f"parameter name must be a Bicep identifier: {name!r}")
        lines.append(f"param {name} = {bicep_literal(parameters[name])}")
    output_path = Path(output_path)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path
