import json
import os
import subprocess
import sys
from pathlib import Path

from zero_engine.journal import DecisionJournal, JournalSigner


def decision_payload(symbol: str = "BTC") -> dict:
    return {
        "as_of": 123.0,
        "source": "test",
        "symbol": symbol,
        "side": "buy",
        "quantity": 0.01,
        "price": 40_000,
        "notional_usd": 400.0,
        "confidence": 0.9,
        "reduce_only": False,
        "allowed": True,
        "reason": "allowed",
    }


def test_decision_journal_writes_hash_chained_entries_and_unwraps_payloads(tmp_path: Path) -> None:
    journal = DecisionJournal(tmp_path / "decisions.jsonl")

    journal.append(decision_payload("BTC"))
    journal.append(decision_payload("ETH"))

    records = journal.read_all()
    entries = journal.read_entries()
    verification = journal.verify_integrity()

    assert [record["symbol"] for record in records] == ["BTC", "ETH"]
    assert entries[0].sequence == 1
    assert entries[0].previous_hash is None
    assert entries[1].sequence == 2
    assert entries[1].previous_hash == entries[0].entry_hash
    assert verification.ok is True
    assert verification.entries == 2
    assert verification.head_hash == entries[1].entry_hash
    assert verification.anchored_entries == 2


def test_decision_journal_detects_payload_tampering(tmp_path: Path) -> None:
    journal = DecisionJournal(tmp_path / "decisions.jsonl")
    journal.append(decision_payload())

    entry = json.loads(journal.path.read_text(encoding="utf-8").splitlines()[0])
    entry["payload"]["price"] = 41_000
    journal.path.write_text(json.dumps(entry, sort_keys=True) + "\n", encoding="utf-8")

    verification = journal.verify_integrity()

    assert verification.ok is False
    assert verification.reason == "entry hash mismatch at entry 1"


def test_decision_journal_detects_deleted_middle_entry(tmp_path: Path) -> None:
    journal = DecisionJournal(tmp_path / "decisions.jsonl")
    journal.append(decision_payload("BTC"))
    journal.append(decision_payload("ETH"))
    journal.append(decision_payload("SOL"))

    lines = journal.path.read_text(encoding="utf-8").splitlines()
    journal.path.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")

    verification = journal.verify_integrity()

    assert verification.ok is False
    assert verification.reason == "sequence mismatch at entry 2"


