import json
import base64
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption

from zero_engine.journal_chain import JournalChainError
from zero_engine.journal_root import (
    build_daily_root,
    default_stream_specs,
    main,
    parse_day,
    write_daily_root,
)
from zero_engine.journal_sidecar import append_sidecar_envelope
from zero_engine.journal_signing import SIGNING_KEY_ENV, SIGNING_KEY_ID_ENV


def test_default_stream_specs_include_dated_genesis(tmp_path: Path) -> None:
    specs = default_stream_specs(
        bus_dir=tmp_path / "bus",
        data_dir=tmp_path / "data",
        day=parse_day("2026-05-04"),
    )

    assert [spec.name for spec in specs] == [
        "trades",
        "events",
        "decisions",
        "rejections",
        "near_misses",
        "genesis",
    ]
    assert specs[-1].path.name == "2026-05-04.jsonl"


def test_build_daily_root_skips_missing_and_empty_streams(tmp_path: Path) -> None:
    data = tmp_path / "data"
    bus = tmp_path / "bus"
    data.mkdir()
    bus.mkdir()
    (data / "trades.jsonl").write_text('{"ts":"2026-05-04T00:00:00Z","event":"close"}\n')
    (bus / "events.jsonl").write_text("")

    root = build_daily_root(
        streams=default_stream_specs(bus_dir=bus, data_dir=data, day=parse_day("2026-05-04")),
        generated_at="2026-05-04T00:05:00Z",
        deployment_id="dep_test",
        sign_from_env=False,
    )

    assert root["version"] == "zero.journal_root.v1"
    assert root["deployment_id"] == "dep_test"
    assert [stream["stream"] for stream in root["streams"]] == ["trades"]
    assert root["source_manifest"][0]["records"] == 1
    assert root["source_manifest"][0]["proof_source"] == "derived_raw"
    assert root["source_manifest_hash"].startswith("sha256:")


def test_write_daily_root_creates_dated_file(tmp_path: Path) -> None:
    data = tmp_path / "data"
    bus = tmp_path / "bus"
    data.mkdir()
    bus.mkdir()
    (data / "trades.jsonl").write_text('{"ts":"2026-05-04T00:00:00Z","event":"close"}\n')

    out = write_daily_root(
        bus_dir=bus,
        data_dir=data,
        output_dir=tmp_path / "roots",
        day=parse_day("2026-05-04"),
        sign_from_env=False,
        anchor=False,
    )

    assert out.name == "journal-root-2026-05-04.json"
    payload = json.loads(out.read_text())
    assert payload["streams"][0]["stream"] == "trades"


def test_cli_generate_writes_root(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = tmp_path / "data"
    bus = tmp_path / "bus"
    roots = tmp_path / "roots"
    data.mkdir()
    bus.mkdir()
    (data / "trades.jsonl").write_text('{"ts":"2026-05-04T00:00:00Z","event":"close"}\n')

    assert main([
        "--bus-dir",
        str(bus),
        "--data-dir",
        str(data),
        "--output-dir",
        str(roots),
        "--day",
        "2026-05-04",
        "--no-sign-env",
        "--no-anchor",
    ]) == 0

    out_path = Path(capsys.readouterr().out.strip())
    assert out_path.exists()
    assert out_path.name == "journal-root-2026-05-04.json"


def test_build_daily_root_signs_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    bus = tmp_path / "bus"
    data.mkdir()
    bus.mkdir()
    (data / "trades.jsonl").write_text('{"ts":"2026-05-04T00:00:00Z","event":"close"}\n')
    raw_key = Ed25519PrivateKey.generate().private_bytes(
        Encoding.Raw,
        PrivateFormat.Raw,
        NoEncryption(),
    )
    monkeypatch.setenv(SIGNING_KEY_ENV, base64.urlsafe_b64encode(raw_key).decode("ascii"))
    monkeypatch.setenv(SIGNING_KEY_ID_ENV, "journal-test-v1")

    root = build_daily_root(
        streams=default_stream_specs(bus_dir=bus, data_dir=data, day=parse_day("2026-05-04")),
        generated_at="2026-05-04T00:05:00Z",
    )

    assert root["signing_key_id"] == "journal-test-v1"
    assert root["signing_public_key_b64"]
    assert root["signature"]


def test_build_daily_root_prefers_complete_live_sidecar(tmp_path: Path) -> None:
    data = tmp_path / "data"
    bus = tmp_path / "bus"
    data.mkdir()
    bus.mkdir()
    trade = {"ts": "2026-05-04T00:00:00Z", "event": "close"}
    trades_file = data / "trades.jsonl"
    trades_file.write_text(json.dumps(trade) + "\n")
    append_sidecar_envelope(trades_file, trade, stream="trades")

    root = build_daily_root(
        streams=default_stream_specs(bus_dir=bus, data_dir=data, day=parse_day("2026-05-04")),
        generated_at="2026-05-04T00:05:00Z",
        sign_from_env=False,
    )

    assert root["source_manifest"][0]["proof_source"] == "live_sidecar"
    assert root["source_manifest"][0]["sidecar_records"] == 1


def test_build_daily_root_rejects_complete_sidecar_bound_to_different_raw_payload(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    bus = tmp_path / "bus"
    data.mkdir()
    bus.mkdir()
    trades_file = data / "trades.jsonl"
    trade = {"ts": "2026-05-04T00:00:00Z", "event": "close", "coin": "ETH"}
    trades_file.write_text(json.dumps(trade) + "\n")
    append_sidecar_envelope(trades_file, trade, stream="trades")
    trades_file.write_text(
        json.dumps({"ts": "2026-05-04T00:00:00Z", "event": "close", "coin": "BTC"}) + "\n"
    )

    with pytest.raises(JournalChainError, match="payload hash mismatch"):
        build_daily_root(
            streams=default_stream_specs(bus_dir=bus, data_dir=data, day=parse_day("2026-05-04")),
            generated_at="2026-05-04T00:05:00Z",
            sign_from_env=False,
        )


def test_build_daily_root_falls_back_when_sidecar_is_partial(tmp_path: Path) -> None:
    data = tmp_path / "data"
    bus = tmp_path / "bus"
    data.mkdir()
    bus.mkdir()
    first = {"ts": "2026-05-04T00:00:00Z", "event": "close"}
    second = {"ts": "2026-05-04T00:01:00Z", "event": "close"}
    trades_file = data / "trades.jsonl"
    trades_file.write_text(json.dumps(first) + "\n" + json.dumps(second) + "\n")
    append_sidecar_envelope(trades_file, first, stream="trades")

    root = build_daily_root(
        streams=default_stream_specs(bus_dir=bus, data_dir=data, day=parse_day("2026-05-04")),
        generated_at="2026-05-04T00:05:00Z",
        sign_from_env=False,
    )

    assert root["source_manifest"][0]["proof_source"] == "derived_raw_sidecar_partial"
    assert root["source_manifest"][0]["records"] == 2
    assert root["source_manifest"][0]["sidecar_records"] == 1
