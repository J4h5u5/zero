"""Hash-chained journal envelopes for tamper-evident runtime evidence.

This module is deliberately offline-first. It can wrap existing JSONL streams
into verifiable envelopes and generate signed root files without mutating live
engine journals. Wiring live writers comes after the verifier is stable.
"""
from __future__ import annotations

import argparse
import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


ZERO_HASH = "sha256:" + ("0" * 64)
JOURNAL_VERSION = "zero.journal.v1"
ROOT_VERSION = "zero.journal_root.v1"


class JournalChainError(ValueError):
    """Raised when a journal stream cannot be parsed or verified."""


@dataclass(frozen=True)
class VerificationResult:
    """Summary returned by verify_chain."""

    stream: str
    count: int
    head_hash: str
    first_ts: str | None
    last_ts: str | None


def canonical_json(value: Any) -> str:
    """Return canonical JSON for stable hashing across runtimes."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(value: bytes | str) -> str:
    """Return a sha256-prefixed hex digest."""
    import hashlib

    raw = value.encode("utf-8") if isinstance(value, str) else value
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def now_utc_iso() -> str:
    """UTC timestamp formatted consistently for journal envelopes."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _entry_hash_body(entry: dict[str, Any]) -> dict[str, Any]:
    """Fields covered by entry_hash and Ed25519 signatures."""
    return {
        key: value
        for key, value in entry.items()
        if key not in {"entry_hash", "signature", "signing_key_id", "signing_public_key_b64"}
    }


def _signature_payload(entry: dict[str, Any]) -> bytes:
    body = dict(_entry_hash_body(entry))
    body["entry_hash"] = entry["entry_hash"]
    body["signing_key_id"] = entry.get("signing_key_id", "")
    body["signing_public_key_b64"] = entry.get("signing_public_key_b64", "")
    return canonical_json(body).encode("utf-8")


def _root_hash_body(root: dict[str, Any]) -> dict[str, Any]:
    """Fields covered by root_hash."""
    return {
        key: value
        for key, value in root.items()
        if key not in {
            "root_hash",
            "signature",
            "signing_key_id",
            "signing_public_key_b64",
            "anchor",
        }
    }


def _root_signature_payload(root: dict[str, Any]) -> bytes:
    """Fields covered by root signatures."""
    body = dict(_root_hash_body(root))
    body["root_hash"] = root["root_hash"]
    body["signing_key_id"] = root.get("signing_key_id", "")
    body["signing_public_key_b64"] = root.get("signing_public_key_b64", "")
    return canonical_json(body).encode("utf-8")


def build_entry(
    payload: dict[str, Any],
    *,
    stream: str,
    seq: int,
    prev_hash: str = ZERO_HASH,
    ts: str | None = None,
    deployment_id: str | None = None,
    event_type: str | None = None,
    signing_key: Ed25519PrivateKey | None = None,
    signing_key_id: str | None = None,
) -> dict[str, Any]:
    """Build a hash-chained envelope for a single journal payload."""
    if seq < 1:
        raise JournalChainError("journal sequence must start at 1")
    if not stream:
        raise JournalChainError("journal stream is required")
    if not prev_hash.startswith("sha256:"):
        raise JournalChainError("prev_hash must be sha256-prefixed")

    entry: dict[str, Any] = {
        "version": JOURNAL_VERSION,
        "seq": seq,
        "ts": ts or now_utc_iso(),
        "stream": stream,
        "deployment_id": deployment_id or "",
        "event_type": event_type or str(payload.get("event") or payload.get("type") or ""),
        "payload_hash": sha256_hex(canonical_json(payload)),
        "prev_hash": prev_hash,
    }
    entry["entry_hash"] = sha256_hex(canonical_json(_entry_hash_body(entry)))

    if signing_key is not None:
        if not signing_key_id:
            raise JournalChainError("signing_key_id is required when signing")
        entry["signing_key_id"] = signing_key_id
        entry["signing_public_key_b64"] = base64.b64encode(
            signing_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ).decode("ascii")
        signature = signing_key.sign(_signature_payload(entry))
        entry["signature"] = base64.b64encode(signature).decode("ascii")

    return entry


def build_chain(
    records: Iterable[dict[str, Any]],
    *,
    stream: str,
    deployment_id: str | None = None,
    start_hash: str = ZERO_HASH,
    signing_key: Ed25519PrivateKey | None = None,
    signing_key_id: str | None = None,
) -> list[dict[str, Any]]:
    """Wrap existing JSON records in a fresh journal chain."""
    chain: list[dict[str, Any]] = []
    prev_hash = start_hash
    for seq, payload in enumerate(records, start=1):
        entry = build_entry(
            payload,
            stream=stream,
            seq=seq,
            prev_hash=prev_hash,
            ts=str(payload.get("ts") or payload.get("timestamp") or now_utc_iso()),
            deployment_id=deployment_id,
            signing_key=signing_key,
            signing_key_id=signing_key_id,
        )
        chain.append(entry)
        prev_hash = entry["entry_hash"]
    return chain


