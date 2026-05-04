# QA Onboarding Checklist

This checklist is for new technical engineers and QA engineers validating ZERO
as a paper-first, safety-critical public runtime.

Use this as a repeatable baseline for local verification and pull-request
review.

## 1) Environment And Bootstrap

Run from repository root:

```bash
just bootstrap
```

Quickly verify Python and pytest resolve to the same interpreter family:

```bash
python3 --version
python3 -m pytest --version
```

Expected outcome:

- `python3 -m pytest` works without import errors.
- Avoid running bare `pytest` if it points to a different Python install.

## 2) Core Baseline Checks

Run the smallest high-signal baseline before reviewing behavior:

```bash
cd engine && PYTHONPATH="$PWD/src" python3 -m pytest -q -p no:cacheprovider
cd ../cli && cargo test --workspace
cd .. && just docs-check
```

Expected outcome:

- Engine tests pass.
- CLI workspace tests pass.
- `docs-check` passes with no missing machine-readable assets.

## 3) Paper API Smoke

Run smoke on a free local port:

```bash
ZERO_PAPER_API_PORT=8877 just paper-api-smoke
```

Expected outcome:

- Command exits successfully.
- Refusal-mode/live-boundary assertions pass.
- No credential/token leaks in generated evidence checks.

If default port `8765` is already occupied, do not reuse it silently; use an
explicit override as shown above.

## 4) Safety-Critical Regression Slice

Run a focused subset that protects core invariants:

```bash
python3 -m pytest \
  engine/tests/test_live.py \
  engine/tests/test_reconciliation.py \
  engine/tests/test_mcp.py \
  engine/tests/test_proof_privacy.py \
  engine/tests/test_journal.py \
  engine/tests/test_journal_anchor_cadence.py \
  -q -p no:cacheprovider
```

Expected outcome:

- Live-capable paths fail closed by default.
- MCP mutation attempts are refused.
- Privacy regression fixtures are refused.
- Journal integrity and anchor cadence validation pass.

## 5) MCP And Privacy Verification

```bash
PYTHONPATH="$PWD/engine/src" python3 -m zero_engine.mcp --smoke
PYTHONPATH="$PWD/engine/src" scripts/mcp_transcript.py --check
PYTHONPATH="$PWD/engine/src" scripts/proof_privacy_regression.py
```

Expected outcome:

- MCP smoke prints `zero mcp smoke passed: ...`.
- Transcript check passes.
- Privacy regression reports refused unsafe fixtures.

## 6) PR Review Workflow

For each public PR:

1. Read PR summary and changed files:
   `gh pr view <n> --json files,body,title,url`
2. Inspect full patch:
   `gh pr diff <n>`
3. Run only claimed/impacted tests first, then expand scope if risk is higher.
4. Map changes to ZERO invariants:
   - paper-first default
   - fail-closed live boundary
   - no secret/private leakage
   - journal/audit integrity
   - OpenAPI/fixture contract stability
5. Publish findings ordered by severity:
   - `P1`: blocking safety/contract issue
   - `P2`: important robustness/correctness issue
   - `P3`: non-blocking improvement

## 7) Invariant Checklist (Fast Audit)

- Paper mode remains default and runnable without credentials.
- Live-risk increase requires explicit readiness and refusal paths.
- Risk-reducing controls remain available when risk increase is blocked.
- Public packets stay aggregate-only and redacted.
- MCP remains read-only (no order placement, no state mutation).
- New autonomous behavior updates failure-mode documentation when required.

## 8) Escalation Rules

Escalate immediately when you find:

- Secret or private-identifier leakage in public artifacts.
- Any path that makes live trading easier than paper mode.
- Broken refusal behavior on protected/live-capable actions.
- Journal integrity verification gaps or bypasses.
- API/OpenAPI contract drift without fixture/test updates.

When escalating, include:

- exact command run
- exact failing output
- file and line reference
- blast radius estimate
- minimal rollback or mitigation
