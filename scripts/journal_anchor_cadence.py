#!/usr/bin/env python3
"""Run and verify periodic ZERO decision-journal anchor operations."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from zero_engine.journal import DecisionJournal, JournalSigner, canonical_json

STATE_SCHEMA_VERSION = "zero.decision_journal.anchor_cadence.v1"


def parse_time(value: str) -> datetime:
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(canonical_json(payload) + "\n", encoding="utf-8")
    tmp.replace(path)


def signer_from_args(args: argparse.Namespace) -> JournalSigner | None:
    secret = os.environ.get(args.signing_key_env) if args.signing_key_env else None
    return JournalSigner(secret=secret, key_id=args.key_id) if secret else None


def anchor_timestamp(packet: dict[str, Any]) -> datetime:
    return parse_time(str(packet["anchored_at"]))


def build_state(
    *,
    status: str,
    reason: str,
    generated_at: datetime,
    journal: Path,
    anchor_dir: Path,
    state_path: Path,
    cadence_hours: int,
    anchor_path: Path | None,
    anchor_packet: dict[str, Any] | None,
    verification: dict[str, Any],
) -> dict[str, Any]:
    anchored_at = anchor_timestamp(anchor_packet) if anchor_packet else None
    next_due_at = anchored_at + timedelta(hours=cadence_hours) if anchored_at else None
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "status": status,
        "reason": reason,
        "generated_at": isoformat_z(generated_at),
        "journal_path": str(journal),
        "anchor_dir": str(anchor_dir),
        "state_path": str(state_path),
        "cadence_hours": cadence_hours,
        "next_due_at": isoformat_z(next_due_at) if next_due_at else None,
        "anchor_path": str(anchor_path) if anchor_path else None,
        "anchor_hash": anchor_packet.get("anchor_hash") if anchor_packet else None,
        "journal_head_hash": verification.get("journal_head_hash") or verification.get("head_hash"),
        "entries": verification.get("entries", 0),
        "externally_anchored": bool(verification.get("externally_anchored", False)),
        "verification": verification,
    }


def anchor_path_for(anchor_dir: Path, now: datetime, anchor_hash: str) -> Path:
    stamp = isoformat_z(now).replace("-", "").replace(":", "")
    short_hash = anchor_hash.removeprefix("sha256:")[:12]
    return anchor_dir / f"journal-anchor-{stamp}-{short_hash}.json"


def verify_anchor(
    args: argparse.Namespace,
    *,
    anchor_packet: dict[str, Any],
    signer: JournalSigner | None,
) -> dict[str, Any]:
    report = DecisionJournal(args.journal).verify_external_anchor(
        anchor_packet,
        signer=signer,
        require_signature=args.require_signature,
        require_anchor=args.require_anchor,
        require_external=args.require_external,
    )
    return report.to_dict()


def latest_is_fresh(
    *,
    latest_packet: dict[str, Any],
    latest_verification: dict[str, Any],
    current_head: str,
    now: datetime,
    max_age_hours: int,
) -> tuple[bool, str]:
    if not latest_verification.get("ok"):
        return False, str(latest_verification.get("reason"))
    if latest_verification.get("journal_head_hash") != current_head:
        return False, "journal head changed since latest anchor"
    age = now - anchor_timestamp(latest_packet)
    if age > timedelta(hours=max_age_hours):
        return False, "latest anchor is stale"
    return True, "latest anchor is fresh"


def run(args: argparse.Namespace) -> int:
    now = parse_time(args.now) if args.now else datetime.now(UTC)
    signer = signer_from_args(args)
    journal = DecisionJournal(args.journal)
    verification = journal.verify_integrity(
        signer=signer,
        require_signature=args.require_signature,
        require_anchor=args.require_anchor,
    )
    if not verification.ok:
        print(f"zero journal anchor cadence: ok=False reason={verification.reason}", file=sys.stderr)
        return 1
    if verification.head_hash is None:
        print("zero journal anchor cadence: ok=False reason=empty journal", file=sys.stderr)
        return 1

    args.anchor_dir.mkdir(parents=True, exist_ok=True)
    latest_path = args.anchor_dir / "journal-anchor-latest.json"
    state_path = args.state or (args.anchor_dir / "journal-anchor-state.json")
    latest_packet = read_json(latest_path)
    if latest_packet is not None:
        latest_verification = verify_anchor(args, anchor_packet=latest_packet, signer=signer)
        fresh, reason = latest_is_fresh(
            latest_packet=latest_packet,
            latest_verification=latest_verification,
            current_head=verification.head_hash,
            now=now,
            max_age_hours=args.max_age_hours,
        )
        if fresh:
            state = build_state(
                status="fresh",
                reason=reason,
                generated_at=now,
                journal=args.journal,
                anchor_dir=args.anchor_dir,
                state_path=state_path,
                cadence_hours=args.max_age_hours,
                anchor_path=latest_path,
                anchor_packet=latest_packet,
                verification=latest_verification,
            )
            write_json_atomic(state_path, state)
            print(
                "zero journal anchor cadence: "
                f"status=fresh external={state['externally_anchored']} head={state['journal_head_hash']}"
            )
            return 0

    if args.require_external and not args.anchor_ref:
        state = build_state(
            status="external_receipt_required",
            reason="external receipt required before writing a live-capable anchor",
            generated_at=now,
            journal=args.journal,
            anchor_dir=args.anchor_dir,
            state_path=state_path,
            cadence_hours=args.max_age_hours,
            anchor_path=None,
            anchor_packet=None,
            verification=verification.to_dict(),
        )
        write_json_atomic(state_path, state)
        print(f"zero journal anchor cadence: ok=False reason={state['reason']}", file=sys.stderr)
        return 1

    anchor = journal.create_external_anchor(
        method=args.method,
        anchor_ref=args.anchor_ref,
        signer=signer,
        require_signature=args.require_signature,
        require_anchor=args.require_anchor,
        anchored_at=now,
        note=args.note,
    ).to_dict()
    verification_payload = verify_anchor(args, anchor_packet=anchor, signer=signer)
    if not verification_payload.get("ok"):
        print(f"zero journal anchor cadence: ok=False reason={verification_payload.get('reason')}", file=sys.stderr)
        return 1

    immutable_path = anchor_path_for(args.anchor_dir, now, str(anchor["anchor_hash"]))
    write_json_atomic(immutable_path, anchor)
    write_json_atomic(latest_path, anchor)
    state = build_state(
        status="anchored" if verification_payload.get("externally_anchored") else "prepared",
        reason="anchor packet created",
        generated_at=now,
        journal=args.journal,
        anchor_dir=args.anchor_dir,
        state_path=state_path,
        cadence_hours=args.max_age_hours,
        anchor_path=latest_path,
        anchor_packet=anchor,
        verification=verification_payload,
    )
    write_json_atomic(state_path, state)
    print(
        "zero journal anchor cadence: "
        f"status={state['status']} external={state['externally_anchored']} "
        f"entries={state['entries']} head={state['journal_head_hash']} anchor={state['anchor_hash']}"
    )
    return 0


def verify_state(args: argparse.Namespace) -> int:
    now = parse_time(args.now) if args.now else datetime.now(UTC)
    signer = signer_from_args(args)
    state = read_json(args.state)
    if state is None:
        print("zero journal anchor cadence verify: ok=False reason=missing state", file=sys.stderr)
        return 1
    if state.get("schema_version") != STATE_SCHEMA_VERSION:
        print("zero journal anchor cadence verify: ok=False reason=wrong state schema", file=sys.stderr)
        return 1
    anchor_path = Path(str(state.get("anchor_path") or ""))
    anchor_packet = read_json(anchor_path)
    if anchor_packet is None:
        print("zero journal anchor cadence verify: ok=False reason=missing anchor packet", file=sys.stderr)
        return 1
    verification = verify_anchor(args, anchor_packet=anchor_packet, signer=signer)
    if not verification.get("ok"):
        print(f"zero journal anchor cadence verify: ok=False reason={verification.get('reason')}", file=sys.stderr)
        return 1
    if state.get("anchor_hash") != anchor_packet.get("anchor_hash"):
        print("zero journal anchor cadence verify: ok=False reason=state anchor hash mismatch", file=sys.stderr)
        return 1
    if args.require_external and not verification.get("externally_anchored"):
        print("zero journal anchor cadence verify: ok=False reason=external receipt required", file=sys.stderr)
        return 1
    next_due = parse_time(str(state["next_due_at"])) if state.get("next_due_at") else None
    if next_due and now > next_due:
        print("zero journal anchor cadence verify: ok=False reason=anchor cadence overdue", file=sys.stderr)
        return 1
    print(
        "zero journal anchor cadence verify: "
        f"ok=True external={verification.get('externally_anchored')} head={verification.get('journal_head_hash')}"
    )
    return 0


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("journal", type=Path)
    parser.add_argument("--require-signature", action="store_true")
    parser.add_argument("--require-anchor", action="store_true")
    parser.add_argument("--require-external", action="store_true")
    parser.add_argument("--signing-key-env", default=None)
    parser.add_argument("--key-id", default="local-operator")
    parser.add_argument("--now", default=None)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or verify ZERO journal anchor cadence.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="create or refresh a periodic anchor packet")
    add_common(run_parser)
    run_parser.add_argument("--anchor-dir", type=Path, required=True)
    run_parser.add_argument("--state", type=Path, default=None)
    run_parser.add_argument("--method", required=True)
    run_parser.add_argument("--anchor-ref", default=None)
    run_parser.add_argument("--note", default=None)
    run_parser.add_argument("--max-age-hours", type=int, default=24)

    verify_parser = subparsers.add_parser("verify-state", help="verify a cadence state file")
    add_common(verify_parser)
    verify_parser.add_argument("--state", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "run":
        return run(args)
    if args.command == "verify-state":
        return verify_state(args)
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
