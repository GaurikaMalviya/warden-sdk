"""tests/test_guard.py — pytest suite for warden.guard.Guard."""

import os
from unittest.mock import patch, MagicMock

import pytest

from warden.guard import Guard
from warden.interceptor import Decision
from warden.drift_agent import DriftResult


@pytest.fixture
def structured_policy_yaml(tmp_path):
    """Fixture creating a YAML file with structured rules."""
    content = """
- field: amount
  operator: ">"
  value: 50000
  action: block
  reason: Loan amount exceeds standard threshold.
- field: country
  operator: in
  value: ["CU", "IR", "KP"]
  action: block
  reason: Sanctioned jurisdiction.
"""
    file_path = tmp_path / "structured_rules.yaml"
    file_path.write_text(content, encoding="utf-8")
    return str(file_path)


@pytest.fixture
def plain_english_policy_yaml(tmp_path):
    """Fixture creating a YAML file with plain English rules."""
    content = """
- "loans over $50k must be blocked"
- "block transactions originating from sanctioned countries"
"""
    file_path = tmp_path / "english_rules.yaml"
    file_path.write_text(content, encoding="utf-8")
    return str(file_path)


class TestGuardInitialization:

    def test_structured_yaml_loads_without_llm(self, structured_policy_yaml):
        """Pre-structured YAML rules should load directly without invoking PolicyAgent."""
        with patch("warden.guard.compile_rule") as mock_compile:
            guard = Guard(policy_file=structured_policy_yaml, verbose=False)
            mock_compile.assert_not_called()
            assert len(guard.policy) == 2
            assert guard.policy[0]["field"] == "amount"
            assert guard.policy[0]["action"] == "block"

    def test_plain_english_yaml_invokes_policy_agent(self, plain_english_policy_yaml):
        """Plain English rules should be compiled via compile_rule."""
        compiled_rule = {
            "field": "amount",
            "operator": ">",
            "value": 50000,
            "action": "block",
            "reason": "Loans over $50k must be blocked",
        }
        with patch("warden.guard.compile_rule", return_value=compiled_rule) as mock_compile:
            guard = Guard(policy_file=plain_english_policy_yaml, verbose=False)
            assert mock_compile.call_count == 2
            assert len(guard.policy) == 2
            assert guard.policy[0] == compiled_rule


class TestGuardCheckPipeline:

    def test_check_allow(self, structured_policy_yaml):
        guard = Guard(policy_file=structured_policy_yaml, verbose=False)
        action = {"type": "loan_approval", "amount": 25000, "country": "US"}
        decision = guard.check(action)

        assert decision.allowed is True
        assert decision.status == "ALLOW"

    def test_check_block_threshold(self, structured_policy_yaml):
        guard = Guard(policy_file=structured_policy_yaml, verbose=False)
        action = {"type": "loan_approval", "amount": 75000, "country": "US"}
        decision = guard.check(action)

        assert decision.allowed is False
        assert decision.status == "BLOCK"
        assert "exceeds standard threshold" in decision.reason

    def test_check_with_reasoning_consistent(self, structured_policy_yaml):
        """When reasoning is consistent with action, decision remains ALLOW."""
        guard = Guard(policy_file=structured_policy_yaml, verbose=False)
        action = {"type": "loan_approval", "amount": 10000, "country": "US"}
        reasoning = "Approved standard loan request within allowable limits"

        decision = guard.check(action, agent_reasoning=reasoning)
        assert decision.allowed is True
        assert decision.status == "ALLOW"

    @patch("warden.guard.check_drift")
    def test_check_with_reasoning_drift_triggers_block(self, mock_drift, structured_policy_yaml):
        """When drift is detected, Guard overrides an ALLOW into a BLOCK."""
        mock_drift.return_value = DriftResult(
            drift_detected=True,
            drift_score=0.92,
            tier="tier_2",
            explanation="Stated reasoning concerned income verification, but action executed refund.",
        )

        guard = Guard(policy_file=structured_policy_yaml, verbose=False)
        action = {"type": "loan_approval", "amount": 10000, "country": "US"}
        reasoning = "refund processed due to billing error"

        decision = guard.check(action, agent_reasoning=reasoning)
        assert decision.allowed is False
        assert decision.status == "BLOCK"
        assert "Drift detected (tier_2)" in decision.reason
        assert "refund" in decision.reason


class TestGuardFailClosed:
    """Tests ensuring Guard NEVER crashes or fails-open upon internal errors."""

    @patch("warden.guard._check")
    def test_fail_closed_on_interceptor_exception(self, mock_check, structured_policy_yaml):
        """If the Interceptor throws an unhandled exception, return BLOCK, do not crash."""
        mock_check.side_effect = RuntimeError("Fatal memory error or corrupted policy AST")

        guard = Guard(policy_file=structured_policy_yaml, verbose=False)
        action = {"type": "loan_approval", "amount": 10000}

        # Must not raise RuntimeError
        decision = guard.check(action)

        assert isinstance(decision, Decision)
        assert decision.allowed is False
        assert decision.status == "BLOCK"
        assert "Fail-closed: internal guard error (RuntimeError)" in decision.reason
        assert "Fatal memory error" in decision.reason
        assert decision.triggered_rule["error_type"] == "RuntimeError"

    @patch("warden.guard.check_drift")
    def test_fail_closed_on_drift_agent_network_timeout(self, mock_drift, structured_policy_yaml):
        """If DriftAgent throws a network timeout or API exception, return BLOCK."""
        mock_drift.side_effect = TimeoutError("Groq API endpoint timed out after 3000ms")

        guard = Guard(policy_file=structured_policy_yaml, verbose=False)
        action = {"type": "loan_approval", "amount": 10000}
        reasoning = "Routine loan approval based on verified credit score"

        # Must not raise TimeoutError
        decision = guard.check(action, agent_reasoning=reasoning)

        assert isinstance(decision, Decision)
        assert decision.allowed is False
        assert decision.status == "BLOCK"
        assert "Fail-closed: internal guard error (TimeoutError)" in decision.reason
        assert "Groq API endpoint timed out" in decision.reason
