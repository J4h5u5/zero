"""Sidecar hash-chain writer for live JSONL streams.

The sidecar writer never changes the raw stream format. For each appended raw
record it appends a signed envelope to a sibling chain file that can be verified
without exposing payload contents in logs.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zero_engine.journal_chain import (
    JournalChainError,
    ZERO_HASH,
    build_entry,
    read_jsonl,
    verify_chain,
    verify_payload_binding,
)
from zero_engine.journal_signing import load_signing_key_from_env


def sidecar_path_for(raw_path: Path | str, stream: str) -> Path:
    """Return the sidecar path for a raw JSONL stream."""
    raw = Path(raw_path)
    safe_stream = stream.replace("/", "_")
    return raw.parent / "journal-chains" / f"{raw.stem}.{safe_stream}.chain.jsonl"


def _record_ts(record: dict[str, Any]) -> str | None:
    raw_ts = record.get("ts") or record.get("timestamp") or record.get("exit_time") or record.get("entry_time")
    return str(raw_ts) if raw_ts else None


def _read_last_jsonl_record(path: Path) -> dict[str, Any] | None:
    """Read the last non-empty JSONL object without scanning the whole file."""
    if not path.exists() or path.stat().st_size == 0:
        return None
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        pos = handle.tell()
        chunk = b""
        while pos > 0:
            read_size = min(4096, pos)
            pos -= read_size
            handle.seek(pos)
            chunk = handle.read(read_size) + chunk
            lines = [line.strip() for line in chunk.splitlines() if line.strip()]
            if lines:
                try:
                    record = json.loads(lines[-1].decode("utf-8"))
                except json.JSONDecodeError as exc:
                    raise JournalChainError(f"{path}: trailing JSONL record is invalid") from exc
                if not isinstance(record, dict):
                    raise JournalChainError(f"{path}: trailing JSONL record must be an object")
                return record
    return None


def append_sidecar_envelope(
    raw_path: Path | str,
    record: dict[str, Any],
    *,
    stream: str,
    deployment_id: str | None = None,
) -> Path:
    """Append one envelope to the stream sidecar and return the sidecar path."""
    chain_path = sidecar_path_for(raw_path, stream)
    chain_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = chain_path.with_suffix(chain_path.suffix + ".lock")

    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            previous = _read_last_jsonl_record(chain_path)
            prev_hash = previous["entry_hash"] if previous else ZERO_HASH
            seq = int(previous["seq"]) + 1 if previous else 1
            signer = load_signing_key_from_env()
            entry = build_entry(
                record,
                stream=stream,
                seq=seq,
                prev_hash=prev_hash,
                ts=_record_ts(record),
                deployment_id=deployment_id,
                signing_key=signer.private_key if signer else None,
                signing_key_id=signer.key_id if signer else None,
            )
            if previous:
                verify_chain([previous], stream=stream, start_hash=previous["prev_hash"])
            with open(chain_path, "a") as chain_file:
                chain_file.write(json.dumps(entry, sort_keys=True, separators=(",", ":"), default=str) + "\n")
                chain_file.flush()
                os.fsync(chain_file.fileno())
        except (KeyError, TypeError) as exc:
            raise JournalChainError(f"invalid existing sidecar chain: {chain_path}") from exc
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    return chain_path


def append_sidecar_best_effort(
    raw_path: Path | str,
    record: dict[str, Any],
    *,
    stream: str,
    deployment_id: str | None = None,
    log_fn=None,
) -> bool:
    """Append a sidecar envelope without blocking runtime writes."""
    try:
        append_sidecar_envelope(raw_path, record, stream=stream, deployment_id=deployment_id)
        return True
    except Exception as exc:
        if log_fn is not None:
            try:
                log_fn(f"WARN: journal sidecar append failed for {stream}: {exc}")
            except (OSError, RuntimeError, TypeError, ValueError):
                pass
        return False


@dataclass(frozen=True)
class SidecarBackfillResult:
    """Summary for a sidecar backfill run."""

    raw_path: str
    sidecar_path: str
    stream: str
    records: int
    head_hash: str
    status: str


def backfill_sidecar(
    raw_path: Path | str,
    *,
    stream: str,
    deployment_id: str | None = None,
    force: bool = False,
) -> SidecarBackfillResult:
    """Build or repair a complete sidecar chain for an existing raw JSONL stream."""
    raw = Path(raw_path)
    chain_path = sidecar_path_for(raw, stream)
    chain_path.parent.mkdir(parents=True, exist_ok=True)
    records = read_jsonl(raw)
    existing = read_jsonl(chain_path)

    if existing and not force:
        try:
            verified = verify_chain(existing, stream=stream)
            verify_payload_binding(existing, records, stream=stream)
            if verified.count == len(records):
                return SidecarBackfillResult(
                    raw_path=str(raw),
                    sidecar_path=str(chain_path),
                    stream=stream,
                    records=verified.count,
                    head_hash=verified.head_hash,
                    status="already_complete",
                )
        except JournalChainError as exc:
            if len(existing) == len(records):
                raise JournalChainError(f"complete sidecar does not match raw stream: {chain_path}: {exc}") from exc
            pass

    signer = load_signing_key_from_env()
    entries = []
    prev_hash = ZERO_HASH
    for seq, record in enumerate(records, start=1):
        entry = build_entry(
            record,
            stream=stream,
            seq=seq,
            prev_hash=prev_hash,
            ts=_record_ts(record),
            deployment_id=deployment_id,
            signing_key=signer.private_key if signer else None,
            signing_key_id=signer.key_id if signer else None,
        )
        entries.append(entry)
        prev_hash = entry["entry_hash"]

    verified = verify_chain(entries, stream=stream)
    tmp = chain_path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with open(tmp, "w") as handle:
            for entry in entries:
                handle.write(json.dumps(entry, sort_keys=True, separators=(",", ":"), default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        tmp.replace(chain_path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass

    return SidecarBackfillResult(
        raw_path=str(raw),
        sidecar_path=str(chain_path),
        stream=stream,
        records=verified.count,
        head_hash=verified.head_hash,
        status="backfilled",
    )


def _cmd_backfill(args: argparse.Namespace) -> int:
    result = backfill_sidecar(
        args.input,
        stream=args.stream,
        deployment_id=args.deployment_id,
        force=args.force,
    )
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    entries = read_jsonl(args.input)
    result = verify_chain(entries, stream=args.stream)
    if args.raw_input:
        records = read_jsonl(args.raw_input)
        verify_payload_binding(entries, records, stream=args.stream)
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ZERO journal sidecar tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backfill = subparsers.add_parser("backfill", help="build a sidecar chain from raw JSONL")
    backfill.add_argument("--input", required=True, type=Path)
    backfill.add_argument("--stream", required=True)
    backfill.add_argument("--deployment-id", default="")
    backfill.add_argument("--force", action="store_true")
    backfill.set_defaults(func=_cmd_backfill)

    verify = subparsers.add_parser("verify", help="verify a sidecar chain")
    verify.add_argument("--input", required=True, type=Path)
    verify.add_argument("--stream", required=True)
    verify.add_argument(
        "--raw-input",
        type=Path,
        help="also verify envelope payload hashes against the raw JSONL stream",
    )
    verify.set_defaults(func=_cmd_verify)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
