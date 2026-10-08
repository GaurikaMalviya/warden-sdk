# Spec: Public Guard Class

## Objective

Unify Stages 1 through 4 into a single, developer-friendly `Guard` class in `warden.guard`:
```python
from warden import Guard

guard = Guard(policy_file="rules.yaml")
decision = guard.check(agent_action, agent_reasoning=None)
```

---

## 1. Initialization (`Guard.__init__`)

```python
def __init__(
    self,
    policy_file: str | None = None,
    policy: list[dict | str] | None = None,
    verbose: bool = True,
) -> None
```

- Accepts `policy_file` (path to a YAML file) or an inline `policy` list.
- If `policy_file` is given, parses YAML content.
- Inspects each rule:
  - **Structured rule** (`dict` with `field`, `operator`, `value`, `action`): preserved as-is. **Zero LLM overhead.**
  - **Plain English rule** (`str` or dict with `"natural_language"`): compiled to a structured dict via `warden.policy_agent.compile_rule()`.
- Stores the compiled list of rule dictionaries for rapid runtime checks.

---

## 2. Check Execution (`Guard.check`)

```python
def check(
    self,
    action: dict,
    reasoning: str | None = None,
) -> Decision
```

Pipeline:
1. **Interceptor Run:** Evaluates `action` deterministically against the compiled policy rules via `warden.interceptor.check()`.
2. **Drift Evaluation:**
   - If `reasoning` is provided and Interceptor returned `ALLOW`:
     - Calls `warden.drift_agent.check_drift(reasoning, action)`.
     - If drift is detected (`drift.drift_detected is True`), overrides the decision to `BLOCK` with reason: `"Drift detected ({drift.tier}): {drift.explanation}"`.
3. **Terminal Output:**
   - If `verbose=True`, renders the formatted decision panel via `warden.output.render()`.
4. Returns the final `Decision`.

---

## 3. Fail-Closed Contract

> **CRITICAL REQUIREMENT:** If any internal component raises an unhandled exception (e.g. malformed action payload, unexpected Groq API error during drift check, network timeouts, or type conversion failures), `check()` **must never crash or fail-open**.

- Catches all uncaught `Exception` instances.
- Immediately synthesizes and returns a `BLOCK` decision:
  ```python
  Decision(
      allowed=False,
      status="BLOCK",
      reason=f"Fail-closed: internal guard error: {exc}",
      triggered_rule={"error": str(exc), "error_type": type(exc).__name__},
  )
  ```
- Renders the block panel if verbose.

---

## 4. Testing Strategy

1. **Initialization:**
   - Load pre-structured YAML (verify 0 LLM calls).
   - Load natural language rules (verify LLM compilation via mocked Groq).
2. **Standard Check:**
   - Allow action.
   - Block action violating threshold.
3. **Drift Integration:**
   - Provide reasoning matching action -> ALLOW.
   - Provide reasoning mismatched with action -> BLOCK due to drift.
4. **Fail-Closed Test:**
   - Mock internal component (e.g., `warden.interceptor.check` or `check_drift`) to raise an unexpected runtime error (e.g. `RuntimeError("Network socket closed")` or `TypeError`).
   - Assert `guard.check()` returns `Decision(allowed=False, status="BLOCK")` and does NOT raise an uncaught exception.
