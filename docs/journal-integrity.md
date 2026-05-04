# Journal Integrity

ZERO decision journals are append-only JSONL files with a cryptographic
envelope around each decision.

The public runtime keeps reads backward-compatible: `DecisionJournal.read_all()`
and `/journal` return the decision payloads operators already expect. The file
on disk now stores `zero.decision_journal.entry.v1` entries so the operator can
verify sequence, previous hash, payload hash, signature status, and timestamp
anchor binding.

Appends are serialized with a per-journal exclusive append lock. The writer
takes the lock before reading the current head, assigning the next sequence, and
fsyncing the new line. This prevents competing agent, API, and operator
processes from writing two entries with the same predecessor hash.

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

Concurrent writer regressions are covered by
`test_decision_journal_serializes_concurrent_writer_processes`, which launches
multiple writer processes against the same journal and then verifies the final
hash chain.

## Timestamp Anchoring

Every entry includes a local timestamp-anchor binding to the entry hash and a
local `anchored_at` clock reading. This is enough to detect local tampering, but
it is not a trusted external timestamp.

External anchoring is handled by a separate public-safe packet:
`zero.decision_journal.external_anchor.v1`. The packet binds the verified
journal head hash, entry count, verification-report hash, timestamp method,
anchor time, and external receipt reference without exposing raw journal
payloads.

Prepare an anchor packet before sending the journal head to Rekor,
OpenTimestamps, RFC3161, or a public chain:

```bash
PYTHONPATH="$PWD/engine/src" scripts/journal_verify.py anchor \
  .zero/decisions.jsonl \
  --output .zero/journal-anchor.json \
  --method opentimestamps \
  --require-signature \
  --signing-key-env ZERO_JOURNAL_SIGNING_KEY
```

After the external service returns a receipt, recreate or update the packet
with a public-safe reference:

```bash
PYTHONPATH="$PWD/engine/src" scripts/journal_verify.py anchor \
  .zero/decisions.jsonl \
  --output .zero/journal-anchor.json \
  --method opentimestamps \
  --anchor-ref ots:sha256:<receipt-digest> \
  --require-signature \
  --signing-key-env ZERO_JOURNAL_SIGNING_KEY
```

Verify the packet against the journal and require an external receipt before
using it as live-capable evidence:

```bash
PYTHONPATH="$PWD/engine/src" scripts/journal_verify.py verify-anchor \
  .zero/decisions.jsonl \
  .zero/journal-anchor.json \
  --require-external \
  --require-signature \
  --signing-key-env ZERO_JOURNAL_SIGNING_KEY
```

The verifier fails on anchor hash mutation, journal-head mismatch, entry-count
mismatch, verification-hash mismatch, and missing external receipt when
`--require-external` is set.

## Periodic Anchor Cadence

Live-capable operators should run the cadence wrapper after each journal-head
change and at least once per configured interval. The wrapper reuses a fresh
same-head anchor, creates a new packet when the head changes or the prior packet
is stale, writes an immutable timestamped packet plus
`journal-anchor-latest.json`, and records a verifiable
`zero.decision_journal.anchor_cadence.v1` state file.

```bash
PYTHONPATH="$PWD/engine/src" scripts/journal_anchor_cadence.py run \
  .zero/decisions.jsonl \
  --anchor-dir .zero/anchors \
  --method opentimestamps \
  --anchor-ref ots:sha256:<receipt-digest> \
  --max-age-hours 24 \
  --require-external \
  --require-signature \
  --signing-key-env ZERO_JOURNAL_SIGNING_KEY
```

Verify the cadence state during live preflight or release evidence collection:

```bash
PYTHONPATH="$PWD/engine/src" scripts/journal_anchor_cadence.py verify-state \
  .zero/decisions.jsonl \
  --state .zero/anchors/journal-anchor-state.json \
  --require-external \
  --require-signature \
  --signing-key-env ZERO_JOURNAL_SIGNING_KEY
```

The operation fails closed when `--require-external` is set without a receipt,
when the state points at a missing or mutated packet, when the journal head no
longer matches the anchor, or when the cadence is overdue. Preserve external
receipt material outside the trading host.

## Incident Rule

Any `zero.decision_journal.verification.v1` failure in a live-capable operator
deployment is a journal anomaly. Follow
[Incident Runbooks](incident-runbooks.md) and publish a redacted postmortem
when live safety, public privacy, or launch claims are affected.
