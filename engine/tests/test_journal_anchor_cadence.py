from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from zero_engine.journal import DecisionJournal

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "journal_anchor_cadence.py"


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


def run_script(*args: str, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    merged_env = {**os.environ, "PYTHONPATH": str(ROOT / "engine" / "src")}
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=check,
        capture_output=True,
        text=True,
        env=merged_env,
    )


def test_journal_anchor_cadence_creates_external_anchor_and_state(tmp_path: Path) -> None:
    journal = DecisionJournal.signed(tmp_path / "decisions.jsonl", secret="test-secret", key_id="operator-test")
    journal.append(decision_payload("BTC"))
    anchor_dir = tmp_path / "anchors"

    run_script(
        "run",
        str(journal.path),
        "--anchor-dir",
        str(anchor_dir),
        "--method",
        "opentimestamps",
        "--anchor-ref",
        "ots:sha256:test-receipt",
        "--require-signature",
        "--require-external",
        "--signing-key-env",
        "ZERO_JOURNAL_SIGNING_KEY",
        "--key-id",
        "operator-test",
        "--now",
        "2026-05-01T00:00:00Z",
        env={"ZERO_JOURNAL_SIGNING_KEY": "test-secret"},
    )
    state = json.loads((anchor_dir / "journal-anchor-state.json").read_text(encoding="utf-8"))
    latest = json.loads((anchor_dir / "journal-anchor-latest.json").read_text(encoding="utf-8"))

    assert state["schema_version"] == "zero.decision_journal.anchor_cadence.v1"
    assert state["status"] == "anchored"
    assert state["externally_anchored"] is True
    assert state["anchor_hash"] == latest["anchor_hash"]
    assert state["next_due_at"] == "2026-05-02T00:00:00Z"
    assert len(list(anchor_dir.glob("journal-anchor-20260501T000000Z-*.json"))) == 1

    verify = run_script(
        "verify-state",
        str(journal.path),
        "--state",
        str(anchor_dir / "journal-anchor-state.json"),
        "--require-signature",
        "--require-external",
        "--signing-key-env",
        "ZERO_JOURNAL_SIGNING_KEY",
        "--key-id",
        "operator-test",
        "--now",
        "2026-05-01T01:00:00Z",
        env={"ZERO_JOURNAL_SIGNING_KEY": "test-secret"},
    )
    assert "ok=True" in verify.stdout


def test_journal_anchor_cadence_reuses_fresh_same_head_anchor(tmp_path: Path) -> None:
    journal = DecisionJournal(tmp_path / "decisions.jsonl")
    journal.append(decision_payload("BTC"))
    anchor_dir = tmp_path / "anchors"

    run_script(
        "run",
        str(journal.path),
        "--anchor-dir",
        str(anchor_dir),
        "--method",
        "rekor",
        "--anchor-ref",
        "rekor:uuid:test",
        "--require-external",
        "--now",
        "2026-05-01T00:00:00Z",
    )
    run_script(
        "run",
        str(journal.path),
        "--anchor-dir",
        str(anchor_dir),
        "--method",
        "rekor",
        "--anchor-ref",
        "rekor:uuid:test-2",
        "--require-external",
        "--now",
        "2026-05-01T12:00:00Z",
    )
    state = json.loads((anchor_dir / "journal-anchor-state.json").read_text(encoding="utf-8"))

    assert state["status"] == "fresh"
    assert len(list(anchor_dir.glob("journal-anchor-20260501T*.json"))) == 1


def test_journal_anchor_cadence_refreshes_when_head_changes(tmp_path: Path) -> None:
    journal = DecisionJournal(tmp_path / "decisions.jsonl")
    journal.append(decision_payload("BTC"))
    anchor_dir = tmp_path / "anchors"

    run_script(
        "run",
        str(journal.path),
        "--anchor-dir",
        str(anchor_dir),
        "--method",
        "rekor",
        "--anchor-ref",
        "rekor:uuid:first",
        "--require-external",
        "--now",
        "2026-05-01T00:00:00Z",
    )
    journal.append(decision_payload("ETH"))
    run_script(
        "run",
        str(journal.path),
        "--anchor-dir",
        str(anchor_dir),
        "--method",
        "rekor",
        "--anchor-ref",
        "rekor:uuid:second",
        "--require-external",
        "--now",
        "2026-05-01T01:00:00Z",
    )
    state = json.loads((anchor_dir / "journal-anchor-state.json").read_text(encoding="utf-8"))

    assert state["status"] == "anchored"
    assert state["entries"] == 2
    assert len(list(anchor_dir.glob("journal-anchor-20260501T*.json"))) == 2


def test_journal_anchor_cadence_refuses_live_required_anchor_without_receipt(tmp_path: Path) -> None:
    journal = DecisionJournal(tmp_path / "decisions.jsonl")
    journal.append(decision_payload("BTC"))
    anchor_dir = tmp_path / "anchors"

    result = run_script(
        "run",
        str(journal.path),
        "--anchor-dir",
        str(anchor_dir),
        "--method",
        "opentimestamps",
        "--require-external",
        "--now",
        "2026-05-01T00:00:00Z",
        check=False,
    )
    state = json.loads((anchor_dir / "journal-anchor-state.json").read_text(encoding="utf-8"))

    assert result.returncode == 1
    assert state["status"] == "external_receipt_required"
    assert not (anchor_dir / "journal-anchor-latest.json").exists()
