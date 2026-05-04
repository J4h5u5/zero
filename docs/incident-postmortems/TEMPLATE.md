# YYYY-MM-DD Incident Title

Status: draft | published | delayed
Severity: P0 | P1 | P2
Incident window:
Detected at:
Resolved at:
Repository version:
Operator environment:

## Summary

One paragraph describing what happened and what was affected.

## Impact

- Affected users or operators:
- Affected systems:
- Live capital affected:
- Public artifacts affected:
- Data privacy affected:

## Timeline

| Time | Event |
|---|---|
| YYYY-MM-DDTHH:MM:SSZ | Detection event. |
| YYYY-MM-DDTHH:MM:SSZ | Containment action. |
| YYYY-MM-DDTHH:MM:SSZ | Verification complete. |

## Failure Mode

Link to one or more IDs from
[Failure Modes Of The Autonomous Loop](../failure-modes-autonomous-loop.md).

## Detection

What check, alert, verifier, operator action, or external report detected the
incident?

## Blast Radius

What could the incident affect before containment? Be explicit about what it
could not affect.

## Rollback And Containment

What kill, pause, flatten, revert, rollback receipt, deployment rollback, or
publication stop was used?

## Journal And Evidence

- Journal entry or audit packet:
- Proof hash:
- Verifier command:
- Redacted artifact path:

## Alerting

Which operator-visible alert fired? If no alert fired, explain the gap.

## Root Cause

What failed technically and operationally?

## What Worked

What prevented a worse outcome?

## What Failed

What should have caught this earlier?

## Remediation

| Item | Owner | Status |
|---|---|---|
| Add regression test. | TBD | open |
| Update runbook. | TBD | open |
| Verify release or deployment. | TBD | open |

## Test Coverage

List the deterministic tests, property tests, drills, or verifiers added after
the incident.

## Publication Notes

Explain redactions and any delayed-publication reason.
