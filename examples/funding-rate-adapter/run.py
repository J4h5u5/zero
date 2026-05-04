from __future__ import annotations

import json

from adapter import example_adapter


def main() -> None:
    adapter = example_adapter()
    latest = adapter.latest("BTC-PERP")

    print(
        json.dumps(
            {
                "mode": "paper",
                "adapter": {
                    "name": adapter.metadata.name,
                    "version": adapter.metadata.version,
                    "source": adapter.metadata.source,
                    "requires_secrets": adapter.metadata.requires_secrets,
                },
                "symbol": latest.symbol,
                "latest_rate": latest.rate,
                "as_of": latest.ts,
                "interval_hours": latest.interval_hours,
                "rows": [
                    {
                        "symbol": row.symbol,
                        "ts": row.ts,
                        "rate": row.rate,
                        "interval_hours": row.interval_hours,
                        "venue": row.venue,
                    }
                    for row in adapter.funding_rates("BTC-PERP")
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
