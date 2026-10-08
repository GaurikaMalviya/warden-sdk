# Warden SDK

> **A safety layer that sits between your AI agent and the real world — and makes sure nothing bad slips through.**

---

## Before We Talk Code: What Is Warden, Really?

Imagine you have hired a very capable but occasionally reckless assistant. They can approve loans, process refunds, execute trades, send emails — all on your behalf, automatically. Most of the time, they do the right thing. But sometimes they make a decision that is clearly wrong: approving a $200,000 loan when your policy says the limit is $50,000, or processing a refund when they told you they were reviewing an employment file.

Now imagine a second, much calmer person standing at the door before every one of those actions goes out. They have a printed copy of your rules. Before anything happens, they check: *"Does this action comply with our policies? And does what the agent *said* it was doing actually match what it is *about* to do?"*

If the answer to either question is no, that door does not open.

**That second person is Warden.**

Warden is not a replacement for your AI agent. It is the guardrail layer that wraps around it — watching every proposed action, enforcing your rules, and catching the moments when an agent drifts away from its stated intent. It gives you a hard, auditable answer — **ALLOW**, **BLOCK**, or **ESCALATE to a human** — before a single irreversible action touches your system.

---

## Who Is This For?

| You are... | Warden helps you... |
|---|---|
| A product manager or business owner | Understand exactly what rule was broken and why an action was blocked — in plain English |
| A developer building AI-powered workflows | Drop a single `guard.check()` call before any agent action to enforce your policies automatically |
| A compliance or risk officer | Define policies in a simple rules file (no coding required) and get a full audit trail of every decision |
| A hackathon judge | Run one script and watch three live guardrail decisions fire in under a second |

---

## What Does It Look Like In Practice?

Your AI agent proposes an action. Warden evaluates it. You get back a colour-coded decision:

```
+----------------------------------- ALLOW -----------------------------------+
| Reason   No policy rule matched; action permitted by default.               |
| Action   {"type": "loan_approval", "amount": 15000, "applicant_id": ...}   |
+-----------------------------------------------------------------------------+

+----------------------------------- BLOCK -----------------------------------+
| Reason   Loan amount exceeds $50,000 limit. Requires secondary review.      |
| Rule     field=amount  operator=>  value=50000                              |
| Action   {"type": "loan_approval", "amount": 75000, "applicant_id": ...}   |
+-----------------------------------------------------------------------------+

+--------------------------------- ESCALATE ----------------------------------+
| Reason   Drift detected (tier_1): zero keyword overlap with action.         |
| Drift    tier=tier_1  drift_score=1.0                                       |
| Action   {"tool": "approve_refund", "params": {"refund_id": "ref_881"}}    |
+-----------------------------------------------------------------------------+
```

Green means the action passed. Red means it was blocked by a policy rule. Yellow means the agent's stated reasoning and its actual intended action do not match — a human needs to look at this.

---

## Running the Live Demo (Judges: Start Here)

No setup beyond installation. Clone the repository, install the package, and run:

```bash
pip install -e .
python examples/demo.py
```

You will see three scenarios fire deterministically in the terminal, each with a colour-coded panel. The entire run takes under two seconds. No live API calls are required for any of the three scenarios — the demo is fully reproducible.

---

## Writing Your Own Policy Rules

Policies live in a plain YAML file. No programming knowledge required. Each rule is a simple condition:

```yaml
# rules.yaml

- field: amount
  operator: ">"
  value: 50000
  action: block
  reason: Loan amount exceeds $50,000 limit. Requires secondary underwriting review.

- field: transaction_type
  operator: "=="
  value: "wire_transfer"
  action: escalate
  reason: All wire transfers must be reviewed by the compliance team.
```

The supported operators are: `==`, `!=`, `>`, `<`, `>=`, `<=`, `in`, `not in`.

The supported actions are: `block` (hard stop), `escalate` (flag for human review), `allow` (explicit permit).

If you prefer writing rules in plain English instead of structured YAML, Warden's Policy Agent can translate them for you at startup using an LLM. See the [Policy Agent](#policy-agent-natural-language-rules) section below.

---

## Installation

**Requirements:** Python 3.10 or newer.

```bash
# Install for use
pip install -e .

# Install with development dependencies (pytest, benchmarking)
pip install -e ".[dev]"
```

Set your Groq API key as an environment variable if you intend to use natural-language policy compilation or the Drift Agent's LLM fallback:

