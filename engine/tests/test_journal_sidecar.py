import base64
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from zero_engine.journal_chain import JournalChainError, read_jsonl, verify_chain
from zero_engine.journal_sidecar import append_sidecar_envelope, backfill_sidecar, main, sidecar_path_for
from zero_engine.journal_signing import SIGNING_KEY_ENV, SIGNING_KEY_ID_ENV
from zero_engine.bus import append_jsonl


def test_sidecar_path_is_sibling_chain_file(tmp_path: Path) -> None:
    path = sidecar_path_for(tmp_path / "trades.jsonl", "trades")

    assert path == tmp_path / "journal-chains" / "trades.trades.chain.jsonl"


def test_append_sidecar_envelope_chains_records(tmp_path: Path) -> None:
    raw = tmp_path / "trades.jsonl"
    first = {"ts": "2026-05-04T00:00:00Z", "event": "close", "coin": "ETH"}
    second = {"ts": "2026-05-04T00:01:00Z", "event": "close", "coin": "BTC"}

    chain_path = append_sidecar_envelope(raw, first, stream="trades")
    append_sidecar_envelope(raw, second, stream="trades")
    entries = read_jsonl(chain_path)

    assert len(entries) == 2
    assert entries[0]["ts"] == first["ts"]
    assert entries[1]["ts"] == second["ts"]
    assert entries[1]["prev_hash"] == entries[0]["entry_hash"]
    assert verify_chain(entries, stream="trades").count == 2


def test_append_sidecar_envelope_uses_trade_exit_time_when_ts_is_absent(tmp_path: Path) -> None:
    raw = tmp_path / "trades.jsonl"
    record = {
        "entry_time": "2026-05-04T00:00:00Z",
        "exit_time": "2026-05-04T00:15:00Z",
        "event": "close",
    }

    chain_path = append_sidecar_envelope(raw, record, stream="trades")
    entry = read_jsonl(chain_path)[0]

    assert entry["ts"] == "2026-05-04T00:15:00Z"


def test_append_sidecar_envelope_signs_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw_key = Ed25519PrivateKey.generate().private_bytes(
        Encoding.Raw,
        PrivateFormat.Raw,
        NoEncryption(),
    )
    monkeypatch.setenv(SIGNING_KEY_ENV, base64.urlsafe_b64encode(raw_key).decode("ascii"))
    monkeypatch.setenv(SIGNING_KEY_ID_ENV, "sidecar-test-v1")
    chain_path = append_sidecar_envelope(
        tmp_path / "trades.jsonl",
        {"ts": "2026-05-04T00:00:00Z", "event": "close"},
        stream="trades",
    )

    entry = read_jsonl(chain_path)[0]
    assert entry["signing_key_id"] == "sidecar-test-v1"
    assert entry["signing_public_key_b64"]
    assert entry["signature"]
    assert verify_chain([entry], stream="trades").count == 1


def test_tampered_sidecar_fails_verification(tmp_path: Path) -> None:
    chain_path = append_sidecar_envelope(
        tmp_path / "trades.jsonl",
        {"ts": "2026-05-04T00:00:00Z", "event": "close"},
        stream="trades",
    )
    entry = read_jsonl(chain_path)[0]
    entry["payload_hash"] = "sha256:" + ("f" * 64)
    chain_path.write_text(json.dumps(entry) + "\n")

    with pytest.raises(JournalChainError, match="entry hash mismatch"):
        verify_chain(read_jsonl(chain_path), stream="trades")


def test_backfill_sidecar_builds_complete_chain(tmp_path: Path) -> None:
    raw = tmp_path / "trades.jsonl"
    raw.write_text(
        '{"ts":"2026-05-04T00:00:00Z","event":"close","coin":"ETH"}\n'
        '{"ts":"2026-05-04T00:01:00Z","event":"close","coin":"BTC"}\n'
    )

    result = backfill_sidecar(raw, stream="trades")
    entries = read_jsonl(result.sidecar_path)

    assert result.status == "backfilled"
    assert result.records == 2
    assert entries[0]["ts"] == "2026-05-04T00:00:00Z"
    assert entries[1]["ts"] == "2026-05-04T00:01:00Z"
    assert verify_chain(entries, stream="trades").head_hash == result.head_hash


