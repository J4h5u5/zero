from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

JOURNAL_ENTRY_SCHEMA_VERSION = "zero.decision_journal.entry.v1"
JOURNAL_SIGNATURE_SCHEMA_VERSION = "zero.decision_journal.signature.v1"
JOURNAL_ANCHOR_SCHEMA_VERSION = "zero.decision_journal.timestamp_anchor.v1"
JOURNAL_VERIFICATION_SCHEMA_VERSION = "zero.decision_journal.verification.v1"


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(payload: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class JournalSigner:
    """Operator-owned HMAC signer for local decision journals.

    This intentionally uses the Python standard library so a fresh clone can
    verify signed journals without extra dependencies. Operators that need
    hardware-backed signatures can attach the resulting journal head to an
    external signature or timestamp service.
    """

    secret: str
    key_id: str = "local-operator"

    def sign(self, entry_hash: str) -> dict[str, Any]:
        signature = hmac.new(
            self.secret.encode("utf-8"),
            entry_hash.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "schema_version": JOURNAL_SIGNATURE_SCHEMA_VERSION,
            "status": "signed",
            "algorithm": "hmac-sha256",
            "key_id": self.key_id,
            "signed_entry_hash": entry_hash,
            "signature": "hex:" + signature,
        }

    def verify(self, signature: Mapping[str, Any], entry_hash: str) -> bool:
        if signature.get("schema_version") != JOURNAL_SIGNATURE_SCHEMA_VERSION:
            return False
        if signature.get("status") != "signed":
            return False
        if signature.get("algorithm") != "hmac-sha256":
            return False
        if signature.get("key_id") != self.key_id:
            return False
        if signature.get("signed_entry_hash") != entry_hash:
            return False
        raw = str(signature.get("signature", ""))
        if not raw.startswith("hex:"):
            return False
        expected = self.sign(entry_hash)["signature"]
        return hmac.compare_digest(raw, expected)


@dataclass(frozen=True)
class JournalEntry:
    sequence: int
    payload: dict[str, Any]
    previous_hash: str | None
    entry_hash: str
    signature: dict[str, Any]
    timestamp_anchor: dict[str, Any]
    schema_version: str = JOURNAL_ENTRY_SCHEMA_VERSION

    def hash_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "sequence": self.sequence,
            "previous_hash": self.previous_hash,
            "payload": self.payload,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.hash_payload(),
            "entry_hash": self.entry_hash,
            "signature": self.signature,
            "timestamp_anchor": self.timestamp_anchor,
        }

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        payload: Mapping[str, Any],
        previous_hash: str | None,
        signer: JournalSigner | None = None,
        anchored_at: datetime | None = None,
    ) -> "JournalEntry":
        entry_payload = dict(payload)
        hash_payload = {
            "schema_version": JOURNAL_ENTRY_SCHEMA_VERSION,
            "sequence": sequence,
            "previous_hash": previous_hash,
            "payload": entry_payload,
        }
        entry_hash = sha256_json(hash_payload)
        signature = (
            signer.sign(entry_hash)
            if signer is not None
            else {
                "schema_version": JOURNAL_SIGNATURE_SCHEMA_VERSION,
                "status": "unsigned_local",
                "algorithm": None,
                "key_id": None,
                "signed_entry_hash": entry_hash,
                "signature": None,
            }
        )
        timestamp_anchor = {
            "schema_version": JOURNAL_ANCHOR_SCHEMA_VERSION,
            "status": "local_untrusted",
            "method": "local_clock",
            "anchored_entry_hash": entry_hash,
            "anchored_at": (anchored_at or datetime.now(UTC)).isoformat().replace("+00:00", "Z"),
            "anchor_ref": None,
        }
        return cls(
            sequence=sequence,
            payload=entry_payload,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
            signature=signature,
            timestamp_anchor=timestamp_anchor,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "JournalEntry":
        if payload.get("schema_version") != JOURNAL_ENTRY_SCHEMA_VERSION:
            raise ValueError("not a decision journal v1 entry")
        signature = payload.get("signature")
        timestamp_anchor = payload.get("timestamp_anchor")
        if not isinstance(signature, dict):
            raise ValueError("journal entry signature must be an object")
        if not isinstance(timestamp_anchor, dict):
            raise ValueError("journal entry timestamp_anchor must be an object")
        raw_payload = payload.get("payload")
        if not isinstance(raw_payload, dict):
            raise ValueError("journal entry payload must be an object")
        return cls(
            sequence=int(payload["sequence"]),
            payload=raw_payload,
            previous_hash=str(payload["previous_hash"]) if payload.get("previous_hash") else None,
            entry_hash=str(payload["entry_hash"]),
            signature=signature,
            timestamp_anchor=timestamp_anchor,
        )


@dataclass(frozen=True)
class JournalVerification:
    ok: bool
    reason: str
    entries: int
    head_hash: str | None
    signed_entries: int
    unsigned_entries: int
    anchored_entries: int
    signature_verified: int = 0
    findings: list[dict[str, Any]] = field(default_factory=list)
    schema_version: str = JOURNAL_VERIFICATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ok": self.ok,
            "reason": self.reason,
            "entries": self.entries,
            "head_hash": self.head_hash,
            "signed_entries": self.signed_entries,
            "unsigned_entries": self.unsigned_entries,
            "anchored_entries": self.anchored_entries,
            "signature_verified": self.signature_verified,
            "findings": self.findings,
        }


