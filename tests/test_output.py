"""tests/test_output.py — pytest suite for warden.output.render."""

import json
from io import StringIO
from rich.console import Console
from warden.interceptor import Decision, check
from warden.output import render, _serialize


# ---------------------------------------------------------------------------
# Helper: capture render output
# ---------------------------------------------------------------------------

def _capture(decision, action=None) -> str:
    buf = StringIO()
    console = Console(file=buf, highlight=False)
    # Patch module-level console for this call
    import warden.output as mod
    original = mod._CONSOLE
    mod._CONSOLE = console
    try:
        result = render(decision, action)
    finally:
        mod._CONSOLE = original
    return buf.getvalue(), result


BLOCK_RULE = {
    "field": "amount", "operator": ">", "value": 50_000,
    "action": "block", "reason": "Exceeds threshold, requires co-signer review.",
}
ESCALATE_RULE = {
    "field": "amount", "operator": ">", "value": 50_000,
    "action": "escalate", "reason": "Requires senior-underwriter approval.",
}


# ---------------------------------------------------------------------------
# Panel content
# ---------------------------------------------------------------------------

class TestPanelContent:
    def test_allow_shows_status_and_reason(self):
        d = check({"amount": 10_000}, [BLOCK_RULE])
        out, _ = _capture(d)
        assert "ALLOW" in out
        assert "No policy rule matched" in out

    def test_block_shows_status_reason_and_rule(self):
        d = check({"amount": 75_000}, [BLOCK_RULE])
        out, _ = _capture(d)
        assert "BLOCK" in out
        assert "co-signer" in out
        assert "amount" in out   # rule row
        assert "50000" in out

    def test_escalate_shows_rule_row(self):
        d = check({"amount": 75_000}, [ESCALATE_RULE])
        out, _ = _capture(d)
        assert "ESCALATE" in out
        assert "amount" in out

    def test_allow_has_no_rule_row(self):
        d = check({"amount": 10_000}, [BLOCK_RULE])
        out, _ = _capture(d)
        assert "field=" not in out


# ---------------------------------------------------------------------------
# Action row
# ---------------------------------------------------------------------------

class TestActionRow:
    def test_action_row_present_when_provided(self):
        d = check({"amount": 75_000}, [BLOCK_RULE])
        out, _ = _capture(d, action={"amount": 75_000})
        assert "75000" in out

    def test_action_row_absent_when_omitted(self):
        d = check({"amount": 75_000}, [BLOCK_RULE])
        out, _ = _capture(d)
        # Without action= kwarg the action line shouldn't appear
        assert "Action" not in out

    def test_unserializable_action_no_exception(self):
        class Unserializable:
            pass
        d = check({}, [])
        out, _ = _capture(d, action={"obj": Unserializable()})
        assert "Action" in out  # fell back to repr, no crash


# ---------------------------------------------------------------------------
# Return value
# ---------------------------------------------------------------------------

class TestReturnValue:
    def test_returns_same_decision_object(self):
        d = check({"amount": 75_000}, [BLOCK_RULE])
        _, returned = _capture(d)
        assert returned is d

    def test_decision_fields_unchanged(self):
        d = check({"amount": 75_000}, [BLOCK_RULE])
        _, returned = _capture(d, action={"amount": 75_000})
        assert returned.allowed is False
        assert returned.status == "BLOCK"
        assert returned.triggered_rule is BLOCK_RULE


# ---------------------------------------------------------------------------
# _serialize helper
# ---------------------------------------------------------------------------

class TestSerialize:
    def test_json_serializable(self):
        assert _serialize({"a": 1}) == json.dumps({"a": 1})

    def test_falls_back_to_repr(self):
        class X:
            def __repr__(self): return "<X>"
        result = _serialize(X())
        assert result == "<X>"
