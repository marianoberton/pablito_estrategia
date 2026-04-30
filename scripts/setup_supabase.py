"""
Applies the Supabase schema (schema.sql) to the configured project.
Run once during Phase 0 setup.
Usage: python scripts/setup_supabase.py
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import httpx
from rich.console import Console

console = Console()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

SCHEMA_PATH = Path(__file__).parent.parent / "src" / "db" / "schema.sql"


def run():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        console.print("[red]Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env[/red]")
        sys.exit(1)

    sql = SCHEMA_PATH.read_text()
    console.print(f"[cyan]Applying schema from {SCHEMA_PATH}...[/cyan]")

    # Split into individual statements (rough split by semicolon + newline)
    statements = [s.strip() for s in sql.split(";") if s.strip()]

    url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }

    # Supabase doesn't expose a direct SQL exec endpoint via REST by default.
    # Use the pg meta endpoint or connect via psycopg2/asyncpg.
    # For simplicity, print instructions to paste in Supabase SQL editor.
    console.print("\n[yellow]Supabase doesn't expose a direct SQL execution REST endpoint.[/yellow]")
    console.print("[yellow]Please apply the schema manually in one of two ways:[/yellow]\n")
    console.print("  Option 1 — Supabase Dashboard SQL editor:")
    console.print(f"    1. Open: {SUPABASE_URL.replace('https://', 'https://app.supabase.com/project/')}")
    console.print("    2. Go to SQL Editor")
    console.print(f"    3. Paste contents of: {SCHEMA_PATH}")
    console.print("    4. Click Run\n")
    console.print("  Option 2 — psql direct connection:")
    console.print("    psql $DATABASE_URL -f src/db/schema.sql\n")

    # Verify tables exist after manual application
    console.print("[cyan]After applying, run this script again with --verify to check tables.[/cyan]")

    if "--verify" in sys.argv:
        _verify()


def _verify():
    from supabase import create_client
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    required_tables = [
        "bot_config", "markets", "chainlink_btc_feed", "binance_btc_feed",
        "orderbook_snapshots", "polymarket_trades", "market_features",
        "bot_decisions", "bot_executions", "bot_logs",
    ]

    console.print("\n[cyan]Verifying tables...[/cyan]")
    all_ok = True
    for table in required_tables:
        try:
            db.table(table).select("*").limit(1).execute()
            console.print(f"  [green]✓[/green] {table}")
        except Exception as e:
            console.print(f"  [red]✗[/red] {table}: {e}")
            all_ok = False

    if all_ok:
        console.print("\n[bold green]✓ All tables verified. Schema applied successfully.[/bold green]")
    else:
        console.print("\n[bold red]✗ Some tables missing. Apply schema first.[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    run()
