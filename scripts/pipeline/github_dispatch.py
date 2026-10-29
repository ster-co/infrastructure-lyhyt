"""Dispatch and track a pinned app-only release in the SDB repository."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class GitHubDispatchError(RuntimeError):
    """Raised when dispatch or completion of the app-only workflow fails."""


def dispatch_title(source_run_id: str, customer_id: str, environment: str, operation: str, release_version: str) -> str:
    return f"lifecycle/{source_run_id}/{customer_id}/{environment}/{operation}/{release_version}"


def _request_json(
    token: str,
    method: str,
    url: str,
    body: Mapping[str, Any] | None = None,
    opener: Callable[..., Any] = urlopen,
) -> tuple[int, Any]:
    data = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Content-Type": "application/json"} if data is not None else {}),
        },
    )
    try:
        with opener(request, timeout=30) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        raise GitHubDispatchError("GitHub App dispatch/status request failed") from None


def dispatch_and_wait(
    *,
    token: str,
    repository: str,
    workflow: str,
    ref: str,
    inputs: Mapping[str, str],
    expected_title: str,
    timeout_seconds: int = 4 * 60 * 60,
    poll_seconds: int = 15,
    opener: Callable[..., Any] = urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Dispatch, locate the unique run by its run-name, and await completion."""
    if not token:
        raise GitHubDispatchError("GitHub App token is empty")
    if repository != "ster-co/SDB-Calculation-v2":
        raise GitHubDispatchError("app-only workflow repository is not allowlisted")
    if workflow != "deploy_app_only.yml":
        raise GitHubDispatchError("workflow is not allowlisted")
    if not ref.startswith("stamp-v") or not expected_title:
        raise GitHubDispatchError("app-only workflow ref or run title is invalid")
    if timeout_seconds < 1 or poll_seconds < 1:
        raise GitHubDispatchError("workflow polling interval is invalid")

    owner, repo = repository.split("/", 1)
    root = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}"
    dispatch_url = f"{root}/actions/workflows/{quote(workflow)}/dispatches"
    status, _ = _request_json(
        token,
        "POST",
        dispatch_url,
        {"ref": ref, "inputs": dict(inputs)},
        opener,
    )
    if status != 204:
        raise GitHubDispatchError(f"GitHub rejected workflow dispatch with HTTP {status}")

    runs_url = f"{root}/actions/workflows/{quote(workflow)}/runs?event=workflow_dispatch&per_page=50"
    deadline = time.monotonic() + timeout_seconds
    run: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        status, payload = _request_json(token, "GET", runs_url, opener=opener)
        if status != 200 or not isinstance(payload, Mapping):
            raise GitHubDispatchError("GitHub workflow status response is invalid")
        runs = payload.get("workflow_runs")
        if not isinstance(runs, list):
            raise GitHubDispatchError("GitHub workflow run list is invalid")
        matches = [
            item for item in runs
            if isinstance(item, dict) and item.get("display_title") == expected_title
        ]
        if len(matches) > 1:
            raise GitHubDispatchError("multiple app-only workflow runs match this lifecycle request")
        if matches:
            run = matches[0]
            if run.get("status") == "completed":
                if run.get("conclusion") != "success":
                    raise GitHubDispatchError(
                        f"app-only workflow completed with conclusion {run.get('conclusion') or 'unknown'}"
                    )
                return {
                    "runId": run.get("id"),
                    "htmlUrl": run.get("html_url"),
                    "status": "success",
                    "title": expected_title,
                }
        sleep(poll_seconds)
    if run and isinstance(run.get("html_url"), str):
        raise GitHubDispatchError(
            f"app-only workflow did not finish before timeout: {run['html_url']}"
        )
    raise GitHubDispatchError("app-only workflow run could not be located before timeout")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="ster-co/SDB-Calculation-v2")
    parser.add_argument("--workflow", default="deploy_app_only.yml")
    parser.add_argument("--ref", required=True)
    parser.add_argument("--inputs-file", required=True)
    parser.add_argument("--expected-title", required=True)
    parser.add_argument("--output-file", required=True)
    args = parser.parse_args()
    try:
        inputs = json.loads(open(args.inputs_file, encoding="utf-8").read())
        result = dispatch_and_wait(
            token=os.environ.get("SDB_GITHUB_TOKEN", ""),
            repository=args.repository,
            workflow=args.workflow,
            ref=args.ref,
            inputs=inputs,
            expected_title=args.expected_title,
        )
        with open(args.output_file, "w", encoding="utf-8") as output:
            json.dump(result, output, separators=(",", ":"))
            output.write("\n")
    except (OSError, json.JSONDecodeError, GitHubDispatchError) as error:
        print(f"app-only release dispatch failed: {error}", file=sys.stderr)
        return 1
    print(f"App-only release succeeded: {result['htmlUrl']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
