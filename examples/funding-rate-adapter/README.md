# Funding Rate Adapter Example

This example shows how to model non-price market data with a deterministic,
local fixture. It is paper-only and does not use exchange credentials, network
access, wallet material, or live mode.

Run it from the repository root:

```bash
PYTHONPATH="$PWD/examples/funding-rate-adapter" \
  python3 examples/funding-rate-adapter/run.py
```

The adapter reads `funding_rates.jsonl` from this directory and exposes
funding-rate rows in chronological order.

Expected output shape:

```json
{
  "mode": "paper",
  "adapter": {
    "name": "fixture-funding-rates",
    "requires_secrets": false,
    "source": "local-jsonl-fixture"
  },
  "symbol": "BTC-PERP",
  "latest_rate": 0.00014
}
```

Contributor rules:

- Keep examples deterministic and paper-first.
- Do not require secrets or live accounts for public examples.
- Return funding-rate rows in chronological order.
- Raise clear errors for missing symbols or invalid limits.
