"""Public proof-pack generation for signed journal roots."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zero_engine.journal_chain import JournalChainError, canonical_json, sha256_hex, verify_root


PROOF_PACK_VERSION = "zero.proof_pack.v1"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _redacted_source_manifest(root: dict[str, Any]) -> list[dict[str, Any]]:
    """Return source metadata without local filesystem paths."""
    out = []
    for source in root.get("source_manifest", []):
        out.append({
            "stream": source.get("stream", ""),
            "records": int(source.get("records", 0) or 0),
            "sidecar_records": int(source.get("sidecar_records", 0) or 0),
            "proof_source": source.get("proof_source", ""),
            "head_hash": source.get("head_hash", ""),
        })
    return sorted(out, key=lambda item: item["stream"])


def build_public_proof(root: dict[str, Any], *, root_file_name: str = "") -> dict[str, Any]:
    """Build a public-safe proof object from a journal root."""
    verify_root(root)
    streams = [
        {
            "stream": item.get("stream", ""),
            "count": int(item.get("count", 0) or 0),
            "head_hash": item.get("head_hash", ""),
            "first_ts": item.get("first_ts"),
            "last_ts": item.get("last_ts"),
        }
        for item in root.get("streams", [])
    ]
    anchor = root.get("anchor", {}) if isinstance(root.get("anchor"), dict) else {}
    proof = {
        "version": PROOF_PACK_VERSION,
        "generated_at": now_utc_iso(),
        "root_file": root_file_name,
        "root_version": root.get("version", ""),
        "root_generated_at": root.get("generated_at", ""),
        "root_hash": root.get("root_hash", ""),
        "root_signature": root.get("signature", ""),
        "root_signature_hash": sha256_hex(str(root.get("signature", ""))),
        "signing_key_id": root.get("signing_key_id", ""),
        "signing_public_key_b64": root.get("signing_public_key_b64", ""),
        "source_manifest_hash": root.get("source_manifest_hash", ""),
        "streams": sorted(streams, key=lambda item: item["stream"]),
        "sources": _redacted_source_manifest(root),
        "anchor": {
            "version": anchor.get("version", ""),
            "provider": anchor.get("provider", ""),
            "status": anchor.get("status", ""),
            "anchored_at": anchor.get("anchored_at", ""),
            "receipt_hash": anchor.get("receipt_hash", ""),
            "ots_proof_hash": anchor.get("ots_proof_hash", ""),
            "calendar_url": anchor.get("calendar_url", ""),
        },
    }
    proof["proof_hash"] = sha256_hex(canonical_json(proof))
    return proof


def render_markdown(proof: dict[str, Any]) -> str:
    """Render a public proof pack as Markdown."""
    lines = [
        "# ZERO Proof Pack",
        "",
        f"- Version: `{proof['version']}`",
        f"- Root file: `{proof.get('root_file', '')}`",
        f"- Root generated: `{proof.get('root_generated_at', '')}`",
        f"- Root hash: `{proof.get('root_hash', '')}`",
        f"- Root signature hash: `{proof.get('root_signature_hash', '')}`",
        f"- Signing key id: `{proof.get('signing_key_id', '')}`",
        f"- Source manifest hash: `{proof.get('source_manifest_hash', '')}`",
        f"- Proof hash: `{proof.get('proof_hash', '')}`",
        "",
        "## Anchor",
        "",
        f"- Provider: `{proof.get('anchor', {}).get('provider', '')}`",
        f"- Status: `{proof.get('anchor', {}).get('status', '')}`",
        f"- Anchored at: `{proof.get('anchor', {}).get('anchored_at', '')}`",
        f"- Receipt hash: `{proof.get('anchor', {}).get('receipt_hash', '')}`",
        "",
        "## Streams",
        "",
        "| Stream | Records | Proof source | Sidecar records | Head hash |",
        "|---|---:|---|---:|---|",
    ]
    source_by_stream = {item["stream"]: item for item in proof.get("sources", [])}
    for stream in proof.get("streams", []):
        source = source_by_stream.get(stream["stream"], {})
        lines.append(
            f"| `{stream['stream']}` | {stream['count']} | "
            f"`{source.get('proof_source', '')}` | {source.get('sidecar_records', 0)} | "
            f"`{stream['head_hash']}` |"
        )
    lines.extend([
        "",
        "## Verification",
        "",
        "This proof pack contains no raw trade rows. It proves stream counts, stream head hashes,",
        "the signed root hash, and the timestamp-anchor receipt metadata available at generation time.",
        "The full root JSON is required for independent signature verification.",
        "",
    ])
    return "\n".join(lines)


def write_proof_pack(root_path: Path | str, *, output_dir: Path | str) -> tuple[Path, Path]:
    """Write public-proof JSON and Markdown files for a root."""
    root_file = Path(root_path)
    root = json.loads(root_file.read_text())
    proof = build_public_proof(root, root_file_name=root_file.name)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    stem = root_file.stem.replace("journal-root-", "proof-pack-")
    json_path = target / f"{stem}.json"
    md_path = target / f"{stem}.md"
    json_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    md_path.write_text(render_markdown(proof))
    return json_path, md_path


def _cmd_generate(args: argparse.Namespace) -> int:
    try:
        json_path, md_path = write_proof_pack(args.root, output_dir=args.output_dir)
    except (json.JSONDecodeError, OSError, JournalChainError) as exc:
        raise SystemExit(f"proof pack generation failed: {exc}") from exc
    print(json.dumps({"json": str(json_path), "markdown": str(md_path)}, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate public ZERO proof packs")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.set_defaults(func=_cmd_generate)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
