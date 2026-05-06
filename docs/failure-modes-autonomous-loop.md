# Failure Modes Of The Autonomous Loop

This document is the public safety taxonomy for ZERO's autonomous loop. It is
written for maintainers, operators, reviewers, and coding agents.

The rule is simple: if a failure mode is not documented with detection, blast
radius, rollback, journal evidence, alerting, and test coverage, it is not
ready for unattended operation.

## Scope

The public repository exposes paper-first autonomous components:

- memory extraction from local outcomes;
- genesis proposal classification;
- paper-only research reports;
- lens/layer/modifier decision-stack review;
- paper-first evolve candidates;
- runtime OODA reports;
- read-only MCP inspection.

Protected live-code evolution remains human-reviewed. The public MCP server is
read-only and must not place orders, mutate runtime state, or read secrets.

## Required Fields

Every autonomous-loop failure mode must define:

| Field | Required answer |
|---|---|
| Detection | Which check sees the problem first? |
| Blast radius | What can be affected before containment? |
| Rollback | What command, revert, kill, or policy change restores safety? |
| Journal entry | Which journal/audit event proves what happened? |
| Alerting | Which operator-visible signal fires? |
| Test or evidence | Which deterministic test, property test, drill, or proof packet covers it? |

Unknown answers mean fail closed.

## Taxonomy

