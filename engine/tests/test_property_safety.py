from __future__ import annotations

import json
import math
import tempfile
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from zero_engine.hyperliquid import HyperliquidInfoClient, parse_positive_float, validate_dry_run_order
from zero_engine.memory import DEFAULT_TTL_DAYS, MemoryEntry, MemoryStore, entry_ttl
from zero_engine.model_gateway import ModelGateway, ModelGatewayConfig
from zero_engine.models import OrderIntent, Position, RiskLimits, Side
from zero_engine.safety import evaluate_order, projected_position

FIXED = datetime(2026, 5, 1, tzinfo=UTC)
FINITE_POSITIVE = st.floats(min_value=0.000001, max_value=1_000_000, allow_nan=False, allow_infinity=False)


@settings(max_examples=120)
@given(
    max_notional=st.floats(min_value=1, max_value=25_000, allow_nan=False, allow_infinity=False),
    max_position=st.floats(min_value=1, max_value=50_000, allow_nan=False, allow_infinity=False),
    min_confidence=st.floats(min_value=0.01, max_value=1.0, allow_nan=False, allow_infinity=False),
    quantity=st.floats(min_value=0.0001, max_value=5, allow_nan=False, allow_infinity=False),
    price=st.floats(min_value=1, max_value=100_000, allow_nan=False, allow_infinity=False),
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    reduce_only=st.booleans(),
    side=st.sampled_from([Side.BUY, Side.SELL]),
    current_quantity=st.floats(min_value=-3, max_value=3, allow_nan=False, allow_infinity=False),
    current_avg_price=st.floats(min_value=1, max_value=100_000, allow_nan=False, allow_infinity=False),
)
def test_risk_gate_property_matches_budget_and_friction_invariants(
    max_notional: float,
    max_position: float,
    min_confidence: float,
    quantity: float,
    price: float,
    confidence: float,
    reduce_only: bool,
    side: Side,
    current_quantity: float,
    current_avg_price: float,
) -> None:
    limits = RiskLimits(
        max_notional_usd=max_notional,
        max_position_notional_usd=max_position,
        min_confidence=min_confidence,
    )
    intent = OrderIntent(
        symbol="BTC",
        side=side,
        quantity=quantity,
        price=price,
        confidence=confidence,
        reduce_only=reduce_only,
    )
    current = Position("BTC", quantity=current_quantity, avg_price=current_avg_price)

    decision = evaluate_order(intent, limits, current)

    if reduce_only:
        assert decision.allowed is True
        assert decision.reason == "reduce-only orders bypass risk-increasing friction"
        return
    if confidence < min_confidence:
        assert decision.allowed is False
        assert decision.reason == "confidence below minimum"
        return
    if intent.notional_usd > max_notional:
        assert decision.allowed is False
        assert decision.reason == "order notional exceeds limit"
        return
    if projected_position(intent, current).notional_usd > max_position:
        assert decision.allowed is False
        assert decision.reason == "projected position exceeds limit"
        return
    assert decision.allowed is True
    assert decision.reason == "allowed"


@settings(max_examples=80)
@given(
    current_quantity=st.floats(min_value=-10, max_value=10, allow_nan=False, allow_infinity=False),
    current_avg_price=FINITE_POSITIVE,
    quantity=FINITE_POSITIVE,
    price=FINITE_POSITIVE,
    side=st.sampled_from([Side.BUY, Side.SELL]),
)
def test_projected_position_property_never_returns_negative_notional_or_wrong_symbol(
    current_quantity: float,
    current_avg_price: float,
    quantity: float,
    price: float,
    side: Side,
) -> None:
    intent = OrderIntent("BTC", side, quantity=quantity, price=price, confidence=1.0)
    projected = projected_position(
        intent,
        Position("BTC", quantity=current_quantity, avg_price=current_avg_price),
    )

    assert projected.symbol == "BTC"
    assert projected.notional_usd >= 0
    assert math.isfinite(projected.notional_usd)
    if projected.quantity == 0:
        assert projected.avg_price == 0


@settings(max_examples=120)
@given(value=st.one_of(st.none(), st.booleans(), st.text(), st.floats(allow_nan=True, allow_infinity=True)))
def test_hyperliquid_positive_float_parser_property_fails_closed(value: Any) -> None:
    if isinstance(value, bool):
        with pytest.raises(ValueError, match="must be numeric"):
            parse_positive_float(value, "mid price")
        return
    try:
        parsed_candidate = float(value)
    except (TypeError, ValueError):
        with pytest.raises(ValueError, match="must be numeric"):
            parse_positive_float(value, "mid price")
        return
    if not math.isfinite(parsed_candidate):
        with pytest.raises(ValueError, match="must be finite"):
            parse_positive_float(value, "mid price")
        return
    if parsed_candidate <= 0:
        with pytest.raises(ValueError, match="must be positive"):
            parse_positive_float(value, "mid price")
        return
    assert parse_positive_float(value, "mid price") == parsed_candidate