```bash
export GROQ_API_KEY="your-key-here"     # macOS / Linux
set GROQ_API_KEY=your-key-here          # Windows
```

---

## Quickstart

```python
from warden import Guard

# 1. Instantiate with a policy file
guard = Guard(policy_file="rules.yaml")

# 2. Before your agent executes an action, check it
decision = guard.check(
    agent_action={"type": "loan_approval", "amount": 75000, "applicant_id": "app_9910"},
    agent_reasoning="Applicant income verified. Proceeding with approval.",
)

# 3. Act on the result
if not decision.allowed:
    print(f"Blocked: {decision.reason}")
```

`guard.check()` returns a `Decision` object every time. It never raises an exception — see the [Fail-Closed Guarantee](#fail-closed-guarantee) below.

---

---

# Technical Deep Dive

The rest of this document is for developers who want to understand exactly how Warden works under the hood.

---

## Architecture Overview

```
Agent Proposed Action
        │
        ▼
┌─────────────────────────────────────┐
│            Guard.check()            │
│                                     │
│  ┌──────────────────────────────┐   │
│  │  Stage 1: Interceptor        │   │   ← Deterministic, sub-millisecond
│  │  Rule-based policy engine    │   │
│  └──────────────────────────────┘   │
│           │ ALLOW?                  │
│           ▼                         │
│  ┌──────────────────────────────┐   │
│  │  Stage 4: Drift Agent        │   │   ← Only runs if reasoning provided
│  │  Tier 1: Keyword match       │   │   ← Zero LLM cost for clear cases
│  │  Tier 2: Groq LLM fallback  │   │   ← Only for ambiguous cases
│  └──────────────────────────────┘   │
│           │                         │
│           ▼                         │
│  ┌──────────────────────────────┐   │
│  │  Output Layer (Rich panels) │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
        │
        ▼
  Decision(allowed, status, reason, triggered_rule)
```

---

## Module Reference

### `warden.guard` — `Guard` (Public API)

The single entry point for all Warden functionality.

```python
Guard(
    policy_file: str | Path | None = None,
    policy: list[Any] | None = None,
    verbose: bool = True,
    drift_action: str = "BLOCK",
)
```

| Parameter | Type | Description |
|---|---|---|
| `policy_file` | `str \| Path` | Path to a YAML policy file |
| `policy` | `list` | Inline list of rule dicts or plain-English rule strings |
| `verbose` | `bool` | If `True`, prints Rich terminal panels on every check |
| `drift_action` | `str` | Status to assign on drift detection: `"BLOCK"` or `"ESCALATE"` |

```python
Guard.check(
    agent_action: dict,
    agent_reasoning: str | None = None,
    drift_action: str | None = None,
) -> Decision
```

| Parameter | Type | Description |
|---|---|---|
| `agent_action` | `dict` | The proposed action/tool call payload |
| `agent_reasoning` | `str \| None` | The agent's stated natural-language reasoning (enables drift detection) |
| `drift_action` | `str \| None` | Per-call override for drift action status |

---

### `warden.interceptor` — Deterministic Rule Engine

The core policy evaluation engine. Evaluates a structured action dict against a compiled list of policy rules in strict top-down order. The first matching rule wins. If no rule matches, the action is `ALLOW`ed by default.

**`Decision` dataclass:**

```python
@dataclass
class Decision:
    allowed: bool          # True if action is permitted
    status: str            # "ALLOW", "BLOCK", or "ESCALATE"
    reason: str            # Human-readable explanation
    triggered_rule: dict | None  # The rule that triggered the decision, or None
```

**Supported operators:**

| Operator | Behaviour |
|---|---|
| `==` | Exact equality |
| `!=` | Not equal |
| `>` | Greater than |
| `<` | Less than |
| `>=` | Greater than or equal |
| `<=` | Less than or equal |
| `in` | Field value exists in a list |
| `not in` | Field value does not exist in a list |

Execution is pure Python with no external dependencies. Latency is deterministically sub-millisecond.

---

### `warden.drift_agent` — Two-Tier Semantic Consistency Checker

Detects mismatches between what an agent *said* it was doing and what it is *actually* about to do. Runs only when `agent_reasoning` is passed to `guard.check()` and only when the Interceptor returned `ALLOW`.

**`DriftResult` dataclass:**

```python
@dataclass
class DriftResult:
    drift_detected: bool   # True if mismatch detected (drift_score >= 0.5)
    drift_score: float     # 0.0 = fully aligned, 1.0 = complete mismatch
    tier: str              # "tier_1" or "tier_2"
    explanation: str       # Human-readable reason for the determination
```

#### Tier 1 — Deterministic Keyword Match (0 ms LLM overhead)

Tokenises the action's primary identifier (e.g. the `tool` or `type` field value and its parameter keys) into core tokens. Checks for their presence in the normalised reasoning text.

- **All tokens present in reasoning** → `drift_score = 0.0`, `drift_detected = False`. No LLM call.
- **Zero token overlap** → `drift_score = 1.0`, `drift_detected = True`. No LLM call.

The demo's Scenario 3 is always caught at Tier 1 because the reasoning contains zero tokens from the `approve_refund` action.

#### Tier 2 — Groq LLM Fallback (Ambiguous Cases Only)

When Tier 1 finds partial token overlap (neither clear match nor clear mismatch), Warden escalates to a Groq API call using `llama-3.1-8b-instant`. The model is asked to evaluate the semantic consistency of the reasoning and action pair and return a JSON object with a `drift_score` and `explanation`.

This tier fires only when truly necessary, keeping the vast majority of checks free of LLM overhead and API latency.

---

### `warden.policy_agent` — Natural Language Rule Compiler {#policy-agent-natural-language-rules}

Translates a plain-English rule string into a structured rule dict compatible with the Interceptor. This runs at startup when you pass natural-language strings in your policy, not at check time.

```python
from warden.policy_agent import compile_rule

rule = compile_rule("block all wire transfers over $10,000")
# Returns:
# {
#   "field": "amount",
#   "operator": ">",
#   "value": 10000,
#   "action": "block",
#   "reason": "Block all wire transfers over $10,000"
# }
```

Uses `llama-3.3-70b-versatile` via Groq in JSON mode. Includes one automatic retry on malformed responses. Raises `PolicyGenerationError` if both attempts fail. Requires `GROQ_API_KEY` to be set in the environment.

---

### `warden.output` — Rich Terminal Renderer

Renders colour-coded decision panels to the terminal using the [Rich](https://github.com/Textualize/rich) library.

| Decision | Panel Colour |
|---|---|
| `ALLOW` | Bold green |
| `BLOCK` | Bold red |
| `ESCALATE` | Bold yellow |

Each panel displays the reason, the triggered rule details (or drift score and tier), and the full action payload. Rendering is disabled by setting `verbose=False` on the `Guard` instance.

---

## Fail-Closed Guarantee

This is the most important security property of Warden.

> **An action is never permitted if evaluation fails.**

If any internal component — the interceptor, the drift agent, the LLM client, the YAML parser — raises an unhandled exception of any kind, `Guard.check()` catches it and immediately returns:

```python
Decision(
    allowed=False,
    status="BLOCK",
    reason="Fail-closed: internal guard error (ExceptionType): <message>",
    triggered_rule={"error": "...", "error_type": "..."},
)
```

`guard.check()` will never propagate an exception to your calling code. It will never silently permit an action. The path of least privilege is always a block.

---

## Project Structure

```
warden-sdk/
├── pyproject.toml              # Build config, dependencies, metadata
├── README.md
├── examples/
│   ├── demo.py                 # Standalone hackathon demo (run this)
│   └── rules.yaml              # Example policy file for the demo
└── src/
    └── warden/
        ├── __init__.py         # Public exports: Guard, Decision, compile_rule
        ├── guard.py            # Public Guard class — unified orchestrator
        ├── interceptor.py      # Deterministic rule engine + Decision dataclass
        ├── output.py           # Rich terminal rendering
        ├── policy_agent.py     # Natural language → structured rule compiler
        └── drift_agent.py      # Two-tier reasoning-action consistency checker
```

---

## Running the Test Suite

```bash
# Run all tests
python -m pytest tests/ -v

# Run with benchmark timings
python -m pytest tests/ --benchmark-enable -v
```

The test suite covers: interceptor rule evaluation, output rendering, policy agent compilation (with mocked Groq), drift detection (both tiers, with mocked Groq for Tier 2), the full Guard orchestration pipeline, and a packaging smoke test that confirms the installed SDK is importable and functional.

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `rich` | `>=13.0,<14.0` | Colour-coded terminal output |
| `pyyaml` | `>=6.0,<7.0` | YAML policy file parsing |
| `groq` | `>=0.9,<1.0` | LLM client for Policy Agent and Drift Agent Tier 2 |

Python `>=3.10` required.

---

## License

MIT
