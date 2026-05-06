#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass

from zero_engine import OrderIntent, RiskLimits, Side


@dataclass(frozen=True)
class SizingDecision:
    name: str
    input: OrderIntent
    output: OrderIntent | None
    action: str
    reason: str

    def to_dict(self) -> dict:
        payload = {
            "name": self.name,
            "action": self.action,
            "reason": self.reason,
            "input": order_to_dict(self.input),
            "output": order_to_dict(self.output) if self.output is not None else None,
        }
        if self.output is not None:
            payload["notional_delta_usd"] = round(
                self.input.notional_usd - self.output.notional_usd,
                2,
            )
        return payload


def size_paper_order(name: str, intent: OrderIntent, limits: RiskLimits) -> SizingDecision:
    if intent.reduce_only:
        return SizingDecision(
            name=name,
            input=intent,
            output=intent,
            action="preserve",
            reason="reduce-only orders keep original size for risk reduction",
        )

    if intent.confidence < limits.min_confidence:
        return SizingDecision(
            name=name,
            input=intent,
            output=None,
            action="reject",
            reason="confidence below minimum",
        )

    if intent.notional_usd > limits.max_notional_usd:
        capped_quantity = round(limits.max_notional_usd / intent.price, 8)
        return SizingDecision(
            name=name,
            input=intent,
            output=OrderIntent(
                symbol=intent.symbol,
                side=intent.side,
                quantity=capped_quantity,
                price=intent.price,
                confidence=intent.confidence,
                reduce_only=intent.reduce_only,
            ),
            action="cap",
            reason="order notional capped to paper limit",
        )

    return SizingDecision(
        name=name,
        input=intent,
        output=intent,
        action="accept",
        reason="within paper sizing limits",
    )


def order_to_dict(intent: OrderIntent | None) -> dict | None:
    if intent is None:
        return None
    return {
        "symbol": intent.symbol,
        "side": intent.side.value,
        "quantity": intent.quantity,
        "price": intent.price,
        "notional_usd": round(intent.notional_usd, 2),
        "confidence": intent.confidence,
        "reduce_only": intent.reduce_only,
    }


def main() -> int:
    limits = RiskLimits(max_notional_usd=500, min_confidence=0.7)
    candidates = [
        (
            "capped-btc",
            OrderIntent("BTC", Side.BUY, quantity=0.03, price=40_000, confidence=0.82),
        ),
        (
            "low-confidence-eth",
            OrderIntent("ETH", Side.BUY, quantity=0.25, price=2_000, confidence=0.42),
        ),
        (
            "reduce-only-btc",
            OrderIntent(
                "BTC",
                Side.SELL,
                quantity=0.03,
                price=40_000,
                confidence=0.2,
                reduce_only=True,
            ),
        ),
    ]
    decisions = [size_paper_order(name, intent, limits) for name, intent in candidates]

    print(
        json.dumps(
            {
                "mode": "paper",
                "policy": "deterministic-paper-sizing",
                "limits": {
                    "max_notional_usd": limits.max_notional_usd,
                    "min_confidence": limits.min_confidence,
                },
                "submits_orders": False,
                "decisions": [decision.to_dict() for decision in decisions],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