def read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    """Read a JSONL file with line-numbered parse errors."""
    journal_path = Path(path)
    if not journal_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(journal_path.read_text().splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise JournalChainError(f"{journal_path}:{line_no}: invalid JSONL: {exc.msg}") from exc
        if not isinstance(record, dict):
            raise JournalChainError(f"{journal_path}:{line_no}: JSONL record must be an object")
        records.append(record)
    return records


def verify_chain(
    entries: Iterable[dict[str, Any]],
    *,
    stream: str | None = None,
    start_hash: str = ZERO_HASH,
    public_keys: dict[str, Ed25519PublicKey] | None = None,
) -> VerificationResult:
    """Verify sequence, linkage, hashes, and optional Ed25519 signatures."""
    entry_list = list(entries)
    prev_hash = start_hash
    first_ts: str | None = None
    last_ts: str | None = None
    actual_stream = stream or ""

    for expected_seq, entry in enumerate(entry_list, start=1):
        if entry.get("version") != JOURNAL_VERSION:
            raise JournalChainError(f"entry {expected_seq}: unsupported journal version")
        if entry.get("seq") != expected_seq:
            raise JournalChainError(f"entry {expected_seq}: sequence mismatch")
        if stream and entry.get("stream") != stream:
            raise JournalChainError(f"entry {expected_seq}: stream mismatch")
        if entry.get("prev_hash") != prev_hash:
            raise JournalChainError(f"entry {expected_seq}: previous hash mismatch")

        recomputed = sha256_hex(canonical_json(_entry_hash_body(entry)))
        if entry.get("entry_hash") != recomputed:
            raise JournalChainError(f"entry {expected_seq}: entry hash mismatch")

        signing_key_id = entry.get("signing_key_id")
        signature = entry.get("signature")
        public_key_b64 = entry.get("signing_public_key_b64")
        if signing_key_id or signature or public_key_b64:
            if not signing_key_id or not signature:
                raise JournalChainError(f"entry {expected_seq}: incomplete signature fields")
            public_key = None
            if public_key_b64:
                try:
                    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
                except ValueError as exc:
                    raise JournalChainError(f"entry {expected_seq}: invalid public key") from exc
            else:
                public_key = (public_keys or {}).get(signing_key_id)
            if public_key is None:
                raise JournalChainError(f"entry {expected_seq}: missing public key {signing_key_id}")
            try:
                public_key.verify(base64.b64decode(signature), _signature_payload(entry))
            except (InvalidSignature, ValueError) as exc:
                raise JournalChainError(f"entry {expected_seq}: invalid signature") from exc

        actual_stream = str(entry.get("stream") or actual_stream)
        first_ts = first_ts or str(entry.get("ts") or "")
        last_ts = str(entry.get("ts") or "")
        prev_hash = str(entry["entry_hash"])

    return VerificationResult(
        stream=actual_stream or stream or "",
        count=len(entry_list),
        head_hash=prev_hash,
        first_ts=first_ts,
        last_ts=last_ts,
    )


def verify_payload_binding(
    entries: Iterable[dict[str, Any]],
    records: Iterable[dict[str, Any]],
    *,
    stream: str | None = None,
) -> bool:
    """Verify each envelope payload hash still matches its raw JSONL record."""
    entry_list = list(entries)
    record_list = list(records)
    if len(entry_list) != len(record_list):
        raise JournalChainError(
            f"payload binding count mismatch: {len(entry_list)} envelopes for {len(record_list)} records"
        )
    for idx, (entry, record) in enumerate(zip(entry_list, record_list, strict=True), start=1):
        if stream and entry.get("stream") != stream:
            raise JournalChainError(f"entry {idx}: stream mismatch")
        expected = sha256_hex(canonical_json(record))
        if entry.get("payload_hash") != expected:
            raise JournalChainError(f"entry {idx}: payload hash mismatch")
    return True


def generate_root(
    stream_results: Iterable[VerificationResult],
    *,
    generated_at: str | None = None,
    deployment_id: str | None = None,
    signing_key: Ed25519PrivateKey | None = None,
    signing_key_id: str | None = None,
) -> dict[str, Any]:
    """Generate a daily root object from verified stream summaries."""
    streams = [
        {
            "stream": result.stream,
            "count": result.count,
            "head_hash": result.head_hash,
            "first_ts": result.first_ts,
            "last_ts": result.last_ts,
        }
        for result in stream_results
    ]
    root: dict[str, Any] = {
        "version": ROOT_VERSION,
        "generated_at": generated_at or now_utc_iso(),
        "deployment_id": deployment_id or "",
        "streams": sorted(streams, key=lambda item: item["stream"]),
    }
    root["root_hash"] = sha256_hex(canonical_json(_root_hash_body(root)))
    if signing_key is not None:
        sign_root(root, signing_key=signing_key, signing_key_id=signing_key_id)
    return root


def sign_root(
    root: dict[str, Any],
    *,
    signing_key: Ed25519PrivateKey,
    signing_key_id: str | None,
) -> dict[str, Any]:
    """Sign a journal root after any metadata fields have been attached."""
    if not signing_key_id:
        raise JournalChainError("signing_key_id is required when signing root")
    root.pop("signature", None)
    root["signing_key_id"] = signing_key_id
    root["signing_public_key_b64"] = base64.b64encode(
        signing_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode("ascii")
    root["root_hash"] = sha256_hex(canonical_json(_root_hash_body(root)))
    root["signature"] = base64.b64encode(signing_key.sign(_root_signature_payload(root))).decode("ascii")
    return root


def verify_root(
    root: dict[str, Any],
    *,
    public_keys: dict[str, Ed25519PublicKey] | None = None,
) -> bool:
    """Verify a root hash and optional Ed25519 signature."""
    if root.get("version") != ROOT_VERSION:
        raise JournalChainError("unsupported journal root version")
    recomputed = sha256_hex(canonical_json(_root_hash_body(root)))
    if root.get("root_hash") != recomputed:
        raise JournalChainError("root hash mismatch")

    signature = root.get("signature")
    signing_key_id = root.get("signing_key_id")
    public_key_b64 = root.get("signing_public_key_b64")
    if not signature and not signing_key_id and not public_key_b64:
        return True
    if not signature or not signing_key_id:
        raise JournalChainError("incomplete root signature fields")

    public_key = None
    if public_key_b64:
        try:
            public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        except ValueError as exc:
            raise JournalChainError("invalid root public key") from exc
    else:
        public_key = (public_keys or {}).get(str(signing_key_id))
    if public_key is None:
        raise JournalChainError(f"missing root public key {signing_key_id}")
    try:
        public_key.verify(base64.b64decode(signature), _root_signature_payload(root))
    except (InvalidSignature, ValueError) as exc:
        raise JournalChainError("invalid root signature") from exc
    return True


def _json_default(value: Any) -> Any:
    if isinstance(value, VerificationResult):
        return value.__dict__
    raise TypeError(f"object of type {type(value).__name__} is not JSON serializable")


def _cmd_wrap(args: argparse.Namespace) -> int:
    records = read_jsonl(args.input)
    chain = build_chain(records, stream=args.stream, deployment_id=args.deployment_id)
    payload = "\n".join(canonical_json(entry) for entry in chain)
    if payload:
        payload += "\n"
    if args.output:
        Path(args.output).write_text(payload)
    else:
        print(payload, end="")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    entries = read_jsonl(args.input)
    result = verify_chain(entries, stream=args.stream or None)
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0


def _cmd_root(args: argparse.Namespace) -> int:
    entries = read_jsonl(args.input)
    result = verify_chain(entries, stream=args.stream or None)
    root = generate_root([result], deployment_id=args.deployment_id)
    if args.output:
        Path(args.output).write_text(json.dumps(root, indent=2, sort_keys=True))
    else:
        print(json.dumps(root, indent=2, sort_keys=True, default=_json_default))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ZERO journal hash-chain tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    wrap = subparsers.add_parser("wrap", help="wrap raw JSONL records into journal envelopes")
    wrap.add_argument("--input", required=True, type=Path)
    wrap.add_argument("--output", type=Path)
    wrap.add_argument("--stream", required=True)
    wrap.add_argument("--deployment-id", default="")
    wrap.set_defaults(func=_cmd_wrap)

    verify = subparsers.add_parser("verify", help="verify journal envelope JSONL")
    verify.add_argument("--input", required=True, type=Path)
    verify.add_argument("--stream", default="")
    verify.set_defaults(func=_cmd_verify)

    root = subparsers.add_parser("root", help="generate a root from a verified envelope JSONL")
    root.add_argument("--input", required=True, type=Path)
    root.add_argument("--output", type=Path)
    root.add_argument("--stream", default="")
    root.add_argument("--deployment-id", default="")
    root.set_defaults(func=_cmd_root)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
