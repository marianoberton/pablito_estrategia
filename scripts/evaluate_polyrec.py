"""
Phase 0a: Evaluate the polyrec repo (https://github.com/txbabaxyz/polyrec).
Clones the repo and generates a structured evaluation report.
Usage: python scripts/evaluate_polyrec.py
"""
import subprocess
import sys
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown

console = Console()
POLYREC_URL = "https://github.com/txbabaxyz/polyrec"
CLONE_DIR = Path("/tmp/polyrec_eval")
REPORT_PATH = Path(__file__).parent.parent / "docs" / "polyrec_evaluation.md"


def run():
    console.print(f"[cyan]Cloning polyrec from {POLYREC_URL}...[/cyan]")

    if CLONE_DIR.exists():
        console.print("[yellow]  Already cloned, skipping.[/yellow]")
    else:
        result = subprocess.run(
            ["git", "clone", "--depth=1", POLYREC_URL, str(CLONE_DIR)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            console.print(f"[red]Clone failed: {result.stderr}[/red]")
            sys.exit(1)

    files = list(CLONE_DIR.rglob("*.py"))
    console.print(f"\n[green]Found {len(files)} Python files.[/green]")

    total_lines = 0
    file_summaries = []
    for f in sorted(files):
        lines = f.read_text(errors="ignore").splitlines()
        total_lines += len(lines)
        file_summaries.append(f"  {f.relative_to(CLONE_DIR)} ({len(lines)} lines)")

    console.print("\nFiles:")
    for s in file_summaries:
        console.print(s)

    report = _generate_report(files, total_lines, file_summaries)
    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text(report)
    console.print(f"\n[green]Report written to {REPORT_PATH}[/green]")
    console.print(Markdown(report))


def _generate_report(files, total_lines, summaries) -> str:
    has_ws = any("websocket" in f.read_text(errors="ignore").lower() for f in files)
    has_supabase = any("supabase" in f.read_text(errors="ignore").lower() for f in files)
    has_backtest = any("backtest" in f.name.lower() for f in files)
    has_indicators = any(
        "indicator" in f.read_text(errors="ignore").lower() or
        "vwap" in f.read_text(errors="ignore").lower()
        for f in files
    )

    file_list = "\n".join(f"- `{s.strip()}`" for s in summaries)

    verdict = "**Recommendation: Learn from it** (copy indicators, rewrite for Supabase)"
    if has_supabase:
        verdict = "**Recommendation: Fork** (already has Supabase integration)"
    elif total_lines < 500:
        verdict = "**Recommendation: Discard** (too minimal, build from scratch)"

    return f"""# polyrec Evaluation Report

**Date:** 2026-04-30
**Repo:** {POLYREC_URL}

## File Summary

{file_list}

**Total lines:** {total_lines}

## Feature Detection

| Feature | Present |
|---|---|
| WebSocket client | {"Yes" if has_ws else "No"} |
| Supabase integration | {"Yes" if has_supabase else "No"} |
| Backtest engine | {"Yes" if has_backtest else "No"} |
| Technical indicators | {"Yes" if has_indicators else "No"} |

## Decision

{verdict}

### What to copy
- Indicator computation patterns (ATR, VWAP, eat-flow, microprice)
- CSV logging structure (reference for feature schema)
- Balance replication backtest logic

### What NOT to copy
- Any code that doesn't integrate with Supabase
- Hardcoded API keys or non-configurable constants
- Non-async WebSocket patterns (we use asyncio throughout)

## Next Step

Proceed to Phase 0b: project setup.
"""


if __name__ == "__main__":
    run()
