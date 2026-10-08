"""warden.policy_agent — LLM-based policy compiler for Warden.

Translates natural language constraints into structured JSON policy rules.
"""

import json
import os

from groq import Groq

_SYSTEM_PROMPT = """You are a policy compiler for the Warden SDK.
Your job is to translate a natural language constraint into a strict JSON object.

The output MUST be a JSON object with the following keys:
- "field": (string) the name of the field being constrained (e.g. "amount", "loan_amount", "type").
- "operator": (string) MUST be one of: "==", "!=", ">", "<", ">=", "<=", "in", "not in".
- "value": (any) the threshold or value to compare against. Use numbers for amounts.
- "action": (string) MUST be one of: "allow", "block", "escalate".
- "reason": (string) a concise summary of the rule.

Return ONLY the JSON object. Do not wrap it in markdown block quotes.
"""


class PolicyGenerationError(Exception):
    """Raised when the Policy Agent fails to compile a rule into valid JSON."""
    pass


def compile_rule(text: str) -> dict:
    """Compile a natural language rule into a structured policy dictionary.

    Requires the GROQ_API_KEY environment variable.

    Args:
        text: A natural language rule, e.g. "block transactions over $1000".

    Returns:
        dict: A policy rule dictionary compatible with `check()`.

    Raises:
        ValueError: If GROQ_API_KEY is not set.
        PolicyGenerationError: If the model fails to return valid structured JSON
            after retries.
    """
    if "GROQ_API_KEY" not in os.environ:
        raise ValueError("GROQ_API_KEY environment variable is required")

    client = Groq()

    # Retry exactly once
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Low temp for deterministic structure
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from model")

            rule = json.loads(content)
            
            # Basic validation
            required_keys = {"field", "operator", "value", "action", "reason"}
            if not required_keys.issubset(rule.keys()):
                raise ValueError(f"Missing required keys. Got: {list(rule.keys())}")
            if rule["operator"] not in {"==", "!=", ">", "<", ">=", "<=", "in", "not in"}:
                raise ValueError(f"Invalid operator: {rule['operator']}")
            if rule["action"] not in {"allow", "block", "escalate"}:
                raise ValueError(f"Invalid action: {rule['action']}")

            return rule
            
        except (json.JSONDecodeError, ValueError) as e:
            if attempt == 1:
                # Failed on retry
                raise PolicyGenerationError(f"Failed to compile rule after retries: {e}")
            continue
            
    raise PolicyGenerationError("Failed to compile rule") # Should be unreachable due to if attempt == 1
