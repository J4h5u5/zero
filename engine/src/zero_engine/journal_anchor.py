"""Timestamp anchoring for signed journal roots.

Anchors are proof metadata attached after root signing. The root hash and root
signature deliberately exclude the `anchor` field, so adding a receipt cannot
change the evidence being anchored.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zero_engine.journal_chain import JournalChainError, canonical_json, sha256_hex, verify_root


ANCHOR_VERSION = "zero.journal_anchor.v1"
ANCHOR_PROVIDER_ENV = "ZERO_JOURNAL_ANCHOR_PROVIDER"
ANCHOR_WEBHOOK_URL_ENV = "ZERO_JOURNAL_ANCHOR_WEBHOOK_URL"
ANCHOR_WEBHOOK_TOKEN_ENV = "ZERO_JOURNAL_ANCHOR_WEBHOOK_TOKEN"
ANCHOR_OTS_CALENDARS_ENV = "ZERO_JOURNAL_OTS_CALENDARS"
DEFAULT_OTS_CALENDARS = (
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_anchor_payload(root: dict[str, Any]) -> dict[str, Any]:
    """Return the minimal payload that external timestamp services should anchor."""
    verify_root(root)
    return {
        "version": ANCHOR_VERSION,
        "root_version": root.get("version"),
        "root_hash": root.get("root_hash"),
        "root_signature_hash": sha256_hex(str(root.get("signature", ""))),
        "signing_key_id": root.get("signing_key_id", ""),
        "generated_at": root.get("generated_at", ""),
        "stream_count": len(root.get("streams", [])),
    }


def create_local_anchor(root: dict[str, Any], *, receipt_dir: Path, day: str | None = None) -> dict[str, Any]:
    """Write a local timestamp receipt and return the receipt metadata."""
    payload = build_anchor_payload(root)
    root_day = day or str(root.get("generated_at", ""))[:10] or datetime.now(timezone.utc).date().isoformat()
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt: dict[str, Any] = {
        **payload,
        "provider": "local",
        "anchored_at": now_utc_iso(),
        "status": "local_only",
    }
    receipt["receipt_hash"] = sha256_hex(canonical_json(receipt))
    receipt_path = receipt_dir / f"journal-anchor-{root_day}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return {
        "version": ANCHOR_VERSION,
        "provider": "local",
        "status": "local_only",
        "anchored_at": receipt["anchored_at"],
        "receipt_hash": receipt["receipt_hash"],
        "receipt_path": str(receipt_path),
    }


def create_webhook_anchor(root: dict[str, Any], *, url: str, token: str = "", timeout_s: float = 10.0) -> dict[str, Any]:
    """Post an anchor payload to an operator-controlled timestamp webhook."""
    payload = build_anchor_payload(root)
    request_body = json.dumps(payload, sort_keys=True).encode("utf-8")
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=request_body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = response.read().decode("utf-8")
            try:
                receipt_body = json.loads(body) if body else {}
            except json.JSONDecodeError:
                receipt_body = {"body": body[:500]}
            status_code = int(getattr(response, "status", 200))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise JournalChainError(f"webhook anchor failed: {exc}") from exc

    receipt = {
        "version": ANCHOR_VERSION,
        "provider": "webhook",
        "status": "anchored" if 200 <= status_code < 300 else "failed",
        "anchored_at": now_utc_iso(),
        "url": url,
        "http_status": status_code,
        "receipt_body_hash": sha256_hex(canonical_json(receipt_body)),
    }
    if not 200 <= status_code < 300:
        raise JournalChainError(f"webhook anchor failed with status {status_code}")
    return receipt


def _root_hash_bytes(root_hash: str) -> bytes:
    if not root_hash.startswith("sha256:"):
        raise JournalChainError("root_hash must be sha256-prefixed for OpenTimestamps anchoring")
    try:
        digest = bytes.fromhex(root_hash.split(":", 1)[1])
    except ValueError as exc:
        raise JournalChainError("root_hash is not valid hex") from exc
    if len(digest) != 32:
        raise JournalChainError("root_hash must decode to a 32-byte sha256 digest")
    return digest


def _calendar_digest_url(calendar_url: str) -> str:
    return calendar_url.rstrip("/") + "/digest"


def create_opentimestamps_anchor(
    root: dict[str, Any],
    *,
    calendars: list[str] | tuple[str, ...] | None = None,
    timeout_s: float = 10.0,
) -> dict[str, Any]:
    """Submit the root hash to OpenTimestamps calendar servers."""
    payload = build_anchor_payload(root)
    digest = _root_hash_bytes(str(payload["root_hash"]))
    selected_calendars = list(calendars or DEFAULT_OTS_CALENDARS)
    if not selected_calendars:
        raise JournalChainError("at least one OpenTimestamps calendar is required")

    errors: list[str] = []
    for calendar in selected_calendars:
        request = urllib.request.Request(
            _calendar_digest_url(calendar),
            data=digest,
            headers={"content-type": "application/octet-stream"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                proof = response.read()
                status_code = int(getattr(response, "status", 200))
        except (urllib.error.URLError, TimeoutError) as exc:
            errors.append(f"{calendar}: {exc}")
            continue
        if not 200 <= status_code < 300:
            errors.append(f"{calendar}: http {status_code}")
            continue
        if not proof:
            errors.append(f"{calendar}: empty proof")
            continue
        return {
            "version": ANCHOR_VERSION,
            "provider": "opentimestamps",
            "status": "pending",
            "anchored_at": now_utc_iso(),
            "calendar_url": calendar,
            "calendar_digest_url": _calendar_digest_url(calendar),
            "root_hash": payload["root_hash"],
            "ots_proof_b64": base64.b64encode(proof).decode("ascii"),
            "ots_proof_hash": sha256_hex(proof),
            "calendar_http_status": status_code,
            "receipt_hash": sha256_hex(canonical_json({
                "provider": "opentimestamps",
                "root_hash": payload["root_hash"],
                "calendar_url": calendar,
                "ots_proof_hash": sha256_hex(proof),
            })),
        }
    raise JournalChainError("OpenTimestamps anchoring failed: " + "; ".join(errors))


def anchor_root(
    root: dict[str, Any],
    *,
    provider: str | None = None,
    receipt_dir: Path | None = None,
    day: str | None = None,
    webhook_url: str | None = None,
    webhook_token: str | None = None,
) -> dict[str, Any] | None:
    """Create an anchor receipt for a root. Returns None when disabled."""
    selected = (provider or os.environ.get(ANCHOR_PROVIDER_ENV) or "local").strip().lower()
    if selected in {"", "none", "off", "disabled"}:
        return None
    if selected == "local":
        return create_local_anchor(root, receipt_dir=receipt_dir or Path("journal-anchors"), day=day)
    if selected == "webhook":
        url = webhook_url or os.environ.get(ANCHOR_WEBHOOK_URL_ENV, "")
        if not url:
            raise JournalChainError(f"{ANCHOR_WEBHOOK_URL_ENV} is required for webhook anchoring")
        return create_webhook_anchor(root, url=url, token=webhook_token or os.environ.get(ANCHOR_WEBHOOK_TOKEN_ENV, ""))
    if selected in {"ots", "opentimestamps"}:
        calendars_raw = os.environ.get(ANCHOR_OTS_CALENDARS_ENV, "")
        calendars = [item.strip() for item in calendars_raw.split(",") if item.strip()] if calendars_raw else None
        return create_opentimestamps_anchor(root, calendars=calendars)
    raise JournalChainError(f"unknown journal anchor provider: {selected}")


def anchor_root_file(
    root_path: Path | str,
    *,
    provider: str | None = None,
    receipt_dir: Path | None = None,
    day: str | None = None,
    webhook_url: str | None = None,
    webhook_token: str | None = None,
) -> dict[str, Any] | None:
    """Attach an anchor receipt to a root JSON file."""
    path = Path(root_path)
    root = json.loads(path.read_text())
    anchor = anchor_root(
        root,
        provider=provider,
        receipt_dir=receipt_dir,
        day=day,
        webhook_url=webhook_url,
        webhook_token=webhook_token,
    )
    if anchor is None:
        return None
    root["anchor"] = anchor
    verify_root(root)
    path.write_text(json.dumps(root, indent=2, sort_keys=True) + "\n")
    return anchor


def _cmd_anchor(args: argparse.Namespace) -> int:
    try:
        anchor = anchor_root_file(
            args.root,
            provider=args.provider,
            receipt_dir=args.receipt_dir,
            webhook_url=args.webhook_url,
        )
    except JournalChainError as exc:
        raise SystemExit(f"journal anchor failed: {exc}") from exc
    print(json.dumps(anchor or {"status": "disabled"}, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Anchor a ZERO journal root")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--provider", default=None, help="local, webhook, or none")
    parser.add_argument("--receipt-dir", type=Path)
    parser.add_argument("--webhook-url")
    parser.set_defaults(func=_cmd_anchor)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
