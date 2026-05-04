# Incident Postmortems

ZERO publishes redacted postmortems for incidents that affect autonomous-loop
trust, live safety, journal integrity, public privacy, or release integrity.

The goal is not performative transparency. The goal is to make autonomous
operation auditable by showing what failed, how it was detected, how far it
could spread, how it was rolled back, what the journal recorded, what alert
fired, and which test now prevents recurrence.

## Publication Policy

Publish a redacted postmortem when any of the following occurs:

- a P0/P1 incident from [Incident Runbooks](../incident-runbooks.md);
- unexpected live order, failed canary, or emergency control failure;
- safety-gate refusal that reveals a design gap;
- journal anomaly, checksum break, signature failure, or timestamp-anchor
  failure;
- autonomous loop proposes, applies, or rehearses an unsafe change;
- public Network or Intelligence packet leaks private identifiers;
- MCP server exposes an unsafe tool, resource, or registry manifest;
- release artifact, SBOM, provenance, or attestation is wrong.

## Timing

- Preserve evidence immediately.
- Draft internally within 72 hours.
- Publish a redacted version within 7 days when public users, public artifacts,
  or live-safety claims are affected.
- If publication would expose secrets or an active exploit, publish a delayed
  notice and complete the postmortem after containment.

## Redaction Rules

Never publish:

- private keys, seed phrases, API tokens, cookies, or auth headers;
- wallet addresses unless the operator explicitly made them public;
- raw exchange order IDs, raw private journals, trace tokens, or idempotency
  tokens;
- strategy labels or private notes that can identify an operator;
- unredacted screenshots containing account state.

Publish instead:

- timestamps;
- release tags and commit SHAs;
- redacted trace IDs;
- proof hashes;
- verifier outputs;
- aggregate counts;
- remediation commits;
- new or updated test names.

## Index

No public incident postmortems have been published yet.

New postmortems should use [TEMPLATE.md](TEMPLATE.md) and be named:

```text
YYYY-MM-DD-short-slug.md
```
