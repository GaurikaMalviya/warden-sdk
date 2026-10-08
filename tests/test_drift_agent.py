"""tests/test_drift_agent.py — pytest suite for warden.drift_agent."""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from warden.drift_agent import check_drift, DriftResult


def _mock_groq_response(content: str):
    """Mock Groq completion response."""
    mock_message = MagicMock()
    mock_message.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


class TestDriftAgent:

    def test_tier1_clear_match(self):
        """When reasoning explicitly matches all action keywords, Tier 1 resolves immediately."""
        reasoning = "Approved refund for customer account following standard return policy."
        action = {"tool": "approve_refund", "params": {"customer_id": "c123", "amount": 45.0}}

        # Ensure no Groq client call is made even if key is absent
        if "GROQ_API_KEY" in os.environ:
            del os.environ["GROQ_API_KEY"]

        result = check_drift(reasoning, action)

        assert isinstance(result, DriftResult)
        assert result.tier == "tier_1"
        assert result.drift_detected is False
        assert result.drift_score == 0.0
        assert "Deterministic match" in result.explanation

    def test_tier1_clear_mismatch(self):
        """When reasoning has zero token overlap with action, Tier 1 resolves immediately."""
        reasoning = "Inspected database active connections and rotated temporary session tokens."
        action = {"tool": "approve_refund", "params": {"amount": 100}}

        if "GROQ_API_KEY" in os.environ:
            del os.environ["GROQ_API_KEY"]

        result = check_drift(reasoning, action)

        assert isinstance(result, DriftResult)
        assert result.tier == "tier_1"
        assert result.drift_detected is True
        assert result.drift_score == 1.0
        assert "Deterministic mismatch" in result.explanation

    @patch("warden.drift_agent.Groq")
    def test_tier2_ambiguous_escalation_drift_detected(self, mock_groq):
        """Partial overlap (e.g. 'approved' matches, but 'refund' vs 'income') triggers Tier 2 Groq call."""
        os.environ["GROQ_API_KEY"] = "mock-key-for-tier2"

        mock_client = MagicMock()
        mock_groq.return_value = mock_client

        llm_response = json.dumps({
            "drift_score": 0.85,
            "drift_detected": True,
            "explanation": "Reasoning claimed approval was based on income verification, but action executed was refund."
        })
        mock_client.chat.completions.create.return_value = _mock_groq_response(llm_response)

        reasoning = "approved because income was verified"
        action = {"tool": "approve_refund", "params": {"amount": 50000}}

        result = check_drift(reasoning, action)

        assert result.tier == "tier_2"
        assert result.drift_detected is True
        assert result.drift_score == 0.85
        assert "income verification" in result.explanation

        # Verify Groq was called with llama-3.1-8b-instant
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "llama-3.1-8b-instant"
        assert call_kwargs["response_format"] == {"type": "json_object"}

    @patch("warden.drift_agent.Groq")
    def test_tier2_ambiguous_escalation_consistent(self, mock_groq):
        """Ambiguous phrasing where Tier 2 LLM judges the action as consistent."""
        os.environ["GROQ_API_KEY"] = "mock-key-for-tier2"

        mock_client = MagicMock()
        mock_groq.return_value = mock_client

        llm_response = json.dumps({
            "drift_score": 0.1,
            "drift_detected": False,
            "explanation": "Releasing funds aligns with the approval rationale stated in reasoning."
        })
        mock_client.chat.completions.create.return_value = _mock_groq_response(llm_response)

        # Partial overlap: "client" and "payout" appear, but tool is "process_payout_hold"
        reasoning = "approved client payout after reviewing contract terms"
        action = {"tool": "process_payout_hold", "params": {"client_id": "c123"}}

        result = check_drift(reasoning, action)

        assert result.tier == "tier_2"
        assert result.drift_detected is False
        assert result.drift_score == 0.1

    def test_tier2_missing_api_key_raises_error(self):
        """If Tier 2 is triggered but GROQ_API_KEY is not set, raise a clear ValueError."""
        if "GROQ_API_KEY" in os.environ:
            del os.environ["GROQ_API_KEY"]

        reasoning = "approved because income was verified"
        action = {"tool": "approve_refund", "params": {"amount": 500}}

        with pytest.raises(ValueError, match="GROQ_API_KEY environment variable is required"):
            check_drift(reasoning, action)
