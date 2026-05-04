#!/usr/bin/env python3
"""Generate and verify ZERO's MCP Registry submission packet."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SERVER_JSON = ROOT / "server.json"
PACKET_JSON = ROOT / "contracts" / "distribution" / "mcp-registry.json"
SCHEMA_VERSION = "zero.mcp_registry_packet.v1"
MCP_SCHEMA = "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
GENERATED_AT = "2026-05-04T00:00:00Z"
SERVER_NAME = "io.github.zero-intel/zero"
REPOSITORY_ID = "1226608140"


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def build_server_json() -> dict[str, Any]:
    project = load_toml(ROOT / "engine" / "pyproject.toml")["project"]
    version = str(project["version"])
    return {
        "$schema": MCP_SCHEMA,
        "_meta": {
            "io.modelcontextprotocol.registry/publisher-provided": {
                "defaultMode": "paper",
                "submissionState": "ready-after-pypi-publication",
                "safetyClass": "read-only-public",
                "sourceCommitPolicy": "release-tagged",
                "verificationCommands": [
                    "PYTHONPATH=$PWD/engine/src python3 -m zero_engine.mcp --smoke",
                    "PYTHONPATH=$PWD/engine/src scripts/mcp_transcript.py --check",
                    "scripts/mcp_registry_packet.py --check",
                ],
            }
        },
        "description": "Read-only MCP inspection for ZERO paper autonomous onchain operations.",
        "name": SERVER_NAME,
        "packages": [
            {
                "identifier": str(project["name"]),
                "registryType": "pypi",
                "transport": {"type": "stdio"},
                "version": version,
            }
        ],
        "repository": {
            "id": REPOSITORY_ID,
            "source": "github",
            "url": "https://github.com/zero-intel/zero",
        },
        "title": "ZERO MCP",
        "version": version,
        "websiteUrl": "https://getzero.dev",
    }


def _server_json_findings(server: dict[str, Any]) -> dict[str, bool | str]:
    project = load_toml(ROOT / "engine" / "pyproject.toml")["project"]
    engine_readme = text("engine/README.md")
    transcript = text("docs/mcp/transcript.jsonl")
    mcp_docs = text("docs/mcp.md")
    distribution_packet = json.loads(text("contracts/distribution/registry-launch.json"))
    package = server["packages"][0]
    name_pattern = re.compile(r"^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$")

    return {
        "schema_version": SCHEMA_VERSION,
        "server_json_schema_current": server.get("$schema") == MCP_SCHEMA,
        "server_name_uses_github_org_namespace": server.get("name") == SERVER_NAME,
        "server_name_matches_registry_pattern": bool(name_pattern.fullmatch(str(server.get("name")))),
        "server_version_matches_engine_package": server.get("version") == project["version"],
        "package_identifier_matches_pyproject": package.get("identifier") == project["name"],
        "package_version_matches_server": package.get("version") == server.get("version"),
        "package_transport_is_stdio": package.get("transport") == {"type": "stdio"},
        "pyproject_exposes_zero_mcp": project.get("scripts", {}).get("zero-mcp") == "zero_engine.mcp:main",
        "pypi_readme_has_mcp_name": f"mcp-name: {SERVER_NAME}" in engine_readme,
        "mcp_docs_state_read_only": "read-only" in mcp_docs and "canPlaceOrders=false" in mcp_docs,
        "transcript_has_safety_catalog": "zero_get_safety_catalog" in transcript,
        "transcript_has_no_order_placing_tool": '"canPlaceOrders":true' not in transcript,
        "package_registry_publication_still_blocked": not distribution_packet["summary"]["package_registries_enabled"],
    }


def build_packet() -> dict[str, Any]:
    server = build_server_json()
    checks = _server_json_findings(server)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": GENERATED_AT,
        "official_registry": {
            "api": "https://registry.modelcontextprotocol.io",
            "server_schema": MCP_SCHEMA,
            "server_name": SERVER_NAME,
            "query_command": (
                "curl -fsS "
                "'https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.zero-intel/zero'"
            ),
            "last_query_evidence": {
                "checked_at": "2026-05-04T05:08:00Z",
                "response": {"servers": [], "metadata": {"count": 0}},
                "interpretation": "not listed yet; expected until the PyPI package is publicly published",
            },
        },
        "submission": {
            "status": "ready_after_pypi_publication",
            "server_json": "server.json",
            "package_registry": "pypi",
            "package_identifier": "zero-engine",
            "auth_method": "github-oidc",
            "publish_commands": [
                "mcp-publisher login github-oidc",
                "mcp-publisher publish",
            ],
            "blocked_until": [
                "zero-engine is published on PyPI with the engine README carrying the mcp-name proof",
                "release workflow explicitly enables package publication for the target release",
                "maintainer-owned GitHub OIDC publish run records registry output",
            ],
        },
        "server_json": server,
        "checks": checks,
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(payload), encoding="utf-8")


def _check(path: Path, expected: dict[str, Any]) -> int:
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    rendered = canonical_json(expected)
    if current == rendered:
        return 0
    diff = difflib.unified_diff(
        current.splitlines(),
        rendered.splitlines(),
        fromfile=str(path.relative_to(ROOT)),
        tofile="generated",
        lineterm="",
    )
    print("\n".join(list(diff)[:200]), file=sys.stderr)
    print(f"{path.relative_to(ROOT)} is stale; run scripts/mcp_registry_packet.py --output", file=sys.stderr)
    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", action="store_true", help="write server.json and packet JSON")
    parser.add_argument("--check", action="store_true", help="fail if committed files are stale")
    parser.add_argument("--json", action="store_true", help="print the packet JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = build_server_json()
    packet = build_packet()

    if args.output:
        _write(SERVER_JSON, server)
        _write(PACKET_JSON, packet)

    if args.check:
        failed = _check(SERVER_JSON, server) | _check(PACKET_JSON, packet)
        failed_checks = [name for name, ok in packet["checks"].items() if isinstance(ok, bool) and not ok]
        if failed_checks:
            print(f"MCP registry packet checks failed: {', '.join(failed_checks)}", file=sys.stderr)
            failed = 1
        if failed:
            return 1

    if args.json or (not args.output and not args.check):
        print(canonical_json(packet), end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
