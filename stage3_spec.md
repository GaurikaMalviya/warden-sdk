# Spec: Stage 3 — Policy Agent

## Objective

Provide a `PolicyAgent` class (or function) in `warden.policy_agent` that translates a natural language constraint (e.g. "block transactions over $1000") into a structured policy dictionary (`{"field": "...", "operator": "...", "value": ..., "action": "block", "reason": "..."}`) compatible with `warden.interceptor.check()`.

This is intended for setup-time policy compilation, so latency is less critical than correctness.

## Tech Stack & Dependencies

- **LLM Client:** `groq` (OpenAI-compatible SDK)
- **Model:** `llama-3.3-70b-versatile`
- **Output Mode:** JSON mode (`response_format={"type": "json_object"}`)
- **Auth:** `GROQ_API_KEY` from environment variables (never hardcoded)

## Interface

```python
from warden.policy_agent import compile_rule

rule_dict = compile_rule("loans over $50k require a second reviewer's approval before being approved")
# Returns:
# {
#   "field": "amount",  # or "loan_amount"
#   "operator": ">",
#   "value": 50000,
#   "action": "escalate",
#   "reason": "Loans over $50k require a second reviewer's approval before being approved"
# }
```

## Behavior & Error Handling

- Uses a strict system prompt describing the allowed operators (from Stage 1: `==, !=, >, <, >=, <=, in, not in`) and allowed actions (`block, escalate, allow`).
- Instructs the model to output *only* valid JSON.
- **Retry Logic:** If the model returns malformed JSON, or JSON that does not meet the basic schema, catch the error and retry exactly *once*.
- **Failure Mode:** If the retry also fails, raise a `ValueError` or custom `PolicyGenerationError` with a clear message. Do not fail silently.

## Security & Environment

- The agent must retrieve `os.environ["GROQ_API_KEY"]`. If missing, it should raise a clear error indicating the missing variable.

## Testing Strategy

- Tests should mock the `groq.Groq` client so no live network calls are made.
- **Test Scenarios:**
  - Successful parsing of valid JSON from the mocked response.
  - Automatic retry upon receiving invalid JSON on the first attempt, followed by valid JSON on the second.
  - Raising a custom exception if both attempts fail.
  - Missing `GROQ_API_KEY` raises an exception immediately.

## File Structure Additions

- `warden/policy_agent.py`
- `tests/test_policy_agent.py`
- Update `warden/__init__.py` to export `compile_rule`.
- Add `groq` to the `stage3` extra in `pyproject.toml` (if not already there).
