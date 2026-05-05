#!/usr/bin/env python3
"""Generate and verify ZERO's non-publishing registry launch packet."""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "contracts" / "distribution" / "registry-launch.json"
SCHEMA_VERSION = "zero.registry_launch_packet.v1"
GENERATED_AT = "2026-05-04T00:00:00Z"


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def crate_names() -> list[str]:
    names: list[str] = []
    for manifest in sorted((ROOT / "cli" / "crates").glob("*/Cargo.toml")):
        data = load_toml(manifest)
        names.append(data.get("package", {}).get("name", manifest.parent.name))
    return names


def contains_any(source: str, needles: list[str]) -> bool:
    return any(needle in source for needle in needles)


def build_packet() -> dict[str, Any]:
    pyproject = load_toml(ROOT / "engine" / "pyproject.toml")
    cargo = load_toml(ROOT / "cli" / "Cargo.toml")
    formula = text("Formula/zero.rb")
    release_workflow = text(".github/workflows/release.yml")
    release_docs = text("docs/release.md")
    distribution_docs = text("docs/distribution.md")
    release_evidence = text("docs/releases/v0.1.2-evidence.md")

    project = pyproject["project"]
    workspace_package = cargo["workspace"]["package"]

    publishing_markers = {
        "pypi": ["pypa/gh-action-pypi-publish", "twine upload", "uv publish"],
        "crates": ["cargo publish", "cargo-release"],
        "container": ["docker/login-action", "ghcr.io/", "docker push"],
    }
    forbidden_found = {
        channel: [marker for marker in markers if marker in release_workflow]
        for channel, markers in publishing_markers.items()
    }

    channels = [
        {
            "channel": "github_release",
            "candidate": "zero-intel/zero",
            "status": "published",
            "current_release": "v0.1.2",
            "required_before_enablement": [],
            "evidence": [
                "docs/releases/v0.1.2-evidence.md",
                "Formula/zero.rb",
                ".github/workflows/release.yml",
            ],
        },
        {
            "channel": "homebrew_tap",
            "candidate": "zero-intel/zero",
            "status": "ready",
            "current_release": "v0.1.2",
            "required_before_enablement": [],
            "evidence": ["Formula/zero.rb", "docs/distribution.md", "docs/release.md"],
        },
        {
            "channel": "pypi",
            "candidate": project["name"],
            "status": "published",
            "current_release": "0.1.2",
            "required_before_enablement": [],
            "evidence": [
                "https://pypi.org/project/zero-engine/0.1.2/",
                "scripts/mcp_registry_listing_check.py --require-pypi-published --json",
                "docs/distribution.md",
            ],
        },
        {
            "channel": "crates_io",
            "candidate": ",".join(crate_names()),
            "status": "published",
            "current_release": "0.1.2",
            "required_before_enablement": [],
            "evidence": [
                "https://crates.io/crates/zero-os/0.1.2",
                "cargo install zero-os --version 0.1.2",
                "cargo owner --list zero-os => squaeragent",
                "CRATESIO_API_TOKEN GitHub secret",
                "docs/registry-launch.md",
                "docs/distribution.md",
            ],
        },
        {
            "channel": "container_registry",
            "candidate": "ghcr.io/zero-intel/zero",
            "status": "ready_credentials_pending",
            "current_release": None,
            "required_before_enablement": [
                "GHCR package visibility is public",
                "anonymous docker pull succeeds from a clean machine",
                "package visibility administration path is documented",
            ],
            "evidence": [
                "legacy authenticated smoke: ghcr.io/zero-intel/zero-paper:0.1.2",
                "legacy digest: sha256:1a9c2f0d2388ad117157b86a70d7db1ff78653d1b9e29c9d936c55efe7666de6",
                "legacy workflow: https://github.com/zero-intel/zero/actions/runs/25360430397",
                ".github/workflows/container-publish.yml",
                "docs/registry-launch.md",
                "docs/distribution.md",
            ],
        },
        {
            "channel": "docker_hub",
            "candidate": "getzero/zero",
            "status": "ready_credentials_pending",
            "current_release": None,
            "required_before_enablement": [
                "Docker Hub namespace is maintainer-controlled",
                "Docker Hub token is least-privilege and stored as a GitHub secret",
                "provenance and SBOM are attached or mirrored in release evidence",
                "anonymous docker pull succeeds from a clean machine",
                "rollback/delete procedure documented in release notes",
            ],
            "evidence": [
                "Dockerfile",
                ".github/workflows/container-publish.yml",
                "docs/distribution.md",
                "docs/registry-launch.md",
            ],
        },
    ]

    checks = {
        "schema_version": SCHEMA_VERSION,
        "package_registry_publication_enabled": True,
        "pypi_package_published": True,
        "release_workflow_has_no_pypi_publish": not forbidden_found["pypi"],
        "release_workflow_has_no_cargo_publish": not forbidden_found["crates"],
        "release_workflow_has_no_container_push": not forbidden_found["container"],
        "pypi_candidate_matches_pyproject": project["name"] == "zero-engine",
        "cargo_workspace_version": workspace_package["version"],
        "homebrew_formula_tracks_current_release": (
            'version "0.1.2"' in formula
            and "releases/download/v0.1.2/zero-macos" in formula
            and "releases/download/v0.1.2/zero-linux" in formula
        ),
        "release_evidence_current": (
            "Release tag: `v0.1.2`" in release_evidence
            and "verification.fail=0" in release_evidence
            and "homebrew_formula_matches_committed=true" in release_evidence
        ),
        "docs_name_trusted_publishing": "Trusted Publishing" in distribution_docs,
        "docs_name_cargo_owner": "cargo owner" in distribution_docs,
        "docs_name_registry_rollback": "Registry Rollback" in distribution_docs,
        "docs_release_states_no_registry_publish": contains_any(
            release_docs,
            [
                "does not publish to any",
                "Do not publish package-registry artifacts",
            ],
        ),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": GENERATED_AT,
        "summary": {
            "default_distribution": "GitHub Release, public Homebrew tap, PyPI zero-engine, crates.io zero-os, legacy authenticated GHCR smoke evidence, and Docker Hub/GHCR product-image workflow readiness",
            "package_registries_enabled": True,
            "current_release": "v0.1.2",
            "policy": "PyPI zero-engine is published through Trusted Publishing; crates.io zero-os is published manually with a least-privilege token until tokenless publishing is available; Docker Hub getzero/zero and GHCR ghcr.io/zero-intel/zero are wired but remain credentials-pending until ownership, provenance, anonymous pull, and rollback evidence are recorded.",
        },
        "channels": channels,
        "checks": checks,
        "forbidden_publish_markers_found": forbidden_found,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write the packet to a file")
    parser.add_argument("--check", action="store_true", help="Fail if the committed packet is stale")
    parser.add_argument("--json", action="store_true", help="Print the packet JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_packet()
    rendered = json.dumps(packet, indent=2, sort_keys=True) + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")

    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != rendered:
            raise SystemExit(f"{OUTPUT.relative_to(ROOT)} is stale; run scripts/registry_launch_packet.py --output {OUTPUT.relative_to(ROOT)}")
        failed = [name for name, ok in packet["checks"].items() if isinstance(ok, bool) and not ok]
        if failed:
            raise SystemExit(f"registry launch packet checks failed: {', '.join(failed)}")

    if args.json or (not args.output and not args.check):
        print(rendered, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
