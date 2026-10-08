"""
tests/test_interceptor.py — pytest suite for warden.interceptor.

Coverage targets:
  - ALLOW: action satisfies all rules
  - BLOCK: action violates a threshold rule
  - ESCALATE: action triggers an escalate rule
  - Default ALLOW: no rule matches the action's fields
  - Missing field: absent field silently skips rule, still ALLOWs
  - First-match wins: multi-rule policies stop at the first triggered rule
  - Unknown operator: raises ValueError
  - Type mismatch: raises TypeError
  - Empty policy: always ALLOWs
  - `in` / `not_in` operators
"""

import pytest
from warden.interceptor import Decision, check


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def loan_block_rule() -> dict:
    return {
        "field":    "amount",
        "operator": ">",
        "value":    50_000,
        "action":   "block",
        "reason":   "Exceeds threshold, requires co-signer review.",
    }


@pytest.fixture()
def loan_escalate_rule() -> dict:
    return {
        "field":    "amount",
        "operator": ">",
        "value":    50_000,
        "action":   "escalate",
        "reason":   "Requires senior-underwriter approval.",
    }


# ---------------------------------------------------------------------------
# Core decision tests
# ---------------------------------------------------------------------------

class TestAllow:
    """Action satisfies all rules — must return ALLOW."""

    def test_amount_below_threshold(self, loan_block_rule):
        action = {"type": "loan_approval", "amount": 30_000, "applicant_id": "1001"}
        decision = check(action, [loan_block_rule])

        assert decision.allowed is True
        assert decision.status == "ALLOW"
        assert decision.triggered_rule is None

    def test_amount_equal_to_threshold_not_triggered(self):
        """Strict > operator: equal value must NOT trigger."""
        rule = {"field": "amount", "operator": ">", "value": 50_000,
                "action": "block", "reason": "over limit"}
        decision = check({"amount": 50_000}, [rule])

        assert decision.status == "ALLOW"

    def test_multiple_rules_none_triggered(self, loan_block_rule):
        rule2 = {"field": "risk_score", "operator": ">", "value": 0.9,
                 "action": "block", "reason": "high risk"}
        action = {"amount": 20_000, "risk_score": 0.5}
        decision = check(action, [loan_block_rule, rule2])

        assert decision.status == "ALLOW"


class TestBlock:
    """Action violates a threshold rule — must return BLOCK."""

    def test_amount_exceeds_threshold(self, loan_block_rule):
        action = {"type": "loan_approval", "amount": 75_000, "applicant_id": "4482"}
        decision = check(action, [loan_block_rule])

        assert decision.allowed is False
        assert decision.status == "BLOCK"
        assert "co-signer" in decision.reason
        assert decision.triggered_rule is loan_block_rule

    def test_block_on_equality(self):
        rule = {"field": "category", "operator": "==", "value": "denied",
                "action": "block", "reason": "category is denied"}
        decision = check({"category": "denied"}, [rule])

        assert decision.status == "BLOCK"

    def test_block_on_not_in(self):
        rule = {"field": "currency", "operator": "not_in",
                "value": ["USD", "EUR", "GBP"],
                "action": "block", "reason": "unsupported currency"}
        decision = check({"currency": "XYZ"}, [rule])

        assert decision.status == "BLOCK"

    def test_less_than_operator(self):
        rule = {"field": "credit_score", "operator": "<", "value": 600,
                "action": "block", "reason": "credit score too low"}
        decision = check({"credit_score": 540}, [rule])

        assert decision.status == "BLOCK"
        assert decision.allowed is False


class TestEscalate:
    """Action triggers an escalate rule — must return ESCALATE."""

    def test_amount_exceeds_escalate_threshold(self, loan_escalate_rule):
        action = {"amount": 55_000}
        decision = check(action, [loan_escalate_rule])

        assert decision.allowed is False
        assert decision.status == "ESCALATE"
        assert decision.triggered_rule is loan_escalate_rule

    def test_in_operator_escalate(self):
        rule = {"field": "applicant_tier", "operator": "in",
                "value": ["vip", "premium"],
                "action": "escalate", "reason": "VIP requires manual review"}
        decision = check({"applicant_tier": "vip"}, [rule])

        assert decision.status == "ESCALATE"


# ---------------------------------------------------------------------------
# Default ALLOW — no matching rule
# ---------------------------------------------------------------------------

