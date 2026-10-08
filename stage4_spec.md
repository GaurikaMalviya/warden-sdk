# Spec: Stage 4 — Drift Agent

## Objective

Build a two-tier `DriftAgent` (or `check_drift` function) in `warden.drift_agent` that detects mismatches between an agent's stated natural-language reasoning and its actual proposed action/tool call.

### Inputs
- `reasoning` (str): Stated reasoning from the agent (e.g. `"Approved because income was verified"`).
- `action` (dict): Proposed action/tool call dict (e.g. `{"tool": "approve_refund", "params": {"amount": 50}}` or `{"type": "loan_approval", "amount": 75000}`).

### Output
A `DriftResult` object (or dataclass) containing:
- `drift_detected` (bool): `True` if a reasoning-action mismatch is identified (`drift_score >= threshold`, default threshold 0.5).
- `drift_score` (float): `0.0` (fully aligned) to `1.0` (complete drift/mismatch).
- `tier` (str): `"tier_1"` (deterministic keyword match) or `"tier_2"` (LLM evaluation via Groq).
- `explanation` (str): Human-readable reason for the determination.

---

## Two-Tier Architecture

### Tier 1: Fast Deterministic First Pass (0ms LLM overhead)
Tokenizes the action identifier (`tool` or `type` field) and parameter keys into core tokens (e.g., `approve_refund` -> `{"approve", "refund"}`). Checks presence in normalized reasoning text.

1. **Clear Match:**
   - All primary action tokens exist in the reasoning (e.g. reasoning mentions both "approve" and "refund" for `approve_refund`).
   - Returns immediately with `drift_score = 0.0`, `drift_detected = False`, `tier = "tier_1"`. No LLM call.

2. **Clear Mismatch:**
   - Zero token overlap between action tokens/params and reasoning text (e.g. reasoning discusses "database sessions" while tool is `delete_user_account`).
   - Returns immediately with `drift_score = 1.0`, `drift_detected = True`, `tier = "tier_1"`. No LLM call.

### Tier 2: Groq LLM Escalation (Ambiguous Cases Only)
When Tier 1 cannot make a confident determination (e.g. partial token overlap where verb matches but target noun is missing, such as reasoning `"Approved because income was verified"` with tool `approve_refund`):
- Calls Groq API using `llama-3.1-8b-instant`.
- System prompt instructs JSON-only evaluation of semantic consistency between reasoning and action.
- Returns JSON with `drift_score` (float 0.0 - 1.0) and `explanation`.
- `tier = "tier_2"`.

---

## Code Honesty & Documentation
Every decision path is explicitly documented with comments indicating which tier handled the case and why, honoring latency claims.

---

## Testing Strategy
Using `pytest` with mocked Groq calls:
1. **Clear Match (Tier 1):** Verify returns `tier="tier_1"` and no LLM call is made.
2. **Clear Mismatch (Tier 1):** Verify returns `tier="tier_1"` and no LLM call is made.
3. **Ambiguous Case (Tier 2):** Verify triggers Tier 2, calls Groq `llama-3.1-8b-instant`, parses JSON score and explanation, and sets `tier="tier_2"`.
4. **Missing/Malformed fields:** Verify robustness with missing keys in action dict.
