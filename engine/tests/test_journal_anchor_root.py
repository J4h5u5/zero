import json
import urllib.error
from pathlib import Path
from unittest.mock import patch

from zero_engine.journal_anchor import (
    anchor_root_file,
    build_anchor_payload,
    create_local_anchor,
    create_opentimestamps_anchor,
    main,
)
from zero_engine.journal_chain import JournalChainError
from zero_engine.journal_chain import verify_root
from zero_engine.journal_root import build_daily_root, default_stream_specs, parse_day, write_daily_root


def _root(tmp_path: Path) -> dict:
    data = tmp_path / "data"
    bus = tmp_path / "bus"
    data.mkdir()
    bus.mkdir()
    (data / "trades.jsonl").write_text('{"ts":"2026-05-04T00:00:00Z","event":"close"}\n')
    return build_daily_root(
        streams=default_stream_specs(bus_dir=bus, data_dir=data, day=parse_day("2026-05-04")),
        generated_at="2026-05-04T00:05:00Z",
        sign_from_env=False,
    )


def test_build_anchor_payload_is_minimal_and_verifiable(tmp_path: Path) -> None:
    root = _root(tmp_path)

    payload = build_anchor_payload(root)

    assert payload["version"] == "zero.journal_anchor.v1"
    assert payload["root_hash"] == root["root_hash"]
    assert payload["stream_count"] == 1


def test_create_local_anchor_writes_receipt(tmp_path: Path) -> None:
    root = _root(tmp_path)

    anchor = create_local_anchor(root, receipt_dir=tmp_path / "anchors", day="2026-05-04")

    receipt_path = Path(anchor["receipt_path"])
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text())
    assert receipt["root_hash"] == root["root_hash"]
    assert receipt["receipt_hash"] == anchor["receipt_hash"]


def test_anchor_root_file_preserves_root_verification(tmp_path: Path) -> None:
    root = _root(tmp_path)
    root_file = tmp_path / "journal-root-2026-05-04.json"
    root_file.write_text(json.dumps(root))

    anchor = anchor_root_file(root_file, provider="local", receipt_dir=tmp_path / "anchors")
    anchored_root = json.loads(root_file.read_text())

    assert anchor is not None
    assert anchored_root["anchor"]["provider"] == "local"
    assert verify_root(anchored_root) is True


def test_anchor_can_be_disabled(tmp_path: Path) -> None:
    root = _root(tmp_path)
    root_file = tmp_path / "journal-root-2026-05-04.json"
    root_file.write_text(json.dumps(root))

    assert anchor_root_file(root_file, provider="none", receipt_dir=tmp_path / "anchors") is None
    assert "anchor" not in json.loads(root_file.read_text())


def test_write_daily_root_attaches_local_anchor_by_default(tmp_path: Path) -> None:
    data = tmp_path / "data"
    bus = tmp_path / "bus"
    roots = tmp_path / "roots"
    data.mkdir()
    bus.mkdir()
    (data / "trades.jsonl").write_text('{"ts":"2026-05-04T00:00:00Z","event":"close"}\n')

    out = write_daily_root(
        bus_dir=bus,
        data_dir=data,
        output_dir=roots,
        day=parse_day("2026-05-04"),
        sign_from_env=False,
    )
    root = json.loads(out.read_text())

    assert root["anchor"]["provider"] == "local"
    assert (tmp_path / "journal-anchors" / "journal-anchor-2026-05-04.json").exists()


def test_cli_anchor_writes_anchor(tmp_path: Path, capsys) -> None:
    root = _root(tmp_path)
    root_file = tmp_path / "journal-root-2026-05-04.json"
    root_file.write_text(json.dumps(root))

    assert main([
        "--root",
        str(root_file),
        "--provider",
        "local",
        "--receipt-dir",
        str(tmp_path / "anchors"),
    ]) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["provider"] == "local"
    assert json.loads(root_file.read_text())["anchor"]["receipt_hash"] == out["receipt_hash"]


def test_create_opentimestamps_anchor_posts_raw_root_digest(tmp_path: Path) -> None:
    root = _root(tmp_path)
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"ots-proof-bytes"

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["data"] = request.data
        captured["timeout"] = timeout
        return FakeResponse()

    with patch("zero_engine.journal_anchor.urllib.request.urlopen", fake_urlopen):
        anchor = create_opentimestamps_anchor(root, calendars=["https://calendar.example"], timeout_s=7.0)

    assert captured["url"] == "https://calendar.example/digest"
    assert captured["data"] == bytes.fromhex(root["root_hash"].split(":", 1)[1])
    assert captured["timeout"] == 7.0
    assert anchor["provider"] == "opentimestamps"
    assert anchor["status"] == "pending"
    assert anchor["ots_proof_b64"]
    assert anchor["ots_proof_hash"].startswith("sha256:")


def test_create_opentimestamps_anchor_tries_next_calendar(tmp_path: Path) -> None:
    root = _root(tmp_path)
    calls = []

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"second-proof"

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            raise urllib.error.URLError("down")
        return FakeResponse()

    with patch("zero_engine.journal_anchor.urllib.request.urlopen", fake_urlopen):
        anchor = create_opentimestamps_anchor(root, calendars=["https://a.example", "https://b.example"])

    assert calls == ["https://a.example/digest", "https://b.example/digest"]
    assert anchor["calendar_url"] == "https://b.example"


def test_create_opentimestamps_anchor_fails_when_all_calendars_fail(tmp_path: Path) -> None:
    root = _root(tmp_path)

    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("down")

    with patch("zero_engine.journal_anchor.urllib.request.urlopen", fake_urlopen):
        try:
            create_opentimestamps_anchor(root, calendars=["https://a.example"])
        except JournalChainError as exc:
            assert "OpenTimestamps anchoring failed" in str(exc)
        else:
            raise AssertionError("expected JournalChainError")
