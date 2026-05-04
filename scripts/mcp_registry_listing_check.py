#!/usr/bin/env python3
"""Verify ZERO's Official MCP Registry listing state."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SERVER_JSON = ROOT / "server.json"
PYPROJECT = ROOT / "engine" / "pyproject.toml"
ENGINE_README = ROOT / "engine" / "README.md"
SCHEMA_VERSION = "zero.mcp_registry_listing_check.v1"
REGISTRY_API = "https://registry.modelcontextprotocol.io/v0.1/servers"
PYPI_API = "https://pypi.org/pypi/{package}/json"
PYPI_VERSION_API = "https://pypi.org/pypi/{package}/{version}/json"


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def fetch_json(url: str, timeout: float) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    request = urllib.request.Request(url, headers={"user-agent": "zero-mcp-registry-check/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body), {"ok": True, "status": response.status, "url": url}
    except urllib.error.HTTPError as exc:
        return None, {"ok": False, "status": exc.code, "reason": exc.reason, "url": url}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, {"ok": False, "reason": str(exc), "url": url}


def server_from_listing(item: dict[str, Any]) -> dict[str, Any]:
    server = item.get("server")
    if isinstance(server, dict):
        return server
    return item


def package_from_server(server: dict[str, Any]) -> dict[str, Any]:
    packages = server.get("packages", [])
    if isinstance(packages, list) and packages and isinstance(packages[0], dict):
        return packages[0]
    return {}


def registry_url(server_name: str) -> str:
    query = urllib.parse.urlencode({"search": server_name})
    return f"{REGISTRY_API}?{query}"


def build_report(timeout: float) -> dict[str, Any]:
    server_json = read_json(SERVER_JSON)
    pyproject = load_toml(PYPROJECT)["project"]
    package_name = str(pyproject["name"])
    package_version = str(pyproject["version"])
    server_name = str(server_json["name"])
    package = package_from_server(server_json)

    registry_response, registry_http = fetch_json(registry_url(server_name), timeout)
    pypi_response, pypi_http = fetch_json(PYPI_API.format(package=package_name), timeout)
    pypi_version_response, pypi_version_http = fetch_json(
        PYPI_VERSION_API.format(package=package_name, version=package_version),
        timeout,
    )

    servers = []
    if isinstance(registry_response, dict) and isinstance(registry_response.get("servers"), list):
        servers = [
            server_from_listing(item)
            for item in registry_response["servers"]
            if isinstance(item, dict)
        ]
    matching_servers = [server for server in servers if server.get("name") == server_name]
    listed_server = next(
        (server for server in matching_servers if server.get("version") == server_json.get("version")),
        matching_servers[0] if matching_servers else {},
    )
    listed_package = package_from_server(listed_server)

    pypi_description = ""
    if isinstance(pypi_version_response, dict) and isinstance(
        pypi_version_response.get("info"), dict
    ):
        pypi_description = str(pypi_version_response["info"].get("description", ""))
    elif isinstance(pypi_response, dict) and isinstance(pypi_response.get("info"), dict):
        pypi_description = str(pypi_response["info"].get("description", ""))
    local_readme = ENGINE_README.read_text(encoding="utf-8")
    mcp_name_marker = f"mcp-name: {server_name}"
    release_files = []
    if isinstance(pypi_response, dict) and isinstance(pypi_response.get("releases"), dict):
        release_files = pypi_response["releases"].get(package_version, [])
    pypi_published = bool(pypi_version_response) or bool(release_files)

    checks = {
        "server_json_name_matches_expected": server_name == "io.github.zero-intel/zero",
        "server_json_package_matches_pyproject": package.get("identifier") == package_name,
        "server_json_version_matches_pyproject": server_json.get("version") == package_version,
        "server_json_package_version_matches_pyproject": package.get("version") == package_version,
        "server_json_registry_base_url_is_pypi": package.get("registryBaseUrl") == "https://pypi.org",
        "server_json_runtime_hint_is_uvx": package.get("runtimeHint") == "uvx",
        "server_json_transport_is_stdio": package.get("transport") == {"type": "stdio"},
        "local_readme_has_pypi_mcp_name_marker": mcp_name_marker in local_readme,
        "pypi_package_published": pypi_published,
        "pypi_version_matches_pyproject": pypi_published,
        "pypi_description_has_mcp_name_marker": (
            bool(pypi_description) and mcp_name_marker in pypi_description
        ),
        "official_registry_listed": bool(matching_servers),
        "official_registry_version_matches_server_json": (
            bool(listed_server) and listed_server.get("version") == server_json.get("version")
        ),
        "official_registry_package_matches_server_json": (
            bool(listed_package)
            and listed_package.get("identifier") == package.get("identifier")
            and listed_package.get("version") == package.get("version")
            and listed_package.get("registryType") == package.get("registryType")
        ),
    }

    if checks["official_registry_listed"]:
        status = "listed"
    elif checks["pypi_package_published"]:
        status = "pypi_published_registry_pending"
    else:
        status = "ready_after_pypi_publication"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": status,
        "server_name": server_name,
        "package": {"name": package_name, "version": package_version},
        "registry": {
            "api": REGISTRY_API,
            "http": registry_http,
            "matching_count": len(matching_servers),
            "response_count": (
                registry_response.get("metadata", {}).get("count")
                if isinstance(registry_response, dict)
                else None
            ),
            "listed_server": listed_server,
        },
        "pypi": {
            "api": PYPI_API.format(package=package_name),
            "http": pypi_http,
            "version_api": PYPI_VERSION_API.format(
                package=package_name,
                version=package_version,
            ),
            "version_http": pypi_version_http,
            "published": pypi_published,
            "version": (
                pypi_version_response.get("info", {}).get("version")
                if isinstance(pypi_version_response, dict)
                else pypi_response.get("info", {}).get("version")
                if isinstance(pypi_response, dict)
                else None
            ),
        },
        "checks": checks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Print the listing report JSON")
    parser.add_argument("--write", type=Path, help="Write the listing report JSON to a file")
    parser.add_argument("--expect-listed", action="store_true", help="Fail unless the server is listed")
    parser.add_argument(
        "--require-pypi-published",
        action="store_true",
        help="Fail unless the referenced PyPI package is published and carries the mcp-name marker",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(timeout=args.timeout)
    rendered = canonical_json(report)

    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(rendered, encoding="utf-8")

    if args.json or not args.write:
        print(rendered, end="")

    failed: list[str] = []
    checks = report["checks"]
    always_required = [
        "server_json_name_matches_expected",
        "server_json_package_matches_pyproject",
        "server_json_version_matches_pyproject",
        "server_json_package_version_matches_pyproject",
        "server_json_registry_base_url_is_pypi",
        "server_json_runtime_hint_is_uvx",
        "server_json_transport_is_stdio",
        "local_readme_has_pypi_mcp_name_marker",
    ]
    failed.extend(name for name in always_required if not checks[name])

    if args.require_pypi_published:
        pypi_required = [
            "pypi_package_published",
            "pypi_version_matches_pyproject",
            "pypi_description_has_mcp_name_marker",
        ]
        failed.extend(name for name in pypi_required if not checks[name])

    if args.expect_listed:
        listed_required = [
            "official_registry_listed",
            "official_registry_version_matches_server_json",
            "official_registry_package_matches_server_json",
        ]
        failed.extend(name for name in listed_required if not checks[name])

    if failed:
        print(f"MCP registry listing checks failed: {', '.join(sorted(set(failed)))}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