def test_decision_journal_serializes_concurrent_writer_processes(tmp_path: Path) -> None:
    journal_path = tmp_path / "decisions.jsonl"
    writer = """
import sys
from zero_engine.journal import DecisionJournal

idx = int(sys.argv[2])
DecisionJournal(sys.argv[1]).append({
    "as_of": 123.0 + idx,
    "source": "concurrency-test",
    "symbol": f"BTC-{idx}",
    "side": "buy",
    "quantity": 0.01,
    "price": 40000 + idx,
    "notional_usd": 400.0,
    "confidence": 0.9,
    "reduce_only": False,
    "allowed": True,
    "reason": "allowed",
})
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", writer, str(journal_path), str(idx)],
            env=env,
            stderr=subprocess.PIPE,
            text=True,
        )
        for idx in range(16)
    ]

    for process in processes:
        _stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr

    journal = DecisionJournal(journal_path)
    verification = journal.verify_integrity()
    records = journal.read_all()

    assert verification.ok is True
    assert verification.entries == 16
    assert {record["symbol"] for record in records} == {f"BTC-{idx}" for idx in range(16)}


def test_signed_decision_journal_verifies_with_operator_key(tmp_path: Path) -> None:
    signer = JournalSigner(secret="local-test-secret", key_id="operator-test")
    journal = DecisionJournal(tmp_path / "decisions.jsonl", signer=signer)
    journal.append(decision_payload())

    verification = journal.verify_integrity(signer=signer, require_signature=True)

    assert verification.ok is True
    assert verification.signed_entries == 1
    assert verification.signature_verified == 1


def test_signed_decision_journal_rejects_wrong_key(tmp_path: Path) -> None:
    journal = DecisionJournal.signed(
        tmp_path / "decisions.jsonl",
        secret="local-test-secret",
        key_id="operator-test",
    )
    journal.append(decision_payload())
    wrong = JournalSigner(secret="wrong-secret", key_id="operator-test")

    verification = journal.verify_integrity(signer=wrong, require_signature=True)

    assert verification.ok is False
    assert verification.reason == "signature mismatch at entry 1"


def test_unsigned_decision_journal_fails_when_signature_is_required(tmp_path: Path) -> None:
    journal = DecisionJournal(tmp_path / "decisions.jsonl")
    journal.append(decision_payload())

    verification = journal.verify_integrity(require_signature=True)

    assert verification.ok is False
    assert verification.reason == "missing signature at entry 1"


def test_decision_journal_cli_verifies_signed_journal(tmp_path: Path) -> None:
    env = {**os.environ, "ZERO_JOURNAL_SIGNING_KEY": "local-test-secret"}
    journal = DecisionJournal.signed(
        tmp_path / "decisions.jsonl",
        secret="local-test-secret",
        key_id="operator-test",
    )
    journal.append(decision_payload())

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "zero_engine.journal",
            "verify",
            str(journal.path),
            "--require-signature",
            "--signing-key-env",
            "ZERO_JOURNAL_SIGNING_KEY",
            "--key-id",
            "operator-test",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "zero.decision_journal.verification.v1"
    assert payload["ok"] is True
    assert payload["signed_entries"] == 1
    assert payload["signature_verified"] == 1


def test_decision_journal_creates_and_verifies_external_anchor(tmp_path: Path) -> None:
    journal = DecisionJournal(tmp_path / "decisions.jsonl")
    journal.append(decision_payload("BTC"))
    journal.append(decision_payload("ETH"))

    anchor = journal.create_external_anchor(
        method="opentimestamps",
        anchor_ref="ots:sha256:example-receipt",
        note="test fixture",
    )
    verification = journal.verify_external_anchor(anchor.to_dict(), require_external=True)

    assert anchor.schema_version == "zero.decision_journal.external_anchor.v1"
    assert anchor.status == "externally_anchored"
    assert anchor.entries == 2
    assert verification.ok is True
    assert verification.externally_anchored is True
    assert verification.anchor_hash == anchor.to_dict()["anchor_hash"]


def test_decision_journal_external_anchor_rejects_head_mismatch(tmp_path: Path) -> None:
    journal = DecisionJournal(tmp_path / "decisions.jsonl")
    journal.append(decision_payload("BTC"))
    anchor = journal.create_external_anchor(method="rekor", anchor_ref="rekor:uuid:test").to_dict()
    journal.append(decision_payload("ETH"))

    verification = journal.verify_external_anchor(anchor, require_external=True)

    assert verification.ok is False
    assert verification.reason == "external anchor journal head mismatch"


def test_decision_journal_external_anchor_can_require_external_receipt(tmp_path: Path) -> None:
    journal = DecisionJournal(tmp_path / "decisions.jsonl")
    journal.append(decision_payload("BTC"))
    anchor = journal.create_external_anchor(method="opentimestamps").to_dict()

    verification = journal.verify_external_anchor(anchor, require_external=True)

    assert verification.ok is False
    assert verification.reason == "external timestamp receipt required"


def test_decision_journal_cli_creates_and_verifies_external_anchor(tmp_path: Path) -> None:
    journal = DecisionJournal(tmp_path / "decisions.jsonl")
    journal.append(decision_payload())
    anchor_path = tmp_path / "journal-anchor.json"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "zero_engine.journal",
            "anchor",
            str(journal.path),
            "--output",
            str(anchor_path),
            "--method",
            "rekor",
            "--anchor-ref",
            "rekor:uuid:test",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "zero_engine.journal",
            "verify-anchor",
            str(journal.path),
            str(anchor_path),
            "--require-external",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "zero.decision_journal.external_anchor.verification.v1"
    assert payload["ok"] is True
    assert payload["externally_anchored"] is True
