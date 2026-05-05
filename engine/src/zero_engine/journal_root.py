"""Daily journal root generation for ZERO runtime streams."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

from zero_engine.journal_anchor import anchor_root_file
from zero_engine.journal_chain import (
    JournalChainError,
    build_chain,
    canonical_json,
    generate_root,
    read_jsonl,
    sha256_hex,
    sign_root,
    verify_root,
    verify_chain,
    verify_payload_binding,
)
from zero_engine.journal_sidecar import sidecar_path_for
from zero_engine.journal_signing import load_signing_key_from_env

BUS_DIR = Path(".zero/bus")
DATA_DIR = Path(".zero/data")


@dataclass(frozen=True)
class StreamSpec:
    """A raw JSONL stream that can be reduced into a journal root."""

    name: str
    path: Path


def parse_day(value: str | None = None) -> date:
    """Parse a YYYY-MM-DD day or return today's UTC date."""
    if not value:
        return datetime.now(timezone.utc).date()
    return date.fromisoformat(value)


def default_stream_specs(
    *,
    bus_dir: Path = BUS_DIR,
    data_dir: Path = DATA_DIR,
    day: date | None = None,
) -> list[StreamSpec]:
    """Return the standard local engine streams for a daily root."""
    root_day = day or datetime.now(timezone.utc).date()
    return [
        StreamSpec("trades", data_dir / "trades.jsonl"),
        StreamSpec("events", bus_dir / "events.jsonl"),
        StreamSpec("decisions", bus_dir / "decisions.jsonl"),
        StreamSpec("rejections", bus_dir / "rejections.jsonl"),
        StreamSpec("near_misses", bus_dir / "near_misses.jsonl"),
        StreamSpec("genesis", bus_dir / "genesis" / f"{root_day.isoformat()}.jsonl"),
    ]


def build_daily_root(
    *,
    streams: Iterable[StreamSpec],
    generated_at: str | None = None,
    deployment_id: str | None = None,
    sign_from_env: bool = True,
) -> dict:
    """Build a root hash over every existing non-empty raw stream."""
    results = []
    sources = []
    for spec in streams:
        records = read_jsonl(spec.path)
        if not records:
            continue
        sidecar_path = sidecar_path_for(spec.path, spec.name)
        sidecar_entries = read_jsonl(sidecar_path)
        proof_source = "derived_raw"
        if sidecar_entries and len(sidecar_entries) == len(records):
            result = verify_chain(sidecar_entries, stream=spec.name)
            verify_payload_binding(sidecar_entries, records, stream=spec.name)
            proof_source = "live_sidecar"
        else:
            chain = build_chain(records, stream=spec.name, deployment_id=deployment_id)
            result = verify_chain(chain, stream=spec.name)
            if sidecar_entries:
                proof_source = "derived_raw_sidecar_partial"
        results.append(result)
        sources.append({
            "stream": spec.name,
            "path": str(spec.path),
            "records": result.count,
            "head_hash": result.head_hash,
            "proof_source": proof_source,
            "sidecar_path": str(sidecar_path),
            "sidecar_records": len(sidecar_entries),
        })

    signer = load_signing_key_from_env() if sign_from_env else None
    root = generate_root(results, generated_at=generated_at, deployment_id=deployment_id)
    # Source metadata is intentionally covered by a second hash so operators can
    # audit which local files were included without changing the journal root
    # format consumed by public proof pages.
    root["source_manifest"] = sources
    root["source_manifest_hash"] = sha256_hex(canonical_json(sources))
    root["root_hash"] = sha256_hex(canonical_json({
        key: value
        for key, value in root.items()
        if key not in {"root_hash", "signature", "signing_key_id", "signing_public_key_b64", "anchor"}
    }))
    if signer:
        sign_root(root, signing_key=signer.private_key, signing_key_id=signer.key_id)
    verify_root(root)
    return root


def write_daily_root(
    *,
    bus_dir: Path = BUS_DIR,
    data_dir: Path = DATA_DIR,
    output_dir: Path | None = None,
    day: date | None = None,
    deployment_id: str | None = None,
    sign_from_env: bool = True,
    anchor: bool = True,
    anchor_provider: str | None = None,
) -> Path:
    """Write journal-root-YYYY-MM-DD.json and return its path."""
    root_day = day or datetime.now(timezone.utc).date()
    target_dir = output_dir or (data_dir / "journal-roots")
    target_dir.mkdir(parents=True, exist_ok=True)
    root = build_daily_root(
        streams=default_stream_specs(bus_dir=bus_dir, data_dir=data_dir, day=root_day),
        deployment_id=deployment_id,
        sign_from_env=sign_from_env,
    )
    out_path = target_dir / f"journal-root-{root_day.isoformat()}.json"
    out_path.write_text(json.dumps(root, indent=2, sort_keys=True) + "\n")
    if anchor:
        anchor_root_file(
            out_path,
            provider=anchor_provider,
            receipt_dir=target_dir.parent / "journal-anchors",
            day=root_day.isoformat(),
        )
    return out_path


def _cmd_generate(args: argparse.Namespace) -> int:
    try:
        out_path = write_daily_root(
            bus_dir=args.bus_dir,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            day=parse_day(args.day),
            deployment_id=args.deployment_id,
            sign_from_env=not args.no_sign_env,
            anchor=not args.no_anchor,
            anchor_provider=args.anchor_provider,
        )
    except JournalChainError as exc:
        raise SystemExit(f"journal root generation failed: {exc}") from exc
    print(str(out_path))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate ZERO daily journal roots")
    parser.add_argument("--bus-dir", type=Path, default=BUS_DIR)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--day", help="UTC day in YYYY-MM-DD format")
    parser.add_argument("--deployment-id", default="")
    parser.add_argument(
        "--no-sign-env",
        action="store_true",
        help="do not sign with ZERO_JOURNAL_SIGNING_KEY_B64 even if present",
    )
    parser.add_argument("--anchor-provider", default=None, help="local, webhook, or none")
    parser.add_argument("--no-anchor", action="store_true", help="do not attach anchor metadata")
    parser.set_defaults(func=_cmd_generate)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