def _legacy_entry(payload: Mapping[str, Any], *, sequence: int, previous_hash: str | None) -> JournalEntry:
    entry = JournalEntry.create(sequence=sequence, payload=payload, previous_hash=previous_hash)
    signature = {
        **entry.signature,
        "status": "legacy_unsigned",
    }
    return JournalEntry(
        sequence=entry.sequence,
        payload=entry.payload,
        previous_hash=entry.previous_hash,
        entry_hash=entry.entry_hash,
        signature=signature,
        timestamp_anchor=entry.timestamp_anchor,
    )


class DecisionJournal:
    """Append-only JSONL journal for replayable engine decisions."""

    def __init__(self, path: str | Path, *, signer: JournalSigner | None = None) -> None:
        self.path = Path(path)
        self.signer = signer

    @classmethod
    def signed(cls, path: str | Path, *, secret: str, key_id: str = "local-operator") -> "DecisionJournal":
        return cls(path, signer=JournalSigner(secret=secret, key_id=key_id))

    @classmethod
    def from_env(
        cls,
        path: str | Path,
        *,
        env: str = "ZERO_JOURNAL_SIGNING_KEY",
        key_id: str = "local-operator",
    ) -> "DecisionJournal":
        secret = os.environ.get(env)
        return cls.signed(path, secret=secret, key_id=key_id) if secret else cls(path)

    def append(self, record: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entries = self.read_entries()
        previous_hash = entries[-1].entry_hash if entries else None
        entry = JournalEntry.create(
            sequence=len(entries) + 1,
            payload=record,
            previous_hash=previous_hash,
            signer=self.signer,
        )
        line = canonical_json(entry.to_dict()) + "\n"
        fd = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def tail(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        records = self.read_all()
        return records[-limit:]

    def read_all(self) -> list[dict[str, Any]]:
        return [entry.payload for entry in self.read_entries()]

    def read_entries(self) -> list[JournalEntry]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        entries: list[JournalEntry] = []
        previous_hash: str | None = None
        for line in lines:
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, dict) and payload.get("schema_version") == JOURNAL_ENTRY_SCHEMA_VERSION:
                entry = JournalEntry.from_dict(payload)
            elif isinstance(payload, dict):
                entry = _legacy_entry(payload, sequence=len(entries) + 1, previous_hash=previous_hash)
            else:
                raise ValueError("journal lines must be JSON objects")
            entries.append(entry)
            previous_hash = entry.entry_hash
        return entries

    def verify_integrity(
        self,
        *,
        signer: JournalSigner | None = None,
        require_signature: bool = False,
        require_anchor: bool = False,
    ) -> JournalVerification:
        findings: list[dict[str, Any]] = []
        try:
            entries = self.read_entries()
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
            return JournalVerification(
                ok=False,
                reason=f"journal parse failure: {exc}",
                entries=0,
                head_hash=None,
                signed_entries=0,
                unsigned_entries=0,
                anchored_entries=0,
                findings=[{"status": "fail", "name": "parse", "detail": str(exc)}],
            )

        signed_entries = 0
        unsigned_entries = 0
        anchored_entries = 0
        signature_verified = 0
        previous_hash: str | None = None
        verifier = signer or self.signer

        for expected_sequence, entry in enumerate(entries, start=1):
            recomputed = sha256_json(entry.hash_payload())
            if entry.sequence != expected_sequence:
                return _journal_fail(
                    f"sequence mismatch at entry {expected_sequence}",
                    entries,
                    findings,
                    signed_entries,
                    unsigned_entries,
                    anchored_entries,
                    signature_verified,
                )
            if entry.previous_hash != previous_hash:
                return _journal_fail(
                    f"previous hash mismatch at entry {expected_sequence}",
                    entries,
                    findings,
                    signed_entries,
                    unsigned_entries,
                    anchored_entries,
                    signature_verified,
                )
            if entry.entry_hash != recomputed:
                return _journal_fail(
                    f"entry hash mismatch at entry {expected_sequence}",
                    entries,
                    findings,
                    signed_entries,
                    unsigned_entries,
                    anchored_entries,
                    signature_verified,
                )

            signature_status = str(entry.signature.get("status"))
            if signature_status == "signed":
                signed_entries += 1
                if verifier is not None:
                    if not verifier.verify(entry.signature, entry.entry_hash):
                        return _journal_fail(
                            f"signature mismatch at entry {expected_sequence}",
                            entries,
                            findings,
                            signed_entries,
                            unsigned_entries,
                            anchored_entries,
                            signature_verified,
                        )
                    signature_verified += 1
            else:
                unsigned_entries += 1
                if require_signature:
                    return _journal_fail(
                        f"missing signature at entry {expected_sequence}",
                        entries,
                        findings,
                        signed_entries,
                        unsigned_entries,
                        anchored_entries,
                        signature_verified,
                    )

            if entry.timestamp_anchor.get("anchored_entry_hash") == entry.entry_hash:
                anchored_entries += 1
            elif require_anchor:
                return _journal_fail(
                    f"timestamp anchor mismatch at entry {expected_sequence}",
                    entries,
                    findings,
                    signed_entries,
                    unsigned_entries,
                    anchored_entries,
                    signature_verified,
                )
            previous_hash = entry.entry_hash

        reason = "empty journal" if not entries else "journal verifies"
        return JournalVerification(
            ok=True,
            reason=reason,
            entries=len(entries),
            head_hash=entries[-1].entry_hash if entries else None,
            signed_entries=signed_entries,
            unsigned_entries=unsigned_entries,
            anchored_entries=anchored_entries,
            signature_verified=signature_verified,
            findings=findings,
        )

def _journal_fail(
    reason: str,
    entries: list[JournalEntry],
    findings: list[dict[str, Any]],
    signed_entries: int,
    unsigned_entries: int,
    anchored_entries: int,
    signature_verified: int,
) -> JournalVerification:
    findings = [*findings, {"status": "fail", "name": "integrity", "detail": reason}]
    return JournalVerification(
        ok=False,
        reason=reason,
        entries=len(entries),
        head_hash=entries[-1].entry_hash if entries else None,
        signed_entries=signed_entries,
        unsigned_entries=unsigned_entries,
        anchored_entries=anchored_entries,
        signature_verified=signature_verified,
        findings=findings,
    )


def _signer_from_args(args: argparse.Namespace) -> JournalSigner | None:
    secret = os.environ.get(args.signing_key_env) if args.signing_key_env else None
    return JournalSigner(secret=secret, key_id=args.key_id) if secret else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ZERO decision journal integrity.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify", help="verify a decision journal")
    verify.add_argument("journal", type=Path)
    verify.add_argument("--require-signature", action="store_true")
    verify.add_argument("--require-anchor", action="store_true")
    verify.add_argument("--signing-key-env", default=None)
    verify.add_argument("--key-id", default="local-operator")
    verify.add_argument("--json", action="store_true")
    args = parser.parse_args()

    signer = _signer_from_args(args)
    report = DecisionJournal(args.journal).verify_integrity(
        signer=signer,
        require_signature=args.require_signature,
        require_anchor=args.require_anchor,
    )
    if args.json:
        print(canonical_json(report.to_dict()))
    else:
        print(
            "zero journal verify: "
            f"ok={report.ok} entries={report.entries} signed={report.signed_entries} "
            f"verified={report.signature_verified} head={report.head_hash} reason={report.reason}"
        )
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
