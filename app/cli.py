"""
Command-line interface for PumpFun Bot
"""
import asyncio
import logging
import sys
import time
import os
from datetime import datetime
from typing import List, Optional

import asyncclick as click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

from .core.wallet_tracker import WalletTracker
from .core.trade_executor import TradeExecutor
from .data.trade_store import TradeStore
from .utils.config import Config
from .utils.constants import (
    CLI_DESC_ADD_WALLET, CLI_DESC_REMOVE_WALLET, CLI_DESC_LIST_WALLETS,
    CLI_DESC_SET_MODE, CLI_DESC_SHOW_PNL, CLI_DESC_SHOW_TRADES,
    CLI_DESC_START, CLI_DESC_STOP, CLI_DESC_STATUS, CLI_DESC_WEB
)
from .web.server import start_web_server
from .utils.process_manager import ProcessManager

# Set up rich console
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, console=console)]
)
logger = logging.getLogger("pumpfun_bot")

# Global state
config = None
wallet_tracker = None
trade_store = None
trade_executor = None
bot_running = False
web_server_process = None

def setup_dependencies():
    """Setup application dependencies"""
    global config, wallet_tracker, trade_store, trade_executor
    
    try:
        # Load configuration
        config = Config.from_env()
        
        # Initialize data store
        trade_store = TradeStore(config.database_path)
        
        # Initialize components
        wallet_tracker = WalletTracker(config)
        trade_executor = TradeExecutor(config, trade_store)
        
        return True
    
    except Exception as e:
        console.print(f"[bold red]Error setting up dependencies: {e}[/bold red]")
        return False


async def transaction_callback(wallet: str, tx_signature: str, tx_data):
    """Callback for processing tracked wallet transactions"""
    try:
        # Process the transaction
        console.print(f"[bold yellow]Detected transaction from wallet: {wallet}[/bold yellow]")
        
        # Execute trade based on the transaction
        result = await trade_executor.process_trade(wallet, tx_signature, tx_data)
        
        if result:
            console.print("[bold green]Successfully copied trade![/bold green]")
        else:
            console.print("[bold red]Failed to copy trade.[/bold red]")
    
    except Exception as e:
        console.print(f"[bold red]Error in transaction callback: {e}[/bold red]")


@click.group()
def cli():
    """PumpFun Bot - Solana Memecoin Copy-Trading CLI"""
    pass


@cli.command("add-wallet", help=CLI_DESC_ADD_WALLET)
@click.argument("wallet_address")
def add_wallet(wallet_address: str):
    """Add a wallet address to track"""
    if not setup_dependencies():
        return
        
    # Validate wallet address format (basic check)
    if len(wallet_address) != 44 or not wallet_address.isalnum():
        console.print("[bold red]Invalid wallet address format. Should be a Solana address.[/bold red]")
        return
    
    try:
        # Add to tracked wallets
        wallet_tracker.add_wallet(wallet_address)
        console.print(f"[bold green]Added wallet to tracking: {wallet_address}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error adding wallet: {e}[/bold red]")


@cli.command("remove-wallet", help=CLI_DESC_REMOVE_WALLET)
@click.argument("wallet_address")
def remove_wallet(wallet_address: str):
    """Remove a wallet address from tracking"""
    if not setup_dependencies():
        return
    
    try:
        wallet_tracker.remove_wallet(wallet_address)
        console.print(f"[bold green]Removed wallet from tracking: {wallet_address}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error removing wallet: {e}[/bold red]")


@cli.command("list-wallets", help=CLI_DESC_LIST_WALLETS)
def list_wallets():
    """List all tracked wallet addresses"""
    if not setup_dependencies():
        return
    
    try:
        wallets = wallet_tracker.get_tracked_wallets()
        
        if not wallets:
            console.print("[yellow]No wallets are currently being tracked.[/yellow]")
            return
            
        table = Table(title="Tracked Wallets")
        table.add_column("Wallet Address", style="cyan")
        
        for wallet in wallets:
            table.add_row(wallet)
            
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Error listing wallets: {e}[/bold red]")