def test_backfill_sidecar_noops_when_complete(tmp_path: Path) -> None:
    raw = tmp_path / "trades.jsonl"
    raw.write_text('{"ts":"2026-05-04T00:00:00Z","event":"close"}\n')

    first = backfill_sidecar(raw, stream="trades")
    second = backfill_sidecar(raw, stream="trades")

    assert first.status == "backfilled"
    assert second.status == "already_complete"
    assert second.head_hash == first.head_hash


def test_backfill_sidecar_rejects_complete_chain_bound_to_different_raw_payload(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "trades.jsonl"
    raw.write_text('{"ts":"2026-05-04T00:00:00Z","event":"close","coin":"ETH"}\n')
    backfill_sidecar(raw, stream="trades")
    raw.write_text('{"ts":"2026-05-04T00:00:00Z","event":"close","coin":"BTC"}\n')

    with pytest.raises(JournalChainError, match="complete sidecar does not match raw stream"):
        backfill_sidecar(raw, stream="trades")


def test_backfill_sidecar_repairs_partial_chain(tmp_path: Path) -> None:
    raw = tmp_path / "trades.jsonl"
    raw.write_text(
        '{"ts":"2026-05-04T00:00:00Z","event":"close"}\n'
        '{"ts":"2026-05-04T00:01:00Z","event":"close"}\n'
    )
    append_sidecar_envelope(raw, {"ts": "2026-05-04T00:00:00Z", "event": "close"}, stream="trades")

    result = backfill_sidecar(raw, stream="trades")

    assert result.status == "backfilled"
    assert result.records == 2


def test_sidecar_cli_backfill_and_verify(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    raw = tmp_path / "trades.jsonl"
    raw.write_text('{"ts":"2026-05-04T00:00:00Z","event":"close"}\n')

    assert main(["backfill", "--input", str(raw), "--stream", "trades"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "backfilled"
    assert main(["verify", "--input", out["sidecar_path"], "--stream", "trades"]) == 0
    verify_out = json.loads(capsys.readouterr().out)
    assert verify_out["count"] == 1


def test_sidecar_cli_verify_raw_binding_rejects_tampered_raw(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw = tmp_path / "trades.jsonl"
    raw.write_text('{"ts":"2026-05-04T00:00:00Z","event":"close","coin":"ETH"}\n')
    assert main(["backfill", "--input", str(raw), "--stream", "trades"]) == 0
    out = json.loads(capsys.readouterr().out)
    raw.write_text('{"ts":"2026-05-04T00:00:00Z","event":"close","coin":"BTC"}\n')

    with pytest.raises(JournalChainError, match="payload hash mismatch"):
        main([
            "verify",
            "--input",
            out["sidecar_path"],
            "--stream",
            "trades",
            "--raw-input",
            str(raw),
        ])


def test_bus_append_jsonl_writes_sidecar_for_decision_stream(tmp_path: Path) -> None:
    raw = tmp_path / "decisions.jsonl"
    record = {"ts": "2026-05-04T00:00:00Z", "coin": "ETH", "verdict": "reject"}

    append_jsonl(raw, record)

    chain_path = sidecar_path_for(raw, "decisions")
    entries = read_jsonl(chain_path)
    assert len(entries) == 1
    assert entries[0]["payload_hash"]
    assert verify_chain(entries, stream="decisions").count == 1


def test_bus_append_jsonl_does_not_sidecar_unlisted_stream(tmp_path: Path) -> None:
    raw = tmp_path / "metrics.jsonl"

    append_jsonl(raw, {"ts": "2026-05-04T00:00:00Z", "ok": True})

    assert not sidecar_path_for(raw, "metrics").exists()
