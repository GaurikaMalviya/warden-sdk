"""warden.output — Rich terminal rendering for Warden decisions.

Caller responsibility: do not include secrets in action dicts;
they will be printed to stdout.
"""

import json
from rich.console import Console
from rich.panel import Panel
from warden.interceptor import Decision

_CONSOLE = Console()

_STYLES = {
    "ALLOW":    "bold green",
    "BLOCK":    "bold red",
    "ESCALATE": "bold yellow",
}


def _serialize(value: object) -> str:
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return repr(value)


def render(decision: Decision, action: dict | None = None) -> Decision:
    """Print a color-coded Rich panel for *decision* and return it unchanged."""
    lines = [f"[bold]Reason[/bold]   {decision.reason}"]

    if decision.triggered_rule is not None:
        r = decision.triggered_rule
        if "field" in r:
            lines.append(
                f"[bold]Rule[/bold]     field={r.get('field')}  "
                f"operator={r.get('operator')}  value={r.get('value')}"
            )
        elif "drift_score" in r:
            lines.append(
                f"[bold]Drift[/bold]    tier={r.get('tier')}  drift_score={r.get('drift_score')}"
            )
        elif "error" in r:
            lines.append(f"[bold]Error[/bold]    {r.get('error')}")

    if action is not None:
        lines.append(f"[bold]Action[/bold]   {_serialize(action)}")

    style = _STYLES.get(decision.status, "white")
    _CONSOLE.print(Panel("\n".join(lines), title=decision.status, style=style))
    return decision
