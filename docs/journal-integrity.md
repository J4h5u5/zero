# Journal Integrity

ZERO decision journals are append-only JSONL files with a cryptographic
envelope around each decision.

The public runtime keeps reads backward-compatible: `DecisionJournal.read_all()`
and `/journal` return the decision payloads operators already expect. The file
on disk now stores `zero.decision_journal.entry.v1` entries so the operator can
verify sequence, previous hash, payload hash, signature status, and timestamp
anchor binding.

## Entry Shape

Each line contains:

| Field | Meaning |
|---|---|
| `schema_version` | `zero.decision_journal.entry.v1` |
| `sequence` | Monotonic 1-based sequence number. |
| `previous_hash` | Previous entry hash, or `null` for the first entry. |
| `payload` | The original accepted or rejected decision record. |
| `entry_hash` | SHA-256 over schema, sequence, previous hash, and payload. |
| `signature` | Operator-owned signing metadata. |
| `timestamp_anchor` | Local timestamp-anchor binding for the entry hash and local clock time. |

Unsigned local journals are still valid for paper examples. Live-capable
operator deployments should set a journal signing key and require signature
verification before risk can increase.

## Signing

The built-in signer uses HMAC-SHA256 from the Python standard library so a
fresh clone has no extra dependency.

```bash
export ZERO_JOURNAL_SIGNING_KEY="replace-with-operator-secret"
PYTHONPATH="$PWD/engine/src" python3 -m zero_engine.journal verify \
  .zero/decisions.jsonl \
  --require-signature \
  --signing-key-env ZERO_JOURNAL_SIGNING_KEY \
  --key-id local-operator
```

The signature is operator-owned. Do not commit signing keys. Do not publish raw
private journals.

## Verification

Verify an unsigned paper journal:

```bash
PYTHONPATH="$PWD/engine/src" scripts/journal_verify.py verify .zero/decisions.jsonl
```

Verify a signed operator journal:

```bash
PYTHONPATH="$PWD/engine/src" scripts/journal_verify.py verify \
  .zero/decisions.jsonl \
  --require-signature \
  --signing-key-env ZERO_JOURNAL_SIGNING_KEY
```

The verifier fails on:

- malformed JSON;
- sequence gaps or reordering;
- previous-hash mismatch;
- payload mutation;
- entry-hash mutation;
- missing signature when required;
- signature mismatch when the operator key is provided;
- timestamp-anchor mismatch when anchors are required.

## Timestamp Anchoring

Every entry includes a local timestamp-anchor binding to the entry hash and a
local `anchored_at` clock reading. This is enough to detect local tampering, but
it is not a trusted external timestamp.

The next trust cycle should add periodic external anchoring for journal heads
through a trusted timestamp service, Rekor/OpenTimestamps, or a public chain.
The public contract is already explicit: the anchor must bind the journal head
hash, anchor time, method, and external reference without exposing raw journal
payloads.

## Incident Rule

Any `zero.decision_journal.verification.v1` failure in a live-capable operator
deployment is a journal anomaly. Follow
[Incident Runbooks](incident-runbooks.md) and publish a redacted postmortem
when live safety, public privacy, or launch claims are affected.
