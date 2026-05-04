# Research Command Chain

ZERO Research is the public, fixture-backed version of the private research
loop. It gives operators and coding agents the missing analysis layer between
local memory, genesis proposals, and evolve gates.

The report artifact uses `zero.research.report.v1`. The API snapshot uses
`zero.research.snapshot.v1`. Source trust decisions use
`zero.research.source_classification.v1`; aggregate source-quality records use
`zero.research.source_quality.v1`.

## Commands

The public chain runs seven deterministic commands:

- `hunt`: market scan from public paper candle fixtures;
- `edge`: accepted/rejected decision analysis from local paper journals;
- `convergence`: feedback-loop drift and lockstep detection;
- `thesis`: seven-day operating hypothesis, anti-thesis, and scorecard;
- `score`: prior-judgment scoring against public paper outcomes;
- `meta`: command usefulness audit;
- `sharpen`: system-improvement backlog.

## Safety Boundary

Research is paper-only and read-only.

- It does not place orders.
- It does not mutate the checkout.
- It does not open branches, commits, pull requests, or deployments.
- It does not claim live PnL or live edge.
- It removes private keys, wallet material, venue order ids, raw venue payloads,
  prices, sizes, quantities, and notionals from public artifacts.
- It classifies source trust before a source can influence paper research.
  Prompt-injected, untrusted, unsupported performance, or risk-increasing
  claims are rejected into quarantine metadata without echoing raw source text.

Live research conclusions require signed operator evidence before they can be
used as public proof.

## Source Quality

Every research report includes `source_quality`:

- `accepted`: fixture, signed-operator, or repository-document sources that can
  be used for paper research;
- `rejected`: untrusted or adversarial sources that can only be used for
  quarantine records and safety review;
- `raw_content_included=false`: public reports never carry raw source text.

The adversarial fixture coverage lives in
`engine/tests/test_research.py::test_research_source_classifier_rejects_prompt_injection_without_echoing_raw_text`.

## Local Example

```bash
PYTHONPATH="$PWD/engine/src" python3 -m zero_engine.research run \
  --repo-root "$PWD" \
  --output artifacts/research/research.json \
  --now 2026-05-01T00:00:00Z

PYTHONPATH="$PWD/engine/src" python3 -m zero_engine.research status \
  --report artifacts/research/research.json \
  --now 2026-05-01T00:00:00Z
```

Installed entrypoint:

```bash
zero-research run --repo-root . --output artifacts/research/research.json
```

## API And MCP

The local paper API exposes:

```bash
curl -fsS http://127.0.0.1:8765/research
```

The MCP server exposes `zero_get_research_report` and the
`zero://research/report` resource. Both are read-only and fixture-backed.

## Relationship To Evolve

Research is not `/evolve`. Research explains what the system should inspect
next. Genesis turns evidence into reviewable proposals. Evolve runs guarded
paper-only builder, red-team, canary, and calibration gates. Promotion still
requires human review.
