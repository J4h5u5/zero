#!/usr/bin/env python3
"""Preflight local Railway CLI readiness for ZERO template operations."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any


SCHEMA_VERSION = "zero.railway_cli_preflight.v1"


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check whether Railway CLI is installed, authenticated, supports "
            "template deployment, and is linked to a project."
        )
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--allow-unauthenticated",
        action="store_true",
        help="Return success when the CLI is installed but auth/linking is pending.",
    )
    return parser.parse_args()


def run(*args: str) -> CommandResult:
    child = subprocess.run(
        ["railway", *args],
        check=False,
        text=True,
        capture_output=True,
        timeout=20,
    )
    return CommandResult(
        ok=child.returncode == 0,
        returncode=child.returncode,
        stdout=child.stdout.strip(),
        stderr=child.stderr.strip(),
    )


def parse_json(raw: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def next_actions(*, authenticated: bool, linked: bool) -> list[str]:
    actions: list[str] = []
    if not authenticated:
        actions.append("Authenticate with `railway login --browserless` or set `RAILWAY_API_TOKEN`.")
    if authenticated and not linked:
        actions.append("Create or link a Railway project with `railway init` or `railway link`.")
    if authenticated and linked:
        actions.append("Run `scripts/railway_doctor.py \"$ZERO_RAILWAY_URL\"` after deployment.")
    return actions


def emit(packet: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(packet, indent=2, sort_keys=True))
        return
    print(f"schema: {packet['schema_version']}")
    print(f"ready: {str(packet['ready']).lower()}")
    for check in packet["checks"]:
        print(f"- {check['name']}: {check['status']} - {check['message']}")
    if packet["next_actions"]:
        print("next:")
        for action in packet["next_actions"]:
            print(f"- {action}")


def main() -> int:
    args = parse_args()
    checks: list[dict[str, Any]] = []

    railway_path = shutil.which("railway")
    if not railway_path:
        packet = {
            "schema_version": SCHEMA_VERSION,
            "ready": False,
            "checks": [
                {
                    "name": "cli_installed",
                    "status": "fail",
                    "message": "Railway CLI is not installed",
                }
            ],
            "next_actions": ["Install Railway CLI with `npm install -g @railway/cli`."],
        }
        emit(packet, args.json)
        return 1

    version = run("--version")
    checks.append(
        {
            "name": "cli_installed",
            "status": "ok" if version.ok else "fail",
            "message": version.stdout or version.stderr,
            "path": railway_path,
        }
    )

    deploy_help = run("deploy", "--help")
    deploy_supported = deploy_help.ok and "--template" in deploy_help.stdout
    checks.append(
        {
            "name": "template_deploy_supported",
            "status": "ok" if deploy_supported else "fail",
            "message": "`railway deploy --template` is available"
            if deploy_supported
            else "Railway CLI does not expose template deploy support",
        }
    )

    whoami = run("whoami", "--json")
    whoami_payload = parse_json(whoami.stdout)
    authenticated = whoami.ok and whoami_payload is not None
    checks.append(
        {
            "name": "authenticated",
            "status": "ok" if authenticated else "fail",
            "message": "Railway account is authenticated"
            if authenticated
            else "Railway CLI is not authenticated",
            "user": whoami_payload,
        }
    )

    status = run("status", "--json")
    status_payload = parse_json(status.stdout)
    linked = status.ok and status_payload is not None
    checks.append(
        {
            "name": "project_linked",
            "status": "ok" if linked else "warn",
            "message": "Current directory is linked to a Railway project"
            if linked
            else "Current directory is not linked to a Railway project",
            "project": status_payload,
        }
    )

    blocking_failures = [
        check
        for check in checks
        if check["status"] == "fail"
        and not (args.allow_unauthenticated and check["name"] == "authenticated")
    ]
    ready = not blocking_failures and linked
    if args.allow_unauthenticated and not authenticated:
        ready = False

    packet = {
        "schema_version": SCHEMA_VERSION,
        "ready": ready,
        "checks": checks,
        "next_actions": next_actions(authenticated=authenticated, linked=linked),
    }
    emit(packet, args.json)
    if ready or args.allow_unauthenticated:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
