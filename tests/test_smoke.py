"""tests/test_smoke.py — Packaging smoke test."""

from pathlib import Path
from warden import Guard, Decision


def test_smoke_import_and_instantiate(tmp_path):
    """Smoke test ensuring package is importable and Guard instantiates cleanly."""
    policy_file = tmp_path / "smoke_policy.yaml"
    policy_file.write_text(
        """
- field: amount
  operator: ">"
  value: 1000
  action: block
  reason: Exceeds smoke test limit
""",
        encoding="utf-8",
    )

    # 1. Instantiate Guard with minimal test policy file
    guard = Guard(policy_file=str(policy_file), verbose=False)

    # 2. Check an action that passes
    pass_decision = guard.check({"type": "test_action", "amount": 500})
    assert isinstance(pass_decision, Decision)
    assert pass_decision.allowed is True
    assert pass_decision.status == "ALLOW"

    # 3. Check an action that blocks
    block_decision = guard.check({"type": "test_action", "amount": 1500})
    assert isinstance(block_decision, Decision)
    assert block_decision.allowed is False
    assert block_decision.status == "BLOCK"
