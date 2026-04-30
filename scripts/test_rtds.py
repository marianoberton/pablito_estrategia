"""
Phase 0 acceptance test: connects to Polymarket RTDS and reads 60 seconds
of Chainlink BTC/USD and Binance BTCUSDT ticks.
Run: python scripts/test_rtds.py
"""
import asyncio
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import websockets
from rich.console import Console
from rich.table import Table

console = Console()
RTDS_URL = "wss://ws-live-data.polymarket.com"
DURATION = 60


async def run():
    counts = defaultdict(int)
    last_prices = {}
    start = time.time()

    console.print(f"[bold green]Connecting to RTDS: {RTDS_URL}[/bold green]")

    async with websockets.connect(RTDS_URL, ping_interval=None) as ws:
        sub = {"type": "subscribe", "topics": ["crypto_prices_chainlink", "crypto_prices"]}
        await ws.send(json.dumps(sub))
        console.print("[cyan]Subscribed. Reading for 60 seconds...[/cyan]\n")

        ping_task = asyncio.create_task(_ping(ws))
        try:
            while time.time() - start < DURATION:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                except asyncio.TimeoutError:
                    continue

                msg = json.loads(raw)
                topic = msg.get("topic", "")
                data = msg.get("data", {})

                if topic == "crypto_prices_chainlink":
                    asset = data.get("asset", "")
                    if "btc" in asset.lower():
                        counts["chainlink"] += 1
                        last_prices["chainlink"] = data.get("price")

                elif topic == "crypto_prices":
                    asset = data.get("asset", "")
                    if "btc" in asset.lower():
                        counts["binance"] += 1
                        last_prices["binance"] = data.get("price")

                elapsed = int(time.time() - start)
                if elapsed % 10 == 0 and elapsed > 0:
                    console.print(
                        f"  t={elapsed}s | chainlink={counts['chainlink']} ticks "
                        f"(last: {last_prices.get('chainlink')}) | "
                        f"binance={counts['binance']} ticks "
                        f"(last: {last_prices.get('binance')})"
                    )
        finally:
            ping_task.cancel()

    _print_results(counts, last_prices)
    return counts


async def _ping(ws):
    while True:
        await asyncio.sleep(5)
        await ws.send(json.dumps({"type": "PING"}))


def _print_results(counts, last_prices):
    table = Table(title="RTDS Test Results (60 seconds)")
    table.add_column("Feed", style="cyan")
    table.add_column("Ticks received", style="magenta")
    table.add_column("Last price", style="green")
    table.add_column("Status", style="bold")

    cl_ok = counts["chainlink"] >= 30
    bn_ok = counts["binance"] >= 30

    table.add_row(
        "Chainlink BTC/USD",
        str(counts["chainlink"]),
        str(last_prices.get("chainlink", "N/A")),
        "[green]PASS[/green]" if cl_ok else "[red]FAIL[/red]",
    )
    table.add_row(
        "Binance BTCUSDT",
        str(counts["binance"]),
        str(last_prices.get("binance", "N/A")),
        "[green]PASS[/green]" if bn_ok else "[red]FAIL[/red]",
    )
    console.print(table)

    if cl_ok and bn_ok:
        console.print("\n[bold green]✓ RTDS connectivity OK — Phase 0 acceptance criterion met.[/bold green]")
    else:
        console.print("\n[bold red]✗ RTDS test FAILED. Check connection and topics.[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