@cli.command("set-mode", help=CLI_DESC_SET_MODE)
@click.argument("mode", type=click.Choice(["paper", "real"]))
def set_mode(mode: str):
    """Set trading mode (paper/real)"""
    if not setup_dependencies():
        return
    
    try:
        # For a real implementation, this would update the configuration file
        console.print(f"[bold yellow]Note: This is changing mode for the current session only.[/bold yellow]")
        console.print(f"[bold yellow]To permanently change mode, edit your .env file.[/bold yellow]")
        
        # Update config object for current session
        config.trading_mode = mode
        
        # Recreate trade executor with new config
        global trade_executor
        trade_executor = TradeExecutor(config, trade_store)
        
        console.print(f"[bold green]Trading mode set to: {mode}[/bold green]")
        
        # Warning for real mode
        if mode == "real":
            console.print(f"[bold red]⚠️ WARNING: Real trading mode will use actual SOL funds![/bold red]")
            
            if not config.wallet_private_key:
                console.print(f"[bold red]No wallet private key configured for real trading.[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Error setting mode: {e}[/bold red]")


@cli.command("show-pnl", help=CLI_DESC_SHOW_PNL)
def show_pnl():
    """Show profit/loss statistics"""
    if not setup_dependencies():
        return
    
    try:
        pnl_stats = trade_store.calculate_pnl()
        token_stats = trade_store.get_token_stats()
        
        # Overall PnL panel
        pnl_panel = Panel(
            f"[bold white]Total PnL:[/bold white] [{'green' if pnl_stats['total_pnl'] >= 0 else 'red'}]{pnl_stats['total_pnl']:.4f} SOL[/]\n"
            f"[bold white]Trade Count:[/bold white] {pnl_stats['trade_count']}\n"
            f"[bold white]Win/Loss:[/bold white] {pnl_stats['win_count']}/{pnl_stats['loss_count']}\n"
            f"[bold white]Win Rate:[/bold white] {pnl_stats['win_rate']:.2f}%",
            title="Overall Performance",
            border_style="blue"
        )
        console.print(pnl_panel)
        
        # Token performance table
        if token_stats:
            table = Table(title="Token Performance")
            table.add_column("Token", style="cyan")
            table.add_column("Trades", style="magenta")
            table.add_column("Volume (SOL)", style="yellow")
            table.add_column("PnL (SOL)", style="green")
            
            for token in sorted(token_stats, key=lambda x: x["pnl"], reverse=True):
                pnl_color = "green" if token["pnl"] >= 0 else "red"
                table.add_row(
                    token["name"],
                    str(token["trade_count"]),
                    f"{token['total_amount']:.4f}",
                    f"[{pnl_color}]{token['pnl']:.4f}[/]"
                )
                
            console.print(table)
        else:
            console.print("[yellow]No token data available yet.[/yellow]")
            
    except Exception as e:
        console.print(f"[bold red]Error showing PnL: {e}[/bold red]")


