"""warden.guard — Public unified Guard interface for the Warden SDK.

Wires together:
- Policy loading & compilation (YAML + PolicyAgent)
- Deterministic action interception (Interceptor)
- Semantic consistency checking (DriftAgent)
- Color-coded terminal rendering (Output)
- Fail-closed security guarantee on any unhandled internal exceptions
"""

from pathlib import Path
from typing import Any
import yaml

from warden.interceptor import Decision, check as _check
from warden.output import render
from warden.policy_agent import compile_rule
from warden.drift_agent import check_drift


class Guard:
    """Public runtime guardrail orchestrator for AI agents.

    Example:
        from warden import Guard

        guard = Guard(policy_file="rules.yaml")
        decision = guard.check(agent_action, agent_reasoning="Verified income")
        if not decision.allowed:
            handle_block(decision.reason)
    """

    def __init__(
        self,
        policy_file: str | Path | None = None,
        policy: list[Any] | None = None,
        verbose: bool = True,
        drift_action: str = "BLOCK",
    ) -> None:
        """Initialize Guard with a YAML policy file or inline policy list.

        Args:
            policy_file: Path to a YAML policy configuration.
            policy: Optional in-memory list of rules (structured dicts or natural language strings).
            verbose: If True, renders Rich terminal panels on check().
            drift_action: Decision status to assign when drift is detected ("BLOCK" or "ESCALATE").
        """
        self.verbose = verbose
        self.drift_action = drift_action
        raw_rules: list[Any] = []

        if policy_file is not None:
            path = Path(policy_file)
            with path.open("r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, list):
                    raw_rules = loaded
                elif isinstance(loaded, dict):
                    raw_rules = loaded.get("rules") or loaded.get("policy") or []
        elif policy is not None:
            raw_rules = policy

        self.policy: list[dict] = self._compile_rules(raw_rules)

    def _compile_rules(self, raw_rules: list[Any]) -> list[dict]:
        """Compile raw rules, invoking LLM only for plain-English rules."""
        compiled: list[dict] = []
        for rule in raw_rules:
            if isinstance(rule, dict) and {"field", "operator", "value", "action"}.issubset(rule.keys()):
                # Already structured rule — skip LLM call completely
                compiled.append(rule)
            elif isinstance(rule, str):
                # Plain English string rule — compile via Policy Agent
                compiled.append(compile_rule(rule))
            elif isinstance(rule, dict) and ("natural_language" in rule or "rule" in rule):
                # Plain English wrapped in dict
                text = str(rule.get("natural_language") or rule.get("rule"))
                compiled.append(compile_rule(text))
            else:
                # Fallback or unknown format, keep as is
                compiled.append(rule)
        return compiled

    def check(
        self,
        agent_action: dict[str, Any],
        agent_reasoning: str | None = None,
        drift_action: str | None = None,
    ) -> Decision:
        """Evaluate an agent's proposed action against policies and stated reasoning.

        FAIL-CLOSED CONTRACT:
        ---------------------
        If any internal component throws an unhandled exception (e.g. malformed
        action, Groq API outage, network timeout), this method catches it and
        returns a BLOCK decision. An action is NEVER allowed if evaluation fails.

        Args:
            agent_action: The proposed agent tool/action dictionary.
            agent_reasoning: Optional natural language reasoning behind the action.
            drift_action: Optional override for status on detected drift ("BLOCK" or "ESCALATE").

        Returns:
            Decision: The final ALLOW, BLOCK, or ESCALATE decision.
        """
        try:
            # 1. Deterministic Interceptor check
            decision = _check(agent_action, self.policy)

            # 2. Optional Drift Agent check if reasoning is supplied and action wasn't blocked
            if decision.status == "ALLOW" and agent_reasoning is not None:
                drift = check_drift(agent_reasoning, agent_action)
                if drift.drift_detected:
                    target_status = drift_action or self.drift_action
                    decision = Decision(
                        allowed=False,
                        status=target_status,
                        reason=f"Drift detected ({drift.tier}): {drift.explanation}",
                        triggered_rule={
                            "drift_score": drift.drift_score,
                            "explanation": drift.explanation,
                            "tier": drift.tier,
                        },
                    )

            # 3. Terminal output layer
            if self.verbose:
                render(decision, agent_action)

            return decision

        except Exception as exc:
            # Explicit Fail-Closed Guarantee
            block_decision = Decision(
                allowed=False,
                status="BLOCK",
                reason=f"Fail-closed: internal guard error ({type(exc).__name__}): {exc}",
                triggered_rule={
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            if self.verbose:
                try:
                    render(block_decision, agent_action)
                except Exception:
                    pass
            return block_decision