@settings(max_examples=80)
@given(
    response=st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=True, allow_infinity=True),
        st.text(),
        st.lists(st.integers()),
        st.dictionaries(
            keys=st.text(min_size=1, max_size=8),
            values=st.one_of(
                st.none(),
                st.booleans(),
                st.text(max_size=12),
                st.floats(allow_nan=True, allow_infinity=True),
                st.lists(st.integers(), max_size=2),
            ),
            max_size=4,
        ),
    )
)
def test_hyperliquid_all_mids_property_never_accepts_malformed_prices(response: Any) -> None:
    client = HyperliquidInfoClient(transport=lambda *_args: response)

    if not isinstance(response, dict):
        with pytest.raises(ValueError, match="allMids response must be an object"):
            client.all_mids()
        return

    expected: dict[str, float] = {}
    for symbol, raw_price in response.items():
        try:
            expected[str(symbol).upper()] = parse_positive_float(raw_price, f"mid price for {symbol}")
        except ValueError:
            with pytest.raises(ValueError):
                client.all_mids()
            return
    assert client.all_mids() == expected


@settings(max_examples=80)
@given(size=st.one_of(st.none(), st.booleans(), st.text(), st.floats(allow_nan=True, allow_infinity=True)))
def test_hyperliquid_dry_run_order_property_rejects_invalid_sizes(size: Any) -> None:
    payload = {"coin": "BTC", "side": "buy", "size": size}

    if isinstance(size, bool):
        with pytest.raises(ValueError, match="size must be numeric"):
            validate_dry_run_order(payload)
        return
    try:
        parsed = float(size)
    except (TypeError, ValueError):
        with pytest.raises(ValueError, match="size must be numeric"):
            validate_dry_run_order(payload)
        return
    if not math.isfinite(parsed):
        with pytest.raises(ValueError, match="size must be finite"):
            validate_dry_run_order(payload)
        return
    if parsed <= 0:
        with pytest.raises(ValueError, match="size must be positive"):
            validate_dry_run_order(payload)
        return
    assert validate_dry_run_order(payload)["size"] == parsed


@settings(max_examples=80)
@given(kind=st.sampled_from(sorted(DEFAULT_TTL_DAYS)))
def test_memory_entry_ttl_property_matches_staleness_policy(kind: str) -> None:
    expires_at = entry_ttl(kind, FIXED)
    entry = MemoryEntry(
        kind=kind,
        scope="local-private",
        subject="BTC",
        summary=f"{kind} memory stays public safe.",
        evidence_hash=f"sha256:{kind}",
        source="test",
        created_at=FIXED,
        expires_at=expires_at,
    )

    assert expires_at == FIXED + timedelta(days=DEFAULT_TTL_DAYS[kind])
    assert entry.is_expired(expires_at - timedelta(microseconds=1)) is False
    assert entry.is_expired(expires_at) is True


@settings(max_examples=40)
@given(kinds=st.lists(st.sampled_from(sorted(DEFAULT_TTL_DAYS)), min_size=1, max_size=8))
def test_memory_store_stats_property_separates_active_and_expired_entries(
    kinds: list[str],
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        store = MemoryStore(f"{directory}/memory.jsonl")
        entries = [
            MemoryEntry(
                kind=kind,
                scope="local-private",
                subject=f"{kind.upper()}-{idx}",
                summary=f"{kind} memory stays public safe.",
                evidence_hash=f"sha256:{idx}",
                source="test",
                created_at=FIXED,
                expires_at=entry_ttl(kind, FIXED),
            )
            for idx, kind in enumerate(kinds)
        ]
        store.append_many(entries)
        now = FIXED + timedelta(days=max(DEFAULT_TTL_DAYS.values()) + 1)

        stats = store.stats(now)

        assert stats["total_entries"] == len(entries)
        assert stats["active_entries"] == 0
        assert stats["expired_entries"] == len(entries)
        assert store.active(now) == []


@settings(max_examples=60)
@given(
    max_attempts=st.integers(min_value=-20, max_value=20),
    timeout_s=st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
)
def test_model_gateway_retry_and_timeout_policy_property_is_bounded(
    max_attempts: int,
    timeout_s: float,
) -> None:
    config = ModelGatewayConfig(max_attempts=max_attempts, timeout_s=timeout_s)

    assert 1 <= config.normalized_max_attempts() <= 3
    assert 1.0 <= config.normalized_timeout_s() <= 120.0


@settings(max_examples=40)
@given(prompt_suffix=st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")), max_size=48), capability=st.text(max_size=24))
def test_model_gateway_failed_evaluation_property_is_public_and_fail_closed(
    prompt_suffix: str,
    capability: str,
) -> None:
    gateway = ModelGateway(ModelGatewayConfig(provider="none"))
    prompt = f"prompt-secret-{prompt_suffix}"

    result = gateway.evaluate_json(
        capability=capability,
        prompt=prompt,
        schema={"type": "object", "required": [], "properties": {}},
    )

    assert result["status"] == "failed_closed"
    assert result["confidence"] == 0.0
    assert result["output"] is None
    assert result["safety"]["fail_closed"] is True
    assert result["safety"]["trading_dependency"] == "advisory_only"
    assert prompt not in json.dumps(gateway.status(generated_at="2026-05-01T00:00:00Z"))