| ID | Failure mode | Detection | Blast radius | Rollback | Journal entry | Alerting | Test or evidence |
|---|---|---|---|---|---|---|---|
| FM-AUTO-001 | Agent hallucinates a strategy and burns through paper budget. | Strategy registry rejects unknown runners; paper budget breaker sees order count, notional, or drawdown drift. | Paper budget for the local session. Live capital should be zero because paper-first is enforced. | Pause evolve, disable the strategy, revert the candidate config, reset paper budget after review. | `zero.evolve.run.v1`, `zero.immune.v1`, rejected `zero.paper.decision.v1`, rollback receipt. | CLI/TUI safety banner, `/immune`, metrics counter, optional operator notification. | `engine/tests/test_evolve.py`, `engine/tests/test_safety.py`, `engine/tests/test_property_safety.py`. |
| FM-AUTO-002 | `evolve` produces a config that passes tests but fails at runtime. | Runtime health marks candidate as failed; production-parity OODA emits live-shadow mismatch or runtime exception. | Candidate branch and paper canary only. Protected paths must not auto-apply to live code. | `zero.evolve.rollback_receipt.v1`, restore original hash, mark proposal quarantined. | Apply receipt, rollback receipt, runtime cycle failure event. | `/runtime-parity`, `/evolve`, CI failure, operator terminal warning. | `engine/tests/test_evolve.py`, `engine/tests/test_runtime.py`, `engine/tests/test_property_safety.py`. |
| FM-AUTO-003 | Agent and human edit the journal concurrently. | Exclusive append lock serializes head reads and writes; verifier detects non-monotonic sequence, previous-hash break, checksum break, or replay mismatch. | Local audit trail for the affected runtime; execution must pause if journal integrity is unknown. | Stop writers, preserve both copies, replay from last good head, restore durable volume snapshot if needed. | `zero.decision_journal.verification.v1`, `zero.journal.integrity_failure.v1`, or incident audit export. | P1 journal anomaly alert, CLI refusal on live preflight, runbook escalation. | `engine/tests/test_journal.py::test_decision_journal_serializes_concurrent_writer_processes`, `engine/tests/test_bus.py`, `docs/runtime-bus.md`. |
| FM-AUTO-004 | Hyperliquid returns malformed response and the agent retries N times. | Adapter schema validation fails; retry budget reaches zero; rate-limit breaker opens. | Read-only market/account freshness or one blocked live submission. Order submissions must not retry blindly. | Mark venue degraded, fail risk-increasing actions, keep reduce-only controls available. | `exchange_error`, reconciliation packet, immune breaker event. | `/hl/reconcile`, `/immune`, `/live-cockpit`, metrics exchange-error counter. | `engine/tests/test_hyperliquid.py`, `engine/tests/test_live.py`, `engine/tests/test_reconciliation.py`, `engine/tests/test_property_safety.py`. |
| FM-AUTO-005 | Stale memory promotes an outdated pattern. | Memory stats report stale source window; genesis confidence drops; proposal age exceeds policy. | Proposal quality and paper canary time, not live execution. | Retire stale memory, regenerate proposal from fresh outcomes, require a new paper canary. | `zero.memory.entry.v1`, `zero.genesis.proposal.v1`, research report. | `/memory`, `/genesis`, docs gap or safety-review issue. | `engine/tests/test_memory.py`, `engine/tests/test_genesis.py`, `engine/tests/test_property_safety.py`. |
| FM-AUTO-006 | Research command ingests prompt-injected or unsupported external claims. | `zero.research.source_classification.v1` marks untrusted, prompt-injected, unsupported-performance, secret-material, or risk-increasing claims as rejected; research report carries source-quality flags without raw source text. | Paper-only research report and proposal queue. | Discard report, quarantine source, regenerate with trusted sources only. | `zero.research.report.v1` with rejected source metadata. | `/research`, safety-review issue when live policy would be affected. | `engine/tests/test_research.py::test_research_source_classifier_rejects_prompt_injection_without_echoing_raw_text`, `engine/tests/test_research.py::test_research_public_safety_rejects_unsafe_report_keys`. |
| FM-AUTO-007 | Model gateway produces unsafe, expensive, or unavailable output. | Gateway budget, timeout, health, and audit checks fail closed. | Evaluation quality degradation; order path must not depend on unverified model output alone. | Fall back to local/mock provider, lower confidence, or reject decision. | Model gateway audit packet and decision rejection reason. | `/model-gateway/health`, metrics, operator warning. | `engine/tests/test_model_gateway.py`, `engine/tests/test_property_safety.py`. |
| FM-AUTO-008 | Paper/live shadow diverges during production-parity OODA. | `zero.runtime.production_parity.v1` reports mismatch or live-shadow fail-closed evidence. | Live promotion blocked; paper session continues. | Disable promotion, capture audit export, create regression fixture. | Runtime parity report, decision-stack packet, live-shadow refusal. | `/runtime-parity`, CLI red status, safety-review issue. | `engine/tests/test_runtime.py`, `engine/tests/test_live.py`. |
| FM-AUTO-009 | MCP client asks ZERO to place an order or mutate state. | MCP safety catalog has no risk-increasing tools; unknown methods, unknown tools, and unavailable resources return `zero.mcp.refusal.v1` without echoing hostile arguments or prompt text. | None if server remains read-only. | Keep server read-only, revoke unsafe registry submission, patch transcript. | MCP transcript refusal and safety catalog resource. | MCP smoke failure, CI failure. | `engine/tests/test_mcp.py::test_mcp_refuses_mutating_methods_without_echoing_raw_arguments`, `engine/tests/test_mcp.py::test_mcp_refuses_unknown_resource_without_echoing_prompt_injection`, `scripts/mcp_transcript.py --check`. |
| FM-AUTO-010 | Public Network or Intelligence packet leaks private identifiers. | Privacy regression fixtures detect wallet-like, raw order ID, trace token, or private journal fields. | Public artifact exposure until publication is stopped. | Stop publishing, rotate unsafe packet, patch serializer, mark proof stale. | Public packet hash, privacy regression incident export. | P1 privacy regression alert, CI failure. | `engine/tests/test_proof_privacy.py`, `scripts/proof_privacy_regression.py`. |
| FM-AUTO-011 | Kill switch, pause, flatten, or reduce-only path is unavailable. | Live certification drill fails; cockpit marks emergency controls not ready. | Live mode must refuse risk-increasing actions. Existing exchange positions may need manual exchange action. | Manual exchange close if needed; keep ZERO live disabled until certification passes. | `zero.live_certification.v1`, live cockpit packet, incident postmortem. | `/live-certification`, `/live-cockpit`, P0/P1 runbook. | `engine/tests/test_live_canary_policy.py`, `scripts/live_cockpit_drill_verify.py`. |
| FM-AUTO-012 | Journal chain, signature, or timestamp anchor fails verification. | `zero.decision_journal.verification.v1` detects missing head, broken previous hash, invalid signature, missing required signature, or stale anchor; `zero.decision_journal.external_anchor.verification.v1` detects anchor packet drift or missing external receipt; `zero.decision_journal.anchor_cadence.v1` detects stale cadence state. | Audit trust for the affected interval. Live mode must refuse if the decision journal or required external anchor is unverifiable. | Stop writers, preserve artifact, restore last verified head, publish redacted postmortem if live safety was affected. | `zero.decision_journal.verification.v1`, `zero.decision_journal.external_anchor.v1`, `zero.decision_journal.anchor_cadence.v1`, verifier report, incident postmortem. | CLI live-preflight refusal, incident alert. | `engine/tests/test_journal.py`, `engine/tests/test_journal_anchor_cadence.py`, `scripts/journal_verify.py`, `scripts/journal_anchor_cadence.py`. |

## Coverage Bar For 100/100

ZERO reaches the autonomous trust bar only when:

- every row above has at least one deterministic regression test;
- safety gates have property-based tests for bounded random inputs;
- decision journals are hash-chained, signed, and locally verifiable;
- journal-head external anchor packets have a periodic operation that attaches
  trusted timestamp receipts or public-chain references and verifies cadence
  state;
- failures that touch live safety, journal integrity, or public privacy produce
  redacted postmortems in `docs/incident-postmortems/`;
- the MCP server has a committed registry packet and live Official MCP Registry
  listing backed by the public `zero-engine` PyPI package.

## Operating Rule

Autonomy is allowed to suggest, classify, rehearse, and paper-canary changes.
Autonomy is not allowed to silently expand live risk, bypass journals, bypass
reconciliation, bypass kill switches, publish private records, or mutate
protected live-code paths without human review.
