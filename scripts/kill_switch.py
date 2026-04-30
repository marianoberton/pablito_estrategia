"""
Kill switch CLI. Layer 2 of 4.
Usage: python scripts/kill_switch.py off
       python scripts/kill_switch.py status
"""
import sys
from dotenv import load_dotenv
load_dotenv()

import click
from rich.console import Console
console = Console()


@click.command()
@click.argument("action", type=click.Choice(["off", "on", "status"]))
def main(action):
    from src.risk.kill_switch import kill, is_enabled
    from src.db.client import get_db

    if action == "off":
        kill("cli_kill_switch")
        console.print("[bold red]Bot disabled.[/bold red]")
    elif action == "on":
        get_db().table("bot_config").update({"enabled": True}).eq("id", 1).execute()
        console.print("[bold green]Bot enabled.[/bold green]")
    elif action == "status":
        enabled = is_enabled()
        status = "[green]ENABLED[/green]" if enabled else "[red]DISABLED[/red]"
        console.print(f"Bot status: {status}")


if __name__ == "__main__":
    main()