@cli.command("show-trades", help=CLI_DESC_SHOW_TRADES)
@click.option("--wallet", "-w", help="Filter by wallet address")
@click.option("--token", "-t", help="Filter by token address")
@click.option("--limit", "-l", type=int, default=10, help="Number of trades to show")
def show_trades(wallet: Optional[str], token: Optional[str], limit: int):
    """Show trade history"""
    if not setup_dependencies():
        return
    
    try:
        # Get wallet trades
        if wallet:
            wallet_trades = trade_store.get_wallet_trades(wallet_address=wallet, limit=limit)
            console.print(f"[bold cyan]Showing trades for wallet: {wallet}[/bold cyan]")
        else:
            wallet_trades = trade_store.get_wallet_trades(limit=limit)
            console.print(f"[bold cyan]Showing recent wallet trades:[/bold cyan]")
            
        if wallet_trades:
            table = Table(title="Tracked Wallet Trades")
            table.add_column("Date", style="cyan")
            table.add_column("Wallet", style="blue")
            table.add_column("Type", style="magenta")
            table.add_column("Token", style="yellow")
            table.add_column("Amount (SOL)", style="green")
            
            for trade in wallet_trades:
                trade_type_color = "green" if trade["trade_type"] == "buy" else "red"
                trade_date = datetime.fromtimestamp(trade["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
                
                table.add_row(
                    trade_date,
                    trade["wallet_address"][:8] + "...",
                    f"[{trade_type_color}]{trade['trade_type'].upper()}[/]",
                    trade["token_name"],
                    f"{trade['amount']:.4f}"
                )
                
            console.print(table)
        else:
            console.print("[yellow]No wallet trades found.[/yellow]")
            
        # Get bot trades
        console.print(f"[bold cyan]Showing bot trades:[/bold cyan]")
        bot_trades = trade_store.get_bot_trades(token_address=token, limit=limit)
        
        if bot_trades:
            table = Table(title="Bot Trades")
            table.add_column("Date", style="cyan")
            table.add_column("Type", style="magenta")
            table.add_column("Token", style="yellow")
            table.add_column("Amount (SOL)", style="green")
            table.add_column("Status", style="blue")
            table.add_column("PnL", style="white")
            
            for trade in bot_trades:
                trade_type_color = "green" if trade["trade_type"] == "buy" else "red"
                trade_date = datetime.fromtimestamp(trade["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
                
                # Determine status color
                status_color = {
                    "pending": "yellow",
                    "submitted": "blue",
                    "completed": "green",
                    "failed": "red"
                }.get(trade["status"], "white")
                
                # Format PnL if available
                pnl_text = "N/A"
                if trade.get("pnl") is not None:
                    pnl_color = "green" if trade["pnl"] >= 0 else "red"
                    pnl_text = f"[{pnl_color}]{trade['pnl']:.4f}[/]"
                
                table.add_row(
                    trade_date,
                    f"[{trade_type_color}]{trade['trade_type'].upper()}[/]",
                    trade["token_name"],
                    f"{trade['amount']:.4f}",
                    f"[{status_color}]{trade['status'].upper()}[/]",
                    pnl_text
                )
                
            console.print(table)
        else:
            console.print("[yellow]No bot trades found.[/yellow]")
            
    except Exception as e:
        console.print(f"[bold red]Error showing trades: {e}[/bold red]")


@cli.command("start", help=CLI_DESC_START)
async def start():
    """Start the bot"""
    if not setup_dependencies():
        return

    process_manager = ProcessManager(config.database_path)
    
    # Check if already running
    cli_status = process_manager.get_process_status("bot_cli")
    if cli_status["running"]:
        console.print("[bold yellow]Bot is already running.[/bold yellow]")
        return

    try:
        # Fork the process
        pid = os.fork()
        if pid > 0:  # Parent process
            process_manager.register_process("bot_cli", pid)
            console.print(f"[bold green]Bot started in background (PID: {pid})[/bold green]")
            return
        else:  # Child process
            # Decouple from parent
            os.setsid()
            
            # Close file descriptors
            os.close(0)
            os.close(1)
            os.close(2)
            
            # Start the bot
            await wallet_tracker.start(transaction_callback)
            
            # Keep the process running
            while True:
                await asyncio.sleep(1)
                
    except Exception as e:
        console.print(f"[bold red]Error starting bot: {e}[/bold red]")


@cli.command("stop", help=CLI_DESC_STOP)
def stop():
    """Stop the bot and web interface"""
    if not setup_dependencies():
        return

    process_manager = ProcessManager(config.database_path)
    
    # Stop CLI process
    cli_status = process_manager.get_process_status("bot_cli")
    if cli_status["running"]:
        if process_manager.stop_process("bot_cli"):
            console.print("[bold green]Bot stopped successfully.[/bold green]")
        else:
            console.print("[bold red]Failed to stop bot.[/bold red]")
    else:
        console.print("[bold yellow]Bot is not running.[/bold yellow]")

    # Stop web process
    web_status = process_manager.get_process_status("bot_web")
    if web_status["running"]:
        if process_manager.stop_process("bot_web"):
            console.print("[bold green]Web interface stopped successfully.[/bold green]")
        else:
            console.print("[bold red]Failed to stop web interface.[/bold red]")
    else:
        console.print("[bold yellow]Web interface is not running.[/bold yellow]")


@cli.command("status", help=CLI_DESC_STATUS)
def status():
    """Show bot status"""
    if not setup_dependencies():
        return

    process_manager = ProcessManager(config.database_path)
    
    # Get status for both CLI and web processes
    cli_status = process_manager.get_process_status("bot_cli")
    web_status = process_manager.get_process_status("bot_web")

    # Create status table
    table = Table(title="PredatorBot Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("PID", style="blue")
    table.add_column("CPU %", style="yellow")
    table.add_column("Memory %", style="magenta")
    table.add_column("Uptime", style="white")

    # Add CLI status
    cli_row = ["Bot CLI"]
    if cli_status["running"]:
        uptime = datetime.now().timestamp() - cli_status["created"]
        cli_row.extend([
            "[green]Running[/green]",
            str(cli_status["pid"]),
            f"{cli_status['cpu_percent']:.1f}%",
            f"{cli_status['memory_percent']:.1f}%",
            f"{int(uptime/3600)}h {int((uptime%3600)/60)}m"
        ])
    else:
        cli_row.extend(["[red]Stopped[/red]", "-", "-", "-", "-"])
    table.add_row(*cli_row)

    # Add Web status
    web_row = ["Web Interface"]
    if web_status["running"]:
        uptime = datetime.now().timestamp() - web_status["created"]
        web_row.extend([
            "[green]Running[/green]",
            str(web_status["pid"]),
            f"{web_status['cpu_percent']:.1f}%",
            f"{web_status['memory_percent']:.1f}%",
            f"{int(uptime/3600)}h {int((uptime%3600)/60)}m"
        ])
    else:
        web_row.extend(["[red]Stopped[/red]", "-", "-", "-", "-"])
    table.add_row(*web_row)

    console.print(table)

    # Show additional info
    if cli_status["running"]:
        wallets = wallet_tracker.get_tracked_wallets()
        console.print(f"\n[bold]Trading Mode:[/bold] {config.trading_mode.upper()}")
        console.print(f"[bold]Tracked Wallets:[/bold] {len(wallets)}")
        console.print(f"[bold]Max SOL per Trade:[/bold] {config.max_sol_per_trade}")


@cli.command("web", help=CLI_DESC_WEB)
@click.option("--host", default="127.0.0.1", help="Host to bind the server to")
@click.option("--port", default=5000, type=int, help="Port to bind the server to")
def web(host: str, port: int):
    """Start the web interface"""
    if not setup_dependencies():
        return

    process_manager = ProcessManager(config.database_path)
    
    # Check if already running
    web_status = process_manager.get_process_status("bot_web")
    if web_status["running"]:
        console.print("[bold yellow]Web interface is already running.[/bold yellow]")
        return

    try:
        # Fork the process
        pid = os.fork()
        if pid > 0:  # Parent process
            process_manager.register_process("bot_web", pid)
            console.print(f"[bold green]Web interface started in background (PID: {pid})[/bold green]")
            console.print(f"Access the dashboard at http://{host}:{port}")
            return
        else:  # Child process
            # Decouple from parent
            os.setsid()
            
            # Close file descriptors
            os.close(0)
            os.close(1)
            os.close(2)
            
            # Start the web server
            from .web.server import app
            app.run(host=host, port=port)
            
    except Exception as e:
        console.print(f"[bold red]Error starting web interface: {e}[/bold red]")
        

def main():
    """Entry point for the CLI application"""
    try:
        cli()
    except Exception as e:
        console.print(f"[bold red]Unhandled error: {e}[/bold red]")
        sys.exit(1)
        

if __name__ == "__main__":
    # Run the CLI
    main()