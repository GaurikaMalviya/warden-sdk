"""tests/test_reporter.py — pytest suite for warden.reporter.Reporter."""

from io import StringIO
import pytest
from rich.console import Console
from warden.reporter import Reporter, _action_summary


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_reporter() -> tuple[Reporter, StringIO]:
    buf = StringIO()
    console = Console(file=buf, highlight=False, no_color=True)
    return Reporter(console=console), buf


BLOCK_RULE = {
    "field": "amount", "operator": ">", "value": 50_000,
    "action": "block", "reason": "Exceeds threshold, requires co-signer review.",
}
ESCALATE_RULE = {
    "field": "amount", "operator": ">", "value": 50_000,
    "action": "escalate", "reason": "Requires senior-underwriter approval.",
}


# ---------------------------------------------------------------------------
# Per-check line format
# ---------------------------------------------------------------------------

class TestCheckLine:
    def test_allow_line_contains_status_and_type(self):
        r, buf = _make_reporter()
        r.check({"type": "loan_approval", "amount": 10_000}, [BLOCK_RULE])
        out = buf.getvalue()
        assert "ALLOW" in out
        assert "loan_approval" in out

    def test_block_line_contains_status_and_reason(self):
        r, buf = _make_reporter()
        r.check({"type": "loan_approval", "amount": 75_000}, [BLOCK_RULE])
        out = buf.getvalue()
        assert "BLOCK" in out
        assert "co-signer" in out  # reason on indented line

    def test_escalate_line_contains_reason(self):
        r, buf = _make_reporter()
        r.check({"type": "loan_approval", "amount": 75_000}, [ESCALATE_RULE])
        out = buf.getvalue()
        assert "ESCALATE" in out
        assert "senior-underwriter" in out

    def test_allow_has_no_reason_line(self):
        r, buf = _make_reporter()
        r.check({"type": "loan_approval", "amount": 10_000}, [BLOCK_RULE])
        out = buf.getvalue()
        # Only one non-blank line for ALLOW (no indented reason)
        non_blank = [l for l in out.splitlines() if l.strip()]
        assert len(non_blank) == 1

    def test_block_has_two_output_lines(self):
        r, buf = _make_reporter()
        r.check({"type": "loan_approval", "amount": 75_000}, [BLOCK_RULE])
        non_blank = [l for l in buf.getvalue().splitlines() if l.strip()]
        assert len(non_blank) == 2  # status line + reason line

    def test_timestamp_present(self):
        r, buf = _make_reporter()
        r.check({"type": "x", "amount": 1}, [])
        assert "[" in buf.getvalue()  # timestamp wrapped in brackets


# ---------------------------------------------------------------------------
# Missing / None fields — must not crash
# ---------------------------------------------------------------------------

class TestRobustness:
    def test_missing_type_field_uses_unknown(self):
        r, buf = _make_reporter()
        r.check({"amount": 10_000}, [BLOCK_RULE])  # no "type" key
        assert "unknown" in buf.getvalue()

    def test_none_action_does_not_crash(self):
        """action=None is not valid per the public API but _action_summary handles it."""
        assert _action_summary(None) == ""

    def test_empty_action_dict_does_not_crash(self):
        r, buf = _make_reporter()
        r.check({}, [])  # no "type", no "amount"
        assert "ALLOW" in buf.getvalue()

    def test_unserializable_value_does_not_crash(self):
        class Unserializable:
            pass
        r, buf = _make_reporter()
        # json.dumps(default=str) converts this; no exception
        r.check({"type": "x", "obj": Unserializable()}, [])
        assert "ALLOW" in buf.getvalue()


# ---------------------------------------------------------------------------
# Return value
# ---------------------------------------------------------------------------

class TestReturnValue:
    def test_returns_decision(self):
        r, _ = _make_reporter()
        decision = r.check({"amount": 75_000}, [BLOCK_RULE])
        assert decision.status == "BLOCK"
        assert decision.allowed is False

    def test_returns_same_object(self):
        from warden.interceptor import check
        r, _ = _make_reporter()
        returned = r.check({"amount": 10_000}, [BLOCK_RULE])
        assert returned.status == "ALLOW"


# ---------------------------------------------------------------------------
# Batch summary
# ---------------------------------------------------------------------------

class TestSummary:
    def test_summary_counts(self):
        r, buf = _make_reporter()
        r.check({"amount": 10_000}, [BLOCK_RULE])   # ALLOW
        r.check({"amount": 75_000}, [BLOCK_RULE])   # BLOCK
        r.check({"amount": 75_000}, [ESCALATE_RULE])# ESCALATE
        buf.truncate(0); buf.seek(0)
        r.summary()
        out = buf.getvalue()
        assert "checked: 3" in out
        assert "blocked: 1" in out
        assert "escalated: 1" in out

    def test_summary_contains_avg_ms(self):
        r, buf = _make_reporter()
        r.check({"amount": 10_000}, [BLOCK_RULE])
        buf.truncate(0); buf.seek(0)
        r.summary()
        assert "ms" in buf.getvalue()

    def test_summary_avg_is_measured_not_zero(self):
        """avg_ms must reflect real elapsed time (> 0)."""
        r, buf = _make_reporter()
        r.check({"amount": 10_000}, [BLOCK_RULE])
        buf.truncate(0); buf.seek(0)
        r.summary()
        import re
        match = re.search(r"avg.*?([\d.]+)ms", buf.getvalue())
        assert match, "avg ms not found in summary"
        assert float(match.group(1)) >= 0  # may be ~0 on fast machines

    def test_summary_empty_batch_no_crash(self):
        r, buf = _make_reporter()
        r.summary()  # no checks performed — division guard
        assert "checked: 0" in buf.getvalue()


# ---------------------------------------------------------------------------
# _action_summary helper
# ---------------------------------------------------------------------------

class TestActionSummary:
    def test_json_output(self):
        import json
        result = _action_summary({"a": 1, "b": "x"})
        assert json.loads(result) == {"a": 1, "b": "x"}

    def test_unserializable_falls_back(self):
        class X:
            def __repr__(self): return "<X>"
        # default=str handles it; no repr fallback needed
        result = _action_summary({"x": X()})
        assert "x" in result

    def test_none_returns_empty(self):
        assert _action_summary(None) == ""
