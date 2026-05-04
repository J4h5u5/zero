#!/usr/bin/env python3
"""Generate and verify ZERO's Railway template launch packet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "contracts" / "distribution" / "railway-template.json"
SCHEMA_VERSION = "zero.railway_template_packet.v1"
GENERATED_AT = "2026-05-04T18:40:00Z"
PUBLIC_DEMO_URL = "https://zero-production-5214.up.railway.app"


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def file_exists(path: str) -> bool:
    return (ROOT / path).is_file()


def build_packet() -> dict[str, Any]:
    readme = text("README.md")
    template_docs = text("docs/railway-template.md")
    deploy_docs = text("docs/railway-deploy.md")
    railway_toml = text("railway.toml")
    dockerfile = text("Dockerfile")
    start_script = text("scripts/railway_start.sh")

    checks = {
        "schema_version": SCHEMA_VERSION,
        "readme_names_live_demo": PUBLIC_DEMO_URL in readme,
        "readme_names_railway_template_docs": "docs/railway-template.md" in readme,
        "template_docs_name_public_demo": PUBLIC_DEMO_URL in template_docs,
        "template_docs_name_partner_publish_step": "Railway Template Publish Packet" in template_docs,
        "deploy_docs_name_doctor": "scripts/railway_doctor.py" in deploy_docs,
        "dockerfile_present": file_exists("Dockerfile"),
        "railway_toml_present": file_exists("railway.toml"),
        "start_script_present": file_exists("scripts/railway_start.sh"),
        "dockerfile_installs_engine": "python -m pip install --no-cache-dir /app/engine"
        in dockerfile,
        "railway_uses_dockerfile": 'builder = "DOCKERFILE"' in railway_toml,
        "railway_healthcheck_configured": 'healthcheckPath = "/health"' in railway_toml,
        "railway_start_uses_port": 'PORT="${PORT:-8765}"' in start_script,
        "railway_start_uses_durable_journal": (
            'ZERO_JOURNAL_PATH="${ZERO_JOURNAL_PATH:-/data/decisions.jsonl}"' in start_script
        ),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": GENERATED_AT,
        "summary": {
            "status": "ready_for_marketplace_publish",
            "public_demo_url": PUBLIC_DEMO_URL,
            "template_name": "ZERO Paper Runtime",
            "workspace": "zero",
            "project": "fabulous-enchantment",
            "service": "zero",
            "environment": "production",
            "latest_verified_deployment": "4eb07a77-9fc1-4e68-b5ca-6de75057fa3d",
            "latest_evidence_bundle": "artifacts/deployment-evidence/20260504T183948Z",
            "doctor_summary": {"ok": 17, "warn": 1, "fail": 0},
            "evidence_verify": {"ok": True, "checks": 60, "fail": 0},
        },
        "runtime": {
            "mode": "paper",
            "public_networking": True,
            "journal_volume_mount": "/data",
            "journal_path": "/data/decisions.jsonl",
            "market_data": "Hyperliquid public mids, read-only",
            "live_execution": "refused by default",
            "custody_required": False,
            "exchange_private_keys_required": False,
        },
        "template_variables": {
            "ZERO_MODE": "paper",
            "ZERO_JOURNAL_PATH": "/data/decisions.jsonl",
            "ZERO_HYPERLIQUID_LIVE_PRICES": "true",
            "ZERO_INTELLIGENCE_STORE_PATH": "/data/zero/intelligence.jsonl",
            "ZERO_INTELLIGENCE_API_PLAN": "free",
            "ZERO_INTELLIGENCE_API_ACCOUNT_ID": "acct_railway",
            "ZERO_DEPLOYMENT_ID": "zero-railway-public-paper",
        },
        "publish_steps": [
            "Publish the linked Railway project as a template from the Railway dashboard.",
            "Use docs/railway-template.md as the marketplace copy and variable map.",
            "Attach the /data volume before public launch.",
            "Run scripts/railway_doctor.py against the public URL.",
            "Run scripts/deployment_evidence.sh with --railway-logs and verify the bundle.",
            "Replace the README template placeholder with Railway's issued template URL.",
        ],
        "checks": checks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write packet JSON to a file.")
    parser.add_argument("--check", action="store_true", help="Fail if the committed packet is stale.")
    parser.add_argument("--json", action="store_true", help="Print packet JSON.")
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
            raise SystemExit(
                f"{OUTPUT.relative_to(ROOT)} is stale; run "
                f"scripts/railway_template_packet.py --output {OUTPUT.relative_to(ROOT)}"
            )
        failed = [name for name, ok in packet["checks"].items() if isinstance(ok, bool) and not ok]
        if failed:
            raise SystemExit(f"railway template packet checks failed: {', '.join(failed)}")

    if args.json or (not args.output and not args.check):
        print(rendered, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
