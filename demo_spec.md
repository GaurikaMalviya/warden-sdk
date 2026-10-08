# Spec: Standalone Demo (`examples/demo.py`)

## Objective

Create a standalone, reproducible demo script in `examples/demo.py` showcasing Warden's three core guardrail decisions:
1. **Scenario 1:** Normal loan approval under threshold → **ALLOW** (Green)
2. **Scenario 2:** Loan approval exceeding $50k threshold → **BLOCK** (Red)
3. **Scenario 3:** Refund action where stated reasoning has zero relation to the tool called → **ESCALATE** via the Drift Agent (Yellow)

---

## Determinism & Reliability Guarantee

- **Zero LLM Variability:** Scenarios 1 and 2 are evaluated by the deterministic Interceptor.
- **Scenario 3 Determinism:** The reasoning is designed so that the Drift Agent's Tier 1 deterministic keyword/token pass catches the mismatch with 100% certainty (0% token overlap between reasoning and action/params), guaranteeing **zero reliance on live LLM APIs** and sub-millisecond execution.
- Executing the script multiple times in succession must produce identical terminal output every run.

---

## Components

1. `examples/rules.yaml`:
   Pre-structured YAML policy file containing threshold rules for loan approvals.
2. `src/warden/guard.py`:
   Support configurable `drift_action` (`"BLOCK"` or `"ESCALATE"`, defaulting to `"BLOCK"`) so drift detections can trigger an escalation when desired.
3. `examples/demo.py`:
   Clean, concise runner script using the packaged `Guard` class, executing the 3 scenarios and verifying expected statuses (`ALLOW`, `BLOCK`, `ESCALATE`).
