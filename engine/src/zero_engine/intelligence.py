from __future__ import annotations

import html
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zero_engine.network import assert_public_profile_safe

COMMERCIAL_CONTRACT_SCHEMA_VERSION = "zero.intelligence.commercial.v1"


@dataclass(frozen=True)
class IntelligenceConfig:
    public_delay_s: int = 900
    export_path: str | None = None

    def __post_init__(self) -> None:
        if self.public_delay_s < 0:
            raise ValueError("intelligence public delay must be non-negative")


@dataclass(frozen=True)
class HostedIntelligenceStore:
    """Append-only stdlib store for hosted-compatible intelligence records."""

    path: str | Path

    def append(
        self,
        record_type: str,
        payload: dict[str, Any],
        *,
        recorded_at: str,
    ) -> dict[str, Any]:
        if record_type not in {"snapshot", "usage_event", "webhook_subscription", "export_job"}:
            raise ValueError(f"unsupported hosted intelligence record type: {record_type}")
        record = {
            "schema_version": "zero.intelligence.store_record.v1",
            "record_type": record_type,
            "recorded_at": recorded_at,
            "payload": payload,
            "privacy": {
                "aggregate_only": True,
                "raw_private_data": False,
                "token_material_included": False,
            },
        }
        assert_intelligence_safe(record)
        path = Path(self.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        return record

    def records(self, *, record_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        path = Path(self.path)
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("schema_version") != "zero.intelligence.store_record.v1":
                continue
            if record_type and record.get("record_type") != record_type:
                continue
            rows.append(record)
        return rows[-limit:]

    def snapshots(self, *, limit: int = 100) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        for record in self.records(record_type="snapshot", limit=limit):
            payload = record.get("payload", {})
            if isinstance(payload, dict) and isinstance(payload.get("snapshot"), dict):
                snapshots.append(payload["snapshot"])
        return snapshots


def stable_hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def account_hash(account_id: str) -> str:
    return stable_hash(account_id)


def intelligence_snapshot(
    profile: dict[str, Any],
    *,
    generated_at: str,
    config: IntelligenceConfig | None = None,
) -> dict[str, Any]:
    cfg = config or IntelligenceConfig()
    metrics = profile.get("metrics", {})
    proof_hash = profile.get("verification", {}).get("proof_hash", "")
    deployment_claim_hash = profile.get("verification", {}).get("deployment_claim_hash", "")
    deployment_heartbeat_hash = profile.get("verification", {}).get("deployment_heartbeat_hash", "")
    snapshot = {
        "schema_version": "zero.intelligence.snapshot.v1",
        "generated_at": generated_at,
        "access": {
            "class": "public_delayed",
            "delay_s": cfg.public_delay_s,
            "commercial_realtime": True,
            "commercial_history": True,
            "commercial_redistribution": True,
        },
        "source": {
            "schema_version": profile.get("schema_version"),
            "proof_hash": proof_hash,
            "deployment_claim_hash": deployment_claim_hash,
            "deployment_heartbeat_hash": deployment_heartbeat_hash,
            "mode": profile.get("mode", "paper"),
            "verification_status": profile.get("verification", {}).get("status", "empty"),
        },
        "signals": {
            "activity_level": activity_level(int(metrics.get("decisions", 0))),
            "rejection_discipline": rejection_discipline(float(metrics.get("rejection_rate", 0.0))),
            "execution_pressure": execution_pressure(float(metrics.get("acceptance_rate", 0.0))),
            "journal_quality": "durable" if metrics.get("journal_durable") else "ephemeral",
            "live_observed": int(metrics.get("live_execution_count", 0)) > 0,
        },
        "aggregates": {
            "decisions": int(metrics.get("decisions", 0)),
            "fills": int(metrics.get("fills", 0)),
            "rejections": int(metrics.get("rejections", 0)),
            "open_positions": int(metrics.get("open_positions", 0)),
            "acceptance_rate": float(metrics.get("acceptance_rate", 0.0)),
            "rejection_rate": float(metrics.get("rejection_rate", 0.0)),
            "total_notional_usd": float(metrics.get("total_notional_usd", 0.0)),
        },
        "commercial_unlocks": [
            "realtime feed",
            "longer history",
            "cohort analytics",
            "benchmark analytics",
            "webhooks",
            "bulk exports",
            "commercial redistribution rights",
            "enterprise reliability commitments",
        ],
        "privacy": {
            "default": "aggregate-only",
            "decision_records_included": False,
            "contains_exchange_credentials": False,
            "contains_private_notes": False,
            "inherits": profile.get("privacy", {}),
        },
    }
    assert_intelligence_safe(snapshot)
    return snapshot


def intelligence_catalog(*, generated_at: str, public_delay_s: int = 900) -> dict[str, Any]:
    commercial_contract = intelligence_commercial_contract(
        generated_at=generated_at,
        public_delay_s=public_delay_s,
    )
    catalog = {
        "schema_version": "zero.intelligence.catalog.v1",
        "generated_at": generated_at,
        "positioning": "commercial data product created by verified autonomous behavior",
        "public": {
            "runtime": "open-source",
            "network_profiles": "open",
            "leaderboards": "open",
            "model_gateway_status": {
                "schema_version": "zero.model_gateway.status.v1",
                "endpoint": "GET /intelligence/model-gateway",
                "default": "fail_closed unless an operator configures a provider",
            },
            "model_gateway_health": {
                "schema_version": "zero.model_gateway.health.v1",
                "endpoint": "GET /intelligence/model-gateway/health",
                "default": "config-only; explicit network=true required for provider probe",
            },
            "model_gateway_audit": {
                "schema_version": "zero.model_gateway.audit.v1",
                "endpoint": "GET /intelligence/model-gateway/audit",
                "default": "production model operations bundle without prompts or raw outputs",
            },
            "delayed_snapshots": {
                "schema_version": "zero.intelligence.snapshot.v1",
                "delay_s": public_delay_s,
                "endpoint": "GET /intelligence/snapshot",
            },
        },
        "commercial": {
            "metered_by": ["freshness", "history", "scale", "webhooks", "exports", "SLA"],
            "not_metered_by": ["local runtime use", "paper mode", "self-custodial operation"],
            "plans": [
                {
                    "name": "free",
                    "scopes": ["intelligence:read:delayed"],
                    "limits": "low public quota",
                },
                {
                    "name": "pro_operator",
                    "scopes": [
                        "intelligence:read:realtime",
                        "intelligence:read:history",
                        "intelligence:webhooks",
                    ],
                    "limits": "subscription quota",
                },
                {
                    "name": "team_fund",
                    "scopes": [
                        "intelligence:read:realtime",
                        "intelligence:read:history",
                        "intelligence:cohorts",
                        "intelligence:exports",
                        "intelligence:webhooks",
                    ],
                    "limits": "subscription plus usage",
                },
                {
                    "name": "enterprise",
                    "scopes": [
                        "intelligence:read:realtime",
                        "intelligence:read:history",
                        "intelligence:cohorts",
                        "intelligence:exports",
                        "intelligence:webhooks",
                        "intelligence:redistribute",
                    ],
                    "limits": "contract SLO and redistribution terms",
                },
            ],
        },
        "hosted_api_contract": {
            "schema_version": COMMERCIAL_CONTRACT_SCHEMA_VERSION,
            "endpoint": "GET /intelligence/commercial",
            "auth": commercial_contract["auth"],
            "rate_limit_headers": commercial_contract["rate_limits"]["headers"],
            "datasets": [dataset["name"] for dataset in commercial_contract["datasets"]],
            "endpoints": [endpoint["path"] for endpoint in commercial_contract["endpoints"]],
        },
        "data_rules": {
            "source": "verified redacted network proof packets",
            "raw_operator_data": "excluded unless explicitly consented and contracted",
            "exchange_credentials": "never collected",
            "custody": "never transferred",
        },
    }
    assert_intelligence_safe(catalog)
    return catalog


def public_intelligence_catalog_page(catalog: dict[str, Any], *, generated_at: str) -> str:
    if catalog.get("schema_version") != "zero.intelligence.catalog.v1":
        raise ValueError("intelligence catalog page requires zero.intelligence.catalog.v1")
    assert_intelligence_safe(catalog)

    public = catalog.get("public", {})
    commercial = catalog.get("commercial", {})
    hosted = catalog.get("hosted_api_contract", {})
    data_rules = catalog.get("data_rules", {})
    plans = commercial.get("plans", [])
    if not isinstance(public, dict):
        raise ValueError("intelligence catalog public section must be an object")
    if not isinstance(commercial, dict):
        raise ValueError("intelligence catalog commercial section must be an object")
    if not isinstance(hosted, dict):
        raise ValueError("intelligence catalog hosted_api_contract section must be an object")
    if not isinstance(data_rules, dict):
        raise ValueError("intelligence catalog data_rules section must be an object")
    if not isinstance(plans, list):
        raise ValueError("intelligence catalog commercial plans must be a list")

    public_rows = "\n".join(
        _catalog_public_row(name, value) for name, value in public.items()
    )
    plan_rows = "\n".join(_catalog_plan_row(plan) for plan in plans if isinstance(plan, dict))
    endpoint_rows = "\n".join(
        f"          <li><code>{_escape(str(endpoint))}</code></li>"
        for endpoint in _as_list(hosted.get("endpoints"))
    )
    dataset_rows = "\n".join(
        f"          <li>{_escape(str(dataset))}</li>" for dataset in _as_list(hosted.get("datasets"))
    )
    metered_rows = "\n".join(
        f"          <li>{_escape(str(item))}</li>" for item in _as_list(commercial.get("metered_by"))
    )
    not_metered_rows = "\n".join(
        f"          <li>{_escape(str(item))}</li>"
        for item in _as_list(commercial.get("not_metered_by"))
    )
    data_rule_rows = "\n".join(
        f"          <li><span>{_label(key)}</span><strong>{_escape(str(value))}</strong></li>"
        for key, value in data_rules.items()
    )
    timestamp = _escape(generated_at)
    delay_s = _escape(str(public.get("delayed_snapshots", {}).get("delay_s", "unknown")))
    positioning = _escape(str(catalog.get("positioning", "")))
    auth_scheme = _escape(str(hosted.get("auth", {}).get("scheme", "none")))
    contract_schema = _escape(str(hosted.get("schema_version", "unknown")))

    page = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>ZERO Intelligence Catalog</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f7f8f8;
        --ink: #111614;
        --muted: #5d6864;
        --line: #d9dfdc;
        --panel: #ffffff;
        --accent: #0b6b53;
        --accent-soft: #dff2eb;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background: var(--bg);
        color: var(--ink);
        font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        line-height: 1.5;
      }}
      main {{
        max-width: 1120px;
        margin: 0 auto;
        padding: 56px 24px;
      }}
      header {{
        display: grid;
        gap: 12px;
        padding-bottom: 28px;
        border-bottom: 1px solid var(--line);
      }}
      h1 {{
        margin: 0;
        font-size: clamp(2.5rem, 6vw, 5rem);
        line-height: 0.98;
        letter-spacing: 0;
      }}
      h2 {{
        margin: 0 0 10px;
        font-size: 1.05rem;
      }}
      p {{
        margin: 0;
        color: var(--muted);
      }}
      code {{
        overflow-wrap: anywhere;
        color: var(--accent);
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        font-size: 0.84rem;
      }}
      .eyebrow {{
        color: var(--muted);
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }}
      .summary {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin: 28px 0;
      }}
      .grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 18px;
        margin: 28px 0;
      }}
      .panel {{
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 18px;
      }}
      .label {{
        color: var(--muted);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}
      .value {{
        margin-top: 8px;
        font-size: 1.25rem;
        font-weight: 700;
      }}
      .rules, .rows {{
        display: grid;
        gap: 10px;
        margin: 0;
        padding: 0;
        list-style: none;
      }}
      .rules li, .rows li {{
        border-bottom: 1px solid var(--line);
        padding-bottom: 10px;
      }}
      .rules li:last-child, .rows li:last-child {{ border-bottom: 0; padding-bottom: 0; }}
      .rows span {{
        display: block;
        color: var(--muted);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}
      .rows strong {{
        display: block;
        margin-top: 3px;
      }}
      .plans {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
      }}
      .plan {{
        border-left: 4px solid var(--accent);
      }}
      .plan ul {{
        margin: 10px 0 0;
        padding-left: 18px;
        color: var(--muted);
      }}
      a {{
        color: var(--accent);
        font-weight: 700;
        text-decoration: none;
      }}
      a:hover {{ text-decoration: underline; }}
      footer {{
        margin-top: 28px;
        color: var(--muted);
        font-size: 0.9rem;
      }}
      @media (max-width: 900px) {{
        main {{ padding: 36px 16px; }}
        .summary, .grid, .plans {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <header>
        <div class="eyebrow">ZERO Intelligence</div>
        <h1>Public Catalog</h1>
        <p>{positioning}. Open runtime and delayed public surfaces stay inspectable; freshness, history, scale, webhooks, exports, and SLAs are commercial.</p>
      </header>
      <section class="summary" aria-label="Catalog summary">
        <div class="panel"><div class="label">Runtime</div><div class="value">{_escape(str(public.get("runtime", "open-source")))}</div></div>
        <div class="panel"><div class="label">Snapshots</div><div class="value">{delay_s}s delay</div></div>
        <div class="panel"><div class="label">Hosted Auth</div><div class="value">{auth_scheme}</div></div>
        <div class="panel"><div class="label">Contract</div><div class="value"><code>{contract_schema}</code></div></div>
      </section>
      <section class="grid" aria-label="Public and commercial boundary">
        <div class="panel">
          <h2>Public Runtime Surfaces</h2>
          <ul class="rows">
{public_rows}
          </ul>
        </div>
        <div class="panel">
          <h2>Commercial Metering</h2>
          <ul class="rules">
{metered_rows}
          </ul>
        </div>
        <div class="panel">
          <h2>Never Metered</h2>
          <ul class="rules">
{not_metered_rows}
          </ul>
        </div>
        <div class="panel">
          <h2>Data Rules</h2>
          <ul class="rows">
{data_rule_rows}
          </ul>
        </div>
      </section>
      <section class="plans" aria-label="Commercial plans">
{plan_rows}
      </section>
      <section class="grid" aria-label="Hosted API contract">
        <div class="panel">
          <h2>Hosted Endpoints</h2>
          <ul class="rules">
{endpoint_rows}
          </ul>
        </div>
        <div class="panel">
          <h2>Datasets</h2>
          <ul class="rules">
{dataset_rows}
          </ul>
        </div>
      </section>
      <section class="panel">
        <h2>Checked Contracts</h2>
        <p><a href="catalog.json">catalog.json</a> · <a href="commercial.json">commercial.json</a> · <a href="snapshot.json">snapshot.json</a> · <a href="model_gateway.json">model_gateway.json</a></p>
      </section>
      <footer>
        Generated {timestamp}. This page is a deterministic public contract view. It does not imply hosted realtime availability, guaranteed returns, custody, or live trading by default.
      </footer>
    </main>
  </body>
</html>
"""
    assert_public_profile_safe({"html": page})
    return page


def intelligence_commercial_contract(
    *,
    generated_at: str,
    public_delay_s: int = 900,
) -> dict[str, Any]:
    contract = {
        "schema_version": COMMERCIAL_CONTRACT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "positioning": "ZERO Intelligence API monetizes verified autonomous behavior, not runtime access",
        "boundary": {
            "open": [
                "local runtime",
                "paper mode",
                "self-custodial operation",
                "public profiles",
                "public leaderboards",
                "delayed public snapshots",
            ],
            "commercial": [
                "fresh realtime access",
                "history",
                "cohorts",
                "benchmarks",
                "webhooks",
                "bulk exports",
                "commercial redistribution",
                "reliability commitments",
            ],
            "not_sold": [
                "custody",
                "basic execution safety",
                "local private journals",
                "operator secrets",
            ],
        },
        "auth": {
            "scheme": "bearer",
            "credential": "hosted ZERO Intelligence API token",
            "runtime_required": False,
            "local_runtime_enforcement": "not enforced by the open-source runtime",
        },
        "plans": [
            {
                "id": "free",
                "name": "Free",
                "billing": "public quota",
                "scopes": ["intelligence:read:delayed"],
                "freshness": f"delayed >= {public_delay_s}s",
                "included_usage_events": ["snapshot.delayed.read"],
            },
            {
                "id": "pro_operator",
                "name": "Pro Operator",
                "billing": "subscription",
                "scopes": [
                    "intelligence:read:realtime",
                    "intelligence:read:history",
                    "intelligence:webhooks",
                ],
                "freshness": "realtime",
                "included_usage_events": [
                    "snapshot.realtime.read",
                    "history.query",
                    "webhook.delivery",
                ],
            },
            {
                "id": "team_fund",
                "name": "Team/Fund",
                "billing": "subscription plus usage",
                "scopes": [
                    "intelligence:read:realtime",
                    "intelligence:read:history",
                    "intelligence:cohorts",
                    "intelligence:benchmarks",
                    "intelligence:exports",
                    "intelligence:webhooks",
                ],
                "freshness": "realtime plus historical",
                "included_usage_events": [
                    "snapshot.realtime.read",
                    "history.query",
                    "cohort.query",
                    "benchmark.query",
                    "export.created",
                    "webhook.delivery",
                ],
            },
            {
                "id": "enterprise",
                "name": "Enterprise",
                "billing": "contract",
                "scopes": [
                    "intelligence:read:realtime",
                    "intelligence:read:history",
                    "intelligence:cohorts",
                    "intelligence:benchmarks",
                    "intelligence:exports",
                    "intelligence:webhooks",
                    "intelligence:redistribute",
                ],
                "freshness": "contract SLO",
                "included_usage_events": [
                    "snapshot.realtime.read",
                    "history.query",
                    "cohort.query",
                    "benchmark.query",
                    "export.created",
                    "webhook.delivery",
                    "redistribution.reported",
                ],
            },
        ],
        "scopes": [
            {
                "name": "intelligence:read:delayed",
                "description": "read delayed aggregate public snapshots",
                "commercial": False,
            },
            {
                "name": "intelligence:read:realtime",
                "description": "read fresh verified behavior snapshots",
                "commercial": True,
            },
            {
                "name": "intelligence:read:history",
                "description": "query historical verified behavior",
                "commercial": True,
            },
            {
                "name": "intelligence:cohorts",
                "description": "query cohort analytics",
                "commercial": True,
            },
            {
                "name": "intelligence:benchmarks",
                "description": "query benchmark analytics",
                "commercial": True,
            },
            {
                "name": "intelligence:exports",
                "description": "create bulk exports",
                "commercial": True,
            },
            {
                "name": "intelligence:webhooks",
                "description": "subscribe to event delivery",
                "commercial": True,
            },
            {
                "name": "intelligence:redistribute",
                "description": "redistribute intelligence commercially",
                "commercial": True,
            },
        ],
        "datasets": [
            {
                "name": "verified_behavior_snapshots",
                "source": "accepted ZERO Network ingestion packets",
                "public_delay_s": public_delay_s,
                "raw_private_data": False,
            },
            {
                "name": "risk_operations_history",
                "source": "aggregate risk, rejection, liveness, and breaker history",
                "public_delay_s": public_delay_s,
                "raw_private_data": False,
            },
            {
                "name": "cohort_benchmarks",
                "source": "aggregated cohorts from verified public-safe packets",
                "public_delay_s": public_delay_s,
                "raw_private_data": False,
            },
            {
                "name": "leaderboard_history",
                "source": "accepted leaderboard rows over time",
                "public_delay_s": public_delay_s,
                "raw_private_data": False,
            },
        ],
        "endpoints": [
            {
                "path": "GET /v1/intelligence/snapshots",
                "required_scope": "intelligence:read:delayed or intelligence:read:realtime",
                "usage_event": "snapshot.delayed.read or snapshot.realtime.read",
            },
            {
                "path": "GET /v1/intelligence/history",
                "required_scope": "intelligence:read:history",
                "usage_event": "history.query",
            },
            {
                "path": "GET /v1/intelligence/cohorts",
                "required_scope": "intelligence:cohorts",
                "usage_event": "cohort.query",
            },
            {
                "path": "GET /v1/intelligence/benchmarks",
                "required_scope": "intelligence:benchmarks",
                "usage_event": "benchmark.query",
            },
            {
                "path": "POST /v1/intelligence/webhooks",
                "required_scope": "intelligence:webhooks",
                "usage_event": "webhook.subscription.created",
            },
            {
                "path": "POST /v1/intelligence/exports",
                "required_scope": "intelligence:exports",
                "usage_event": "export.created",
            },
        ],
        "rate_limits": {
            "headers": [
                "x-zero-ratelimit-limit",
                "x-zero-ratelimit-remaining",
                "x-zero-ratelimit-reset",
                "x-zero-ratelimit-policy",
            ],
            "policy": [
                {
                    "plan": "free",
                    "window": "1h",
                    "unit": "requests",
                    "public_quota": True,
                },
                {
                    "plan": "pro_operator",
                    "window": "1m",
                    "unit": "requests plus webhook deliveries",
                    "public_quota": False,
                },
                {
                    "plan": "team_fund",
                    "window": "1m",
                    "unit": "requests, exports, and webhook deliveries",
                    "public_quota": False,
                },
                {
                    "plan": "enterprise",
                    "window": "contract",
                    "unit": "SLO-backed capacity",
                    "public_quota": False,
                },
            ],
        },
        "usage_events": [
            {
                "name": "snapshot.delayed.read",
                "metered": False,
                "billable": False,
                "required_fields": ["account_id", "scope", "dataset", "timestamp"],
            },
            {
                "name": "snapshot.realtime.read",
                "metered": True,
                "billable": True,
                "required_fields": ["account_id", "scope", "dataset", "timestamp", "freshness_ms"],
            },
            {
                "name": "history.query",
                "metered": True,
                "billable": True,
                "required_fields": ["account_id", "scope", "dataset", "timestamp", "rows_returned"],
            },
            {
                "name": "webhook.delivery",
                "metered": True,
                "billable": True,
                "required_fields": ["account_id", "scope", "event_type", "timestamp", "delivery_status"],
            },
            {
                "name": "export.created",
                "metered": True,
                "billable": True,
                "required_fields": ["account_id", "scope", "dataset", "timestamp", "rows_exported"],
            },
            {
                "name": "redistribution.reported",
                "metered": True,
                "billable": True,
                "required_fields": ["account_id", "scope", "dataset", "timestamp", "distribution_channel"],
            },
        ],
        "webhooks": {
            "event_types": [
                "snapshot.accepted",
                "cohort.updated",
                "benchmark.updated",
                "leaderboard.updated",
                "risk_regime.changed",
            ],
            "delivery": {
                "signing": "hosted webhook signatures required",
                "retries": "bounded retry with dead-letter visibility",
                "payloads": "aggregate-only",
            },
        },
        "exports": {
            "formats": ["jsonl", "csv"],
            "contents": "aggregate-only datasets selected by scope",
            "raw_private_data": False,
            "redistribution_requires_scope": "intelligence:redistribute",
        },
        "reliability": {
            "free": "best effort",
            "pro_operator": "status-page backed",
            "team_fund": "priority support",
            "enterprise": "contract SLO",
        },
        "privacy": {
            "exchange_credentials_collected": False,
            "custody_transferred": False,
            "raw_journals_required": False,
            "raw_model_prompts_included": False,
            "operator_secrets_included": False,
            "source_packets": "redacted ZERO Network packets only",
        },
    }
    assert_intelligence_safe(contract)
    return contract


def export_intelligence_snapshot(
    snapshot: dict[str, Any],
    *,
    consent: bool,
    export_path: str | None,
) -> dict[str, Any]:
    if not consent:
        return {
            "ok": False,
            "exported": False,
            "reason": "explicit consent required",
            "snapshot": snapshot,
        }
    if not export_path:
        return {
            "ok": False,
            "exported": False,
            "reason": "ZERO_INTELLIGENCE_EXPORT_PATH is not configured",
            "snapshot": snapshot,
        }
    assert_intelligence_safe(snapshot)
    path = Path(export_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(snapshot, sort_keys=True, separators=(",", ":")) + "\n")
    return {
        "ok": True,
        "exported": True,
        "reason": "exported to local ZERO Intelligence packet log",
        "path": str(path),
        "proof_hash": snapshot["source"]["proof_hash"],
        "snapshot": snapshot,
    }


def activity_level(decisions: int) -> str:
    if decisions <= 0:
        return "none"
    if decisions < 10:
        return "low"
    if decisions < 100:
        return "moderate"
    return "high"


def rejection_discipline(rejection_rate: float) -> str:
    if rejection_rate <= 0:
        return "none"
    if rejection_rate < 0.5:
        return "loose"
    if rejection_rate < 0.9:
        return "selective"
    return "strict"


def execution_pressure(acceptance_rate: float) -> str:
    if acceptance_rate <= 0:
        return "none"
    if acceptance_rate < 0.1:
        return "very_low"
    if acceptance_rate < 0.35:
        return "low"
    if acceptance_rate < 0.65:
        return "balanced"
    return "high"


def assert_intelligence_safe(payload: dict[str, Any]) -> None:
    assert_public_profile_safe(payload)
    body = json.dumps(payload, sort_keys=True).lower()
    forbidden = [
        "wallet material",
        "api private key",
        "exchange credential",
    ]
    for token in forbidden:
        if token in body:
            raise ValueError(f"intelligence packet contains forbidden token: {token}")


def _catalog_public_row(name: str, value: Any) -> str:
    if isinstance(value, dict):
        detail = value.get("endpoint", value.get("default", value.get("schema_version", value)))
    else:
        detail = value
    return (
        f"          <li><span>{_label(name)}</span>"
        f"<strong>{_escape(str(detail))}</strong></li>"
    )


def _catalog_plan_row(plan: dict[str, Any]) -> str:
    scopes = "\n".join(
        f"              <li><code>{_escape(str(scope))}</code></li>"
        for scope in _as_list(plan.get("scopes"))
    )
    return f"""        <div class="panel plan">
          <h2>{_label(str(plan.get("name", "unknown")))}</h2>
          <p>{_escape(str(plan.get("limits", "limits not specified")))}</p>
          <ul>
{scopes}
          </ul>
        </div>"""


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _label(value: str) -> str:
    return _escape(value.replace("_", " ").replace(":", " ").title())


def _escape(value: str) -> str:
    return html.escape(value, quote=True)
