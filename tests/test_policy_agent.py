"""tests/test_policy_agent.py — pytest suite for warden.policy_agent."""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from warden.policy_agent import compile_rule, PolicyGenerationError


# ---------------------------------------------------------------------------
# Helpers & Mocks
# ---------------------------------------------------------------------------

def _mock_groq_response(content: str):
    """Create a mock Groq chat completion response."""
    mock_message = MagicMock()
    mock_message.content = content
    
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    
    return mock_response


@pytest.fixture
def groq_api_key():
    """Ensure GROQ_API_KEY is set during tests."""
    original = os.environ.get("GROQ_API_KEY")
    os.environ["GROQ_API_KEY"] = "test-key-123"
    yield
    if original is None:
        del os.environ["GROQ_API_KEY"]
    else:
        os.environ["GROQ_API_KEY"] = original


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPolicyAgent:
    
    def test_missing_api_key_raises_error(self):
        """Must raise immediately if GROQ_API_KEY is missing."""
        if "GROQ_API_KEY" in os.environ:
            del os.environ["GROQ_API_KEY"]
            
        with pytest.raises(ValueError, match="GROQ_API_KEY environment variable is required"):
            compile_rule("block loans > 50k")

    @patch("warden.policy_agent.Groq")
    def test_compile_rule_success(self, mock_groq, groq_api_key):
        """Successfully parses valid JSON from model."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        valid_json = json.dumps({
            "field": "amount",
            "operator": ">",
            "value": 50000,
            "action": "block",
            "reason": "Block loans > 50k"
        })
        
        mock_client.chat.completions.create.return_value = _mock_groq_response(valid_json)
        
        rule = compile_rule("block loans > 50k")
        
        assert rule["field"] == "amount"
        assert rule["operator"] == ">"
        assert rule["value"] == 50000
        assert rule["action"] == "block"
        
        # Verify call params
        mock_client.chat.completions.create.assert_called_once()
        kwargs = mock_client.chat.completions.create.call_args[1]
        assert kwargs["model"] == "llama-3.3-70b-versatile"
        assert kwargs["response_format"] == {"type": "json_object"}

    @patch("warden.policy_agent.Groq")
    def test_retry_on_invalid_json(self, mock_groq, groq_api_key):
        """Retries once if model returns malformed JSON, succeeds on attempt 2."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        invalid_json = "{ bad json"
        valid_json = json.dumps({
            "field": "amount",
            "operator": ">",
            "value": 50000,
            "action": "block",
            "reason": "Block loans > 50k"
        })
        
        # side_effect with a list returns the elements in order on subsequent calls
        mock_client.chat.completions.create.side_effect = [
            _mock_groq_response(invalid_json),
            _mock_groq_response(valid_json)
        ]
        
        rule = compile_rule("block loans > 50k")
        
        assert rule["value"] == 50000
        assert mock_client.chat.completions.create.call_count == 2

    @patch("warden.policy_agent.Groq")
    def test_retry_on_missing_keys(self, mock_groq, groq_api_key):
        """Retries once if model returns valid JSON but missing schema keys."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        missing_keys_json = json.dumps({
            "field": "amount",
            "operator": ">"
            # missing value, action, reason
        })
        valid_json = json.dumps({
            "field": "amount",
            "operator": ">",
            "value": 50000,
            "action": "block",
            "reason": "Block loans > 50k"
        })
        
        mock_client.chat.completions.create.side_effect = [
            _mock_groq_response(missing_keys_json),
            _mock_groq_response(valid_json)
        ]
        
        rule = compile_rule("block loans > 50k")
        assert rule["action"] == "block"
        assert mock_client.chat.completions.create.call_count == 2

    @patch("warden.policy_agent.Groq")
    def test_raises_error_after_max_retries(self, mock_groq, groq_api_key):
        """Raises PolicyGenerationError if both attempts fail."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        invalid_json = "still bad json"
        
        mock_client.chat.completions.create.side_effect = [
            _mock_groq_response(invalid_json),
            _mock_groq_response(invalid_json)
        ]
        
        with pytest.raises(PolicyGenerationError, match="Failed to compile rule after retries"):
            compile_rule("block loans > 50k")
            
        assert mock_client.chat.completions.create.call_count == 2
