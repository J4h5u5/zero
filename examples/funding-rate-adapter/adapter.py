from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FundingRateAdapterMetadata:
    name: str
    version: str
    description: str
    source: str
    deterministic: bool = True
    requires_secrets: bool = False


@dataclass(frozen=True)
class FundingRate:
    symbol: str
    ts: str
    rate: float
    interval_hours: int
    venue: str

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol is required")
        if not self.ts:
            raise ValueError("ts is required")
        if self.interval_hours <= 0:
            raise ValueError("interval_hours must be positive")
        if not self.venue:
            raise ValueError("venue is required")


class FixtureFundingRateAdapter:
    metadata = FundingRateAdapterMetadata(
        name="fixture-funding-rates",
        version="0.1.0",
        description="Paper-only funding-rate adapter backed by a checked-in JSONL fixture.",
        source="local-jsonl-fixture",
    )

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._rates = _load_rates(self.path)

    def funding_rates(self, symbol: str, limit: int | None = None) -> tuple[FundingRate, ...]:
        normalized = symbol.upper()
        matches = tuple(row for row in self._rates if row.symbol == normalized)
        if limit is not None:
            if limit <= 0:
                raise ValueError("limit must be positive")
            return matches[-limit:]
        return matches

    def latest(self, symbol: str) -> FundingRate:
        matches = self.funding_rates(symbol)
        if not matches:
            raise KeyError(f"no funding rates for {symbol.upper()}")
        return matches[-1]


def example_adapter(path: str | Path | None = None) -> FixtureFundingRateAdapter:
    fixture_path = (
        Path(path) if path is not None else Path(__file__).with_name("funding_rates.jsonl")
    )
    return FixtureFundingRateAdapter(fixture_path)


def _load_rates(path: Path) -> tuple[FundingRate, ...]:
    rows = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(_parse_rate(json.loads(line)))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid funding rate at {path}:{line_number}: {exc}") from exc
    if not rows:
        raise ValueError(f"no funding rates found in {path}")
    return tuple(rows)


def _parse_rate(raw: dict[str, Any]) -> FundingRate:
    return FundingRate(
        symbol=str(raw["symbol"]).upper(),
        ts=str(raw["ts"]),
        rate=float(raw["rate"]),
        interval_hours=int(raw["interval_hours"]),
        venue=str(raw["venue"]),
    )
