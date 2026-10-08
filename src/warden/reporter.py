"""warden.reporter — batch-aware terminal reporter for Warden decisions.

Wraps warden.check() with per-check Rich output and an end-of-batch summary.
The Interceptor (warden.interceptor) has no dependency on this module.

Caller responsibility: do not include secrets in action dicts;
values are printed to stdout.
"""

import json
import time
from datetime import datetime

from rich.console import Console
from rich.text import Text

from warden.interceptor import Decision
from warden.interceptor import check as _check

_STYLES = {
    "ALLOW":    "bold green",
    "BLOCK":    "bold red",
    "ESCALATE": "bold yellow",
}
_PAD = len("ESCALATE")  # align status column to widest label


def _action_summary(action: dict | None) -> str:
    """Compact single-line representation of *action*; never raises."""
    if not action:
        return ""
    try:
        return json.dumps(action, default=str)
    except Exception:
        return repr(action)


class Reporter:
    """Wraps ``check()`` with timing, Rich terminal output, and batch stats.

    Example::

        r = Reporter()
        decision = r.check(action, policy)
        r.summary()
    """

    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console(highlight=False)
        self._total = 0
        self._blocked = 0
        self._escalated = 0
        self._elapsed: list[float] = []  # seconds, measured per check

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, action: dict, policy: list[dict]) -> Decision:
        """Run ``check()``, print a formatted line, and return the Decision."""
        t0 = time.perf_counter()
        decision = _check(action, policy)
        elapsed = time.perf_counter() - t0

        self._total += 1
        self._elapsed.append(elapsed)
        if decision.status == "BLOCK":
            self._blocked += 1
        elif decision.status == "ESCALATE":
            self._escalated += 1

        self._print_line(decision, action, elapsed)
        return decision

    def summary(self) -> None:
        """Print one end-of-batch summary rule line."""
        avg_ms = (sum(self._elapsed) / len(self._elapsed) * 1000) if self._elapsed else 0.0
        self._console.rule(
            f"[bold]checked:[/bold] {self._total}  "
            f"[bold]blocked:[/bold] {self._blocked}  "
            f"[bold]escalated:[/bold] {self._escalated}  "
            f"[bold]avg:[/bold] {avg_ms:.3f}ms",
            style="dim",
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _print_line(self, decision: Decision, action: dict | None, elapsed: float) -> None:
        style = _STYLES.get(decision.status, "white")
        ts = datetime.now().strftime("%H:%M:%S")
        action_type = (action or {}).get("type", "unknown")
        summary = _action_summary(action)

        line = Text()
        line.append(f"[{ts}] ", style="dim")
        line.append(f"{decision.status:<{_PAD}}", style=style)
        line.append(f"  {action_type}  ")
        line.append(summary, style="dim")
        self._console.print(line)

        # Reason on indented line for non-ALLOW decisions
        if decision.status in ("BLOCK", "ESCALATE") and decision.reason:
            indent = " " * (len(ts) + 4)  # align below status
            self._console.print(f"{indent}{decision.reason}", style=style)