class TestDefaultAllow:
    """
    When no rule matches, the interceptor defaults to ALLOW (fail-open).

    Rationale (documented in interceptor.py):  The SDK is inline middleware;
    silently blocking all unconfigured actions would break pipelines.
    Developers must explicitly opt into restrictions via rules.
    """

    def test_unrelated_field_in_policy(self):
        """Policy only covers 'amount'; action has no 'amount' key."""
        rule = {"field": "amount", "operator": ">", "value": 0,
                "action": "block", "reason": "any amount blocked"}
        action = {"type": "send_email", "recipient": "ops@example.com"}
        decision = check(action, [rule])

        assert decision.allowed is True
        assert decision.status == "ALLOW"
        assert decision.triggered_rule is None

    def test_empty_policy_always_allows(self):
        decision = check({"amount": 999_999}, [])

        assert decision.status == "ALLOW"
        assert decision.allowed is True


# ---------------------------------------------------------------------------
# Missing field — silent skip
# ---------------------------------------------------------------------------

class TestMissingField:
    """A rule whose field is absent from the action is skipped, not violated."""

    def test_missing_field_skips_rule(self):
        rule = {"field": "amount", "operator": ">", "value": 0,
                "action": "block", "reason": "amount required"}
        action = {"type": "read_data"}  # no 'amount' key

        decision = check(action, [rule])

        assert decision.status == "ALLOW"

    def test_missing_field_skips_then_other_rule_triggers(self):
        rules = [
            {"field": "amount",     "operator": ">", "value": 0,
             "action": "block",     "reason": "amount rule"},
            {"field": "risk_score", "operator": ">", "value": 0.8,
             "action": "escalate",  "reason": "high risk"},
        ]
        action = {"risk_score": 0.95}  # amount absent; second rule should fire

        decision = check(action, rules)

        assert decision.status == "ESCALATE"


# ---------------------------------------------------------------------------
# First-match / short-circuit
# ---------------------------------------------------------------------------

class TestFirstMatchWins:
    """Rules are evaluated in order; the first triggered rule determines outcome."""

    def test_escalate_before_block_wins(self):
        rules = [
            {"field": "amount", "operator": ">", "value": 50_000,
             "action": "escalate", "reason": "escalate rule"},
            {"field": "amount", "operator": ">", "value": 60_000,
             "action": "block",   "reason": "block rule"},
        ]
        # Both rules match 75_000, but escalate is first
        decision = check({"amount": 75_000}, rules)

        assert decision.status == "ESCALATE"
        assert "escalate rule" in decision.reason

    def test_block_before_escalate_wins(self):
        rules = [
            {"field": "amount", "operator": ">", "value": 50_000,
             "action": "block",   "reason": "block first"},
            {"field": "amount", "operator": ">", "value": 60_000,
             "action": "escalate", "reason": "escalate second"},
        ]
        decision = check({"amount": 75_000}, rules)

        assert decision.status == "BLOCK"


# ---------------------------------------------------------------------------
# Error conditions
# ---------------------------------------------------------------------------

class TestErrors:
    """Misconfigured policies must fail loudly."""

    def test_unknown_operator_raises_value_error(self):
        rule = {"field": "amount", "operator": "??",
                "value": 0, "action": "block", "reason": "bad op"}
        with pytest.raises(ValueError, match="Unknown operator"):
            check({"amount": 100}, [rule])

    def test_unknown_rule_action_raises_value_error(self):
        rule = {"field": "amount", "operator": ">",
                "value": 0, "action": "suspend", "reason": "bad action"}
        with pytest.raises(ValueError, match="Unknown rule action"):
            check({"amount": 100}, [rule])

    def test_type_mismatch_raises_type_error(self):
        rule = {"field": "amount", "operator": ">",
                "value": "fifty-thousand",  # can't compare int > str
                "action": "block", "reason": "bad type"}
        with pytest.raises(TypeError):
            check({"amount": 75_000}, [rule])


# ---------------------------------------------------------------------------
# Decision immutability
# ---------------------------------------------------------------------------

class TestDecisionImmutability:
    """Decision is frozen — callers cannot mutate returned objects."""

    def test_frozen(self, loan_block_rule):
        decision = check({"amount": 75_000}, [loan_block_rule])
        with pytest.raises((AttributeError, TypeError)):
            decision.status = "ALLOW"  # type: ignore[misc]
