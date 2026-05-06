import json
from pathlib import Path

from zero_engine.journal_anchor import anchor_root_file
from zero_engine.journal_proof_pack import build_public_proof, main, render_markdown, write_proof_pack
from zero_engine.journal_root import write_daily_root, parse_day


def _root_file(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    bus = tmp_path / "bus"
    roots = tmp_path / "roots"
    data.mkdir()
    bus.mkdir()
    (data / "trades.jsonl").write_text('{"ts":"2026-05-04T00:00:00Z","event":"close"}\n')
    root = write_daily_root(
        bus_dir=bus,
        data_dir=data,
        output_dir=roots,
        day=parse_day("2026-05-04"),
        sign_from_env=False,
        anchor=False,
    )
    anchor_root_file(root, provider="local", receipt_dir=tmp_path / "anchors")
    return root


def test_build_public_proof_redacts_local_paths(tmp_path: Path) -> None:
    root_file = _root_file(tmp_path)
    root = json.loads(root_file.read_text())

    proof = build_public_proof(root, root_file_name=root_file.name)

    assert proof["version"] == "zero.proof_pack.v1"
    assert proof["root_hash"] == root["root_hash"]
    assert proof["anchor"]["provider"] == "local"
    assert "ots_proof_hash" in proof["anchor"]
    assert proof["sources"][0]["stream"] == "trades"
    assert "path" not in proof["sources"][0]
    assert "sidecar_path" not in proof["sources"][0]
    assert str(tmp_path) not in json.dumps(proof)


def test_render_markdown_contains_hashes_not_raw_payloads(tmp_path: Path) -> None:
    root_file = _root_file(tmp_path)
    proof = build_public_proof(json.loads(root_file.read_text()), root_file_name=root_file.name)

    md = render_markdown(proof)

    assert "# ZERO Proof Pack" in md
    assert proof["root_hash"] in md
    assert "raw trade rows" in md
    assert '"event":"close"' not in md


def test_write_proof_pack_outputs_json_and_markdown(tmp_path: Path) -> None:
    root_file = _root_file(tmp_path)

    json_path, md_path = write_proof_pack(root_file, output_dir=tmp_path / "proof")

    assert json_path.exists()
    assert md_path.exists()
    proof = json.loads(json_path.read_text())
    assert proof["root_file"] == root_file.name
    assert "ZERO Proof Pack" in md_path.read_text()


def test_cli_generates_proof_pack(tmp_path: Path, capsys) -> None:
    root_file = _root_file(tmp_path)

    assert main(["--root", str(root_file), "--output-dir", str(tmp_path / "proof")]) == 0

    out = json.loads(capsys.readouterr().out)
    assert Path(out["json"]).exists()
    assert Path(out["markdown"]).exists()
