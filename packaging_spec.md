# Spec: Stage 5 — SDK Packaging & Distribution

## Objective

Package Warden as a production-grade, installable Python SDK using the standard `src/` layout (`src/warden/`).

---

## 1. Project Structure (`src/` Layout)

```
warden-sdk/
├── pyproject.toml
├── README.md
├── src/
│   └── warden/
│       ├── __init__.py
│       ├── guard.py
│       ├── interceptor.py
│       ├── output.py
│       ├── reporter.py
│       ├── policy_agent.py
│       └── drift_agent.py
└── tests/
    ├── test_interceptor.py
    ├── test_output.py
    ├── test_reporter.py
    ├── test_policy_agent.py
    ├── test_drift_agent.py
    ├── test_guard.py
    └── test_smoke.py
```

---

## 2. Dependency Specification

In `pyproject.toml`:
- **Core Dependencies (pinned to reasonable version ranges):**
  - `rich>=13.0.0,<14.0.0`
  - `pyyaml>=6.0.0,<7.0.0`
  - `groq>=0.9.0,<1.0.0`
- **Optional / Dev Dependencies:**
  - `pytest>=8.0`
  - `pytest-benchmark`

---

## 3. Metadata Specification

- Package Name: `warden-sdk`
- Version: `0.1.0`
- Python requirement: `>=3.10`
- Readme: `README.md`
- Build Backend: `setuptools.build_meta`
- Package Discovery: `[tool.setuptools.packages.find]` with `where = ["src"]`

---

## 4. Documentation Specification (`README.md`)

1. **One-paragraph description:** Clear statement of Warden as a runtime guardrail layer intercepting autonomous AI agent actions before execution.
2. **Installation instructions:** `pip install -e .` for local development.
3. **Usage example:**
   ```python
   from warden import Guard

   guard = Guard(policy_file="rules.yaml")
   decision = guard.check(agent_action, agent_reasoning=None)
   ```

---

## 5. Verification & Testing

- Smoke test in `tests/test_smoke.py`:
  - Imports `from warden import Guard`
  - Creates a minimal policy file
  - Instantiates `Guard` and validates a sample action.
- Running `pip install -e .` in the environment.
- Confirm all 67 existing tests + new smoke test pass.
