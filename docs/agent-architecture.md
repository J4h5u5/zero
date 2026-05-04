# Agent Architecture

ZERO is an autonomous operating system for self-custodial onchain operations.
This document defines what the agentic loop can do, what it cannot do, and
where humans remain mandatory.

## Authority Model

| Surface | Agent authority | Human authority |
|---|---|---|
| Memory | Extract public-safe lessons from local outcomes and redacted fixtures. | Delete, correct, or quarantine misleading memories. |
| Genesis | Classify proposals and produce plan-only candidates. | Approve which proposal class deserves paper canary work. |
| Research | Produce paper-only reports with source quality labels. | Decide whether research is trusted enough to influence policy. |
| Decision stack | Explain lenses, layers, modifiers, rejections, and consensus. | Change live-risk thresholds and protected policy. |
| Evolve | Generate sandbox candidates, paper canaries, promotion plans, rollback plans, and exact apply receipts. | Apply protected changes, approve live-code changes, and own rollback. |
| Runtime OODA | Observe, orient, decide, act in paper mode, and learn from accepted/rejected decisions. | Enable self-custodial live mode only after local custody, preflight, reconciliation, journal, and kill-switch checks pass. |
| MCP | Expose read-only inspection tools and resources. | No order placement through public MCP. |

## Loop Shape

```text
runtime OODA
  observe -> orient -> decide -> act -> learn

self-evolution
  memory -> research -> genesis -> evolve candidate -> paper canary
         -> calibration -> promotion plan -> human apply -> rollback receipt
```

The runtime loop is the source of operational truth. The self-evolution loop is
the source of candidate change. They are connected through journals and
evidence, not through silent code mutation.

## Bounds

Agents may:

- read public docs, fixtures, OpenAPI contracts, and redacted proof packets;
- run paper examples, tests, and read-only MCP tools;
- classify proposals and generate paper-only candidates;
- write docs, examples, tests, and non-protected code in scoped changes;
- propose rollback plans and incident follow-ups.

Agents must not:

- place live orders through MCP;
- remove paper-first defaults;
- read or emit secrets, wallet material, raw exchange order IDs, private
  journals, private notes, or account-bearing payloads;
- make live trading easier than paper trading;
- bypass live preflight, reconciliation, durable journal checks, dead-man
  controls, kill switches, or operator friction;
- auto-apply protected live-code changes;
- publish PnL, latency, paper/live correlation, or live-capability claims
  without reproducible evidence in the repo.

## Protected Paths

Protected live-code evolution requires human review. Changes that touch these
areas need safety review, tests, and explicit operator-visible refusal paths:

- live execution adapters;
- custody and key handling;
- risk-increasing commands;
- reconciliation gates;
- immune breakers;
- journal integrity;
- public Network and Intelligence serializers;
- MCP safety catalog;
- release and distribution workflows.

## State Ownership

| State | Owner | Durability requirement |
|---|---|---|
| Decision journal | Operator runtime | Append-only, hash-chained, locally signed when configured, verifier-backed, externally anchorable through public-safe receipt packets, and covered by a periodic cadence operation. |
| Runtime bus | Runtime | Checksum-chained and replayable from disk. |
| Memory | Operator runtime | Local, redacted, and source-attributed. |
| Genesis journal | Operator runtime | Append-only, reviewable, and plan-only. |
| Evolve receipts | Operator runtime | Original hash, candidate hash, apply receipt, rollback receipt. |
| Public proof packets | Publisher | Aggregate-only, privacy-checked, and hash-addressed. |

## Failure-Mode Contract

Every new autonomous capability must update
[Failure Modes Of The Autonomous Loop](failure-modes-autonomous-loop.md) when it
introduces a new way to fail. The failure-mode entry must define detection,
blast radius, rollback, journal evidence, alerting, and test coverage.

## Live Operation Boundary

The public repo supports the contracts and operator surfaces needed for
self-custodial live operation. It does not host custody, does not ship private
operator records, and does not make live mode the default.

Before live risk can increase, the local operator deployment must prove:

- custody is configured locally;
- live preflight passes;
- reconciliation is fresh and safe;
- journal durability is verified;
- immune breakers allow the action;
- dead-man and kill-switch controls are ready;
- risk-increasing action has deliberate operator approval.

If any proof is missing, ZERO must refuse risk increase and keep
risk-reducing controls available.
