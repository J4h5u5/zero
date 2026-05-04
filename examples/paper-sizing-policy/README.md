# Paper Sizing Policy Example

This example shows how a strategy can size paper `OrderIntent`s before they
reach execution.

Run it from the repository root:

```bash
PYTHONPATH="$PWD/engine/src" python3 examples/paper-sizing-policy/run.py
```

The sizing policy is deterministic and paper-only:

- it caps risk-increasing order notional to the configured paper limit;
- it rejects risk-increasing setups below the minimum confidence threshold;
- it preserves `reduce_only=true` intents without capping or rejecting them;
- it never calls `PaperEngine.submit`, live APIs, network services, exchange
  credentials, wallets, or private runtime state.

The JSON output is stable so tests and contributors can inspect the policy
decisions without needing a live account.
