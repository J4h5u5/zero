from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from zero_engine.journal_chain import (
    JournalChainError,
    build_chain,
    build_entry,
    canonical_json,
    generate_root,
    main,
    read_jsonl,
    verify_root,
    verify_chain,
    verify_payload_binding,
)


def test_canonical_json_is_stable_for_hashing() -> None:
    left = {"b": 2, "a": {"z": 3, "y": 1}}
    right = {"a": {"y": 1, "z": 3}, "b": 2}

    assert canonical_json(left) == canonical_json(right)


def test_build_and_verify_chain() -> None:
    records = [
        {"ts": "2026-05-04T00:00:00Z", "event": "open", "coin": "ETH"},
        {"ts": "2026-05-04T00:01:00Z", "event": "close", "coin": "ETH"},
    ]

    chain = build_chain(records, stream="trades", deployment_id="dep_test")
    result = verify_chain(chain, stream="trades")

    assert result.stream == "trades"
    assert result.count == 2
    assert result.first_ts == "2026-05-04T00:00:00Z"
    assert result.last_ts == "2026-05-04T00:01:00Z"
    assert result.head_hash == chain[-1]["entry_hash"]


def test_payload_hash_tampering_fails_verification() -> None:
    chain = build_chain([{"ts": "2026-05-04T00:00:00Z", "event": "open"}], stream="trades")
    chain[0]["payload_hash"] = "sha256:" + ("f" * 64)

    with pytest.raises(JournalChainError, match="entry hash mismatch"):
        verify_chain(chain, stream="trades")


def test_previous_hash_tampering_fails_verification() -> None:
    chain = build_chain(
        [
            {"ts": "2026-05-04T00:00:00Z", "event": "open"},
            {"ts": "2026-05-04T00:01:00Z", "event": "close"},
        ],
        stream="trades",
    )
    chain[1]["prev_hash"] = chain[0]["prev_hash"]

    with pytest.raises(JournalChainError, match="previous hash mismatch"):
        verify_chain(chain, stream="trades")


def test_payload_binding_detects_raw_record_rewrite() -> None:
    original = [{"ts": "2026-05-04T00:00:00Z", "event": "open", "coin": "ETH"}]
    chain = build_chain(original, stream="trades")

    with pytest.raises(JournalChainError, match="payload hash mismatch"):
        verify_payload_binding(
            chain,
            [{"ts": "2026-05-04T00:00:00Z", "event": "open", "coin": "BTC"}],
            stream="trades",
        )


def test_payload_binding_detects_missing_raw_records() -> None:
    chain = build_chain(
        [
            {"ts": "2026-05-04T00:00:00Z", "event": "open"},
            {"ts": "2026-05-04T00:01:00Z", "event": "close"},
        ],
        stream="trades",
    )

    with pytest.raises(JournalChainError, match="payload binding count mismatch"):
        verify_payload_binding(chain, [{"ts": "2026-05-04T00:00:00Z", "event": "open"}])


def test_signed_entry_round_trips_with_public_key() -> None:
    key = Ed25519PrivateKey.generate()
    public_key = key.public_key()
    entry = build_entry(
        {"ts": "2026-05-04T00:00:00Z", "event": "safety_refusal"},
        stream="safety_refusals",
        seq=1,
        signing_key=key,
        signing_key_id="test-key-v1",
    )

    result = verify_chain(
        [entry],
        stream="safety_refusals",
        public_keys={"test-key-v1": public_key},
    )

    assert result.count == 1
    assert entry["signature"]


def test_signed_entry_requires_public_key() -> None:
    key = Ed25519PrivateKey.generate()
    entry = build_entry(
        {"ts": "2026-05-04T00:00:00Z", "event": "safety_refusal"},
        stream="safety_refusals",
        seq=1,
        signing_key=key,
        signing_key_id="test-key-v1",
    )
    entry.pop("signing_public_key_b64")

    with pytest.raises(JournalChainError, match="missing public key"):
        verify_chain([entry], stream="safety_refusals")


def test_generate_root_from_verified_streams() -> None:
    trades = verify_chain(build_chain([{"ts": "2026-05-04T00:00:00Z"}], stream="trades"))
    refusals = verify_chain(
        build_chain([{"ts": "2026-05-04T00:02:00Z"}], stream="safety_refusals")
    )

    root = generate_root([refusals, trades], generated_at="2026-05-04T00:03:00Z")

    assert root["version"] == "zero.journal_root.v1"
    assert root["streams"][0]["stream"] == "safety_refusals"
    assert root["streams"][1]["stream"] == "trades"
    assert root["root_hash"].startswith("sha256:")


def test_signed_root_round_trips_and_detects_tampering() -> None:
    key = Ed25519PrivateKey.generate()
    result = verify_chain(build_chain([{"ts": "2026-05-04T00:00:00Z"}], stream="trades"))
    root = generate_root([result], signing_key=key, signing_key_id="root-test-v1")

    assert verify_root(root) is True
    root["streams"][0]["count"] = 2

    with pytest.raises(JournalChainError, match="root hash mismatch"):
        verify_root(root)


def test_signed_entry_embeds_public_key_for_standalone_verify() -> None:
    key = Ed25519PrivateKey.generate()
    entry = build_entry(
        {"ts": "2026-05-04T00:00:00Z", "event": "close"},
        stream="trades",
        seq=1,
        signing_key=key,
        signing_key_id="entry-test-v1",
    )

    assert entry["signing_public_key_b64"]
    assert verify_chain([entry], stream="trades").count == 1


def test_read_jsonl_reports_line_numbers(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text('{"ok": true}\nnot-json\n')

    with pytest.raises(JournalChainError, match=r"bad\.jsonl:2: invalid JSONL"):
        read_jsonl(path)


def test_cli_wrap_verify_root_round_trip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    raw = tmp_path / "raw.jsonl"
    chain = tmp_path / "chain.jsonl"
    root = tmp_path / "root.json"
    raw.write_text('{"ts":"2026-05-04T00:00:00Z","event":"open"}\n')

    assert main(["wrap", "--input", str(raw), "--output", str(chain), "--stream", "trades"]) == 0
    assert main(["verify", "--input", str(chain), "--stream", "trades"]) == 0
    verify_output = capsys.readouterr().out
    assert '"count": 1' in verify_output

    assert main(["root", "--input", str(chain), "--output", str(root), "--stream", "trades"]) == 0
    assert '"root_hash": "sha256:' in root.read_text()
