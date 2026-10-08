"""examples/demo.py — Standalone Hackathon Live Demo for Warden SDK.

Demonstrates 3 deterministic guardrail scenarios:
1. Normal loan approval under threshold -> ALLOW (Green)
2. Loan approval over threshold -> BLOCK (Red)
3. Action/reasoning mismatch -> ESCALATE via Drift Agent Tier 1 (Yellow)
"""

from pathlib import Path
from warden import Guard


def run_demo() -> None:
    policy_path = Path(__file__).parent / "rules.yaml"
    guard = Guard(policy_file=str(policy_path), drift_action="ESCALATE")

    print("\n" + "=" * 60)
    print("  WARDEN SDK -- LIVE GUARDRAIL DEMO")
    print("=" * 60 + "\n")

    # Scenario 1: Under threshold loan -> ALLOW
    print("[Scenario 1] Standard loan approval ($15,000 <= $50,000 limit)")
    d1 = guard.check(
        agent_action={"type": "loan_approval", "amount": 15000, "applicant_id": "app_4482"}
    )
    assert d1.allowed is True and d1.status == "ALLOW"

    # Scenario 2: Over threshold loan -> BLOCK
    print("\n[Scenario 2] Over-limit loan approval ($75,000 > $50,000 limit)")
    d2 = guard.check(
        agent_action={"type": "loan_approval", "amount": 75000, "applicant_id": "app_9910"}
    )
    assert d2.allowed is False and d2.status == "BLOCK"

    # Scenario 3: Stated reasoning mismatch -> ESCALATE via Drift Agent Tier 1
    print("\n[Scenario 3] Reasoning drift (agent executed refund while claiming loan check)")
    d3 = guard.check(
        agent_action={"tool": "approve_refund", "params": {"refund_id": "ref_881", "amount": 150.0}},
        agent_reasoning="Verified applicant employment history and debt-to-income ratio for loan underwriting.",
    )
    assert d3.allowed is False and d3.status == "ESCALATE"

    print("\n" + "-" * 60)
    print("SUCCESS: All 3 scenarios evaluated deterministically.")
    print("-" * 60 + "\n")


if __name__ == "__main__":
    run_demo()
