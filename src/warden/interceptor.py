"""
warden.interceptor — deterministic action-policy evaluation engine.

No I/O, no LLM calls, no side effects.
"""

from dataclasses import dataclass

# Maps operator strings to (action_value, threshold) -> bool callables.
_OPERATORS = {
    ">":      lambda a, b: a > b,
    "<":      lambda a, b: a < b,
    ">=":     lambda a, b: a >= b,
    "<=":     lambda a, b: a <= b,
    "==":     lambda a, b: a == b,
    "!=":     lambda a, b: a != b,
    "in":     lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "not in": lambda a, b: a not in b,
}

# Maps rule["action"] strings to Decision status strings.
_ACTIONS = {"block": "BLOCK", "escalate": "ESCALATE"}


@dataclass(frozen=True, slots=True)
class Decision:
    """Immutable result of :func:`check`."""
    allowed: bool
    status: str          # "ALLOW" | "BLOCK" | "ESCALATE"
    reason: str
    triggered_rule: dict | None = None


def check(action: dict, policy: list[dict]) -> Decision:
    """Evaluate *action* against *policy* and return a :class:`Decision`.

    Rules are evaluated in order; first match wins (short-circuit).

    Default — ALLOW (fail-open):
        The interceptor is inline middleware. Blocking unconfigured action
        types silently breaks pipelines. Opt into restrictions explicitly;
        add a catch-all block rule if you need fail-closed behaviour.

    Raises:
        ValueError: Unknown operator or rule action string.
        TypeError:  Incompatible types for the requested comparison.
    """
    for rule in policy:
        field = rule["field"]

        # Field absent from action — skip, absence is not a violation.
        if field not in action:
            continue

        operator = rule["operator"]
        if operator not in _OPERATORS:
            raise ValueError(
                f"Unknown operator {operator!r}. Supported: {sorted(_OPERATORS)}"
            )

        actual, threshold = action[field], rule["value"]
        try:
            matched = _OPERATORS[operator](actual, threshold)
        except TypeError as exc:
            raise TypeError(
                f"Cannot compare action[{field!r}]={actual!r} "
                f"with threshold={threshold!r} using {operator!r}: {exc}"
            ) from exc

        if not matched:
            continue

        rule_action = rule["action"].lower()
        if rule_action not in _ACTIONS:
            raise ValueError(
                f"Unknown rule action {rule_action!r}. Valid values: {sorted(_ACTIONS)}"
            )
        return Decision(
            allowed=False,
            status=_ACTIONS[rule_action],
            reason=rule.get("reason", "Policy rule triggered."),
            triggered_rule=rule,
        )

    # No rule matched — default ALLOW (fail-open, see docstring above).
    return Decision(True, "ALLOW", "No policy rule matched; action permitted by default.")
