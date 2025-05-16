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
    global bot_running

    # Setup dependencies early to get config for PID file path
    if not setup_dependencies():
        return

    pid_file = os.path.join(config.database_path, "bot.pid")

    # Check if already running
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            import psutil
            if psutil.pid_exists(pid) and any('main.py' in s and 'start' in s for s in psutil.Process(pid).cmdline()):
                console.print(f"[bold yellow]Bot is already running with PID {pid}.[/bold yellow]")
                return
            else:
                # Stale PID file
                console.print("[bold yellow]Warning: Stale PID file found. Removing.[/bold yellow]")
                os.remove(pid_file)
        except Exception as e:
            console.print(f"[bold red]Error checking existing PID file: {e}[/bold red]")
            if os.path.exists(pid_file): os.remove(pid_file)

    console.print("[bold green]Starting bot in background...[/bold green]")

    # Daemonization logic
    try:
        pid = os.fork()
        if pid > 0: # Parent process
            # Write PID file here in parent before it exits
            os.makedirs(os.path.dirname(pid_file), exist_ok=True)
            with open(pid_file, "w") as f:
                f.write(str(pid))
            console.print(f"[bold green]Bot process forked with PID {pid}. Parent exiting.[/bold green]")
            sys.exit(0) # Exit the parent process
    except OSError as e:
        console.print(f"[bold red]Fork failed: {e}[/bold red]")
        sys.exit(1)

    # Daemonization step 2: Decouple from parent environment
    os.setsid()

    # Daemonization step 3: Redirect standard file descriptors
    # It's often better to redirect to log files for debugging, but /dev/null for simplicity here
    # If you want logging, you'll need to configure handlers here.
    sys.stdout.flush()
    sys.stderr.flush()
    si = open(os.devnull, 'r')
    so = open(os.devnull, 'a+')
    se = open(os.devnull, 'a+')
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

    # Now we are in the detached child process. Re-setup dependencies as global state is lost.
    # Note: Global state (like config, wallet_tracker) is not preserved across fork.
    # We need to re-initialize everything here.
    # However, setup_dependencies already handles this. We just need to ensure the globals are updated.
    # setup_dependencies() # Not strictly needed here as the logic below implicitly uses the initialized objects.

    # The actual bot logic that runs in the background process
    bot_running = True # This global is now relevant for the daemon child process

    if not setup_dependencies():
        # If setup fails in the daemon child, log the error and exit
        logger.error("Failed to setup dependencies in daemon process.")
        sys.exit(1)

    try:
        wallets = wallet_tracker.get_tracked_wallets()

        if not wallets:
            logger.warning("Warning: No wallets are being tracked. Bot starting but idle.")

        # Show startup information in logs (stdout redirected)
        logger.info(f"Starting PumpFun Bot in {config.trading_mode.upper()} mode")
        logger.info(f"Tracking {len(wallets)} wallets")
        logger.info(f"Maximum SOL per trade: {config.max_sol_per_trade}")

        if config.trading_mode == "real":
            logger.warning(f"⚠️ WARNING: Running in REAL trading mode. Actual SOL will be used!")

        # Start tracking wallets (this is the long-running part)
        # Progress bar won't work in daemon mode, remove it or handle differently
        # with Progress() as progress:
        #     task = progress.add_task("[cyan]Starting wallet tracker...", total=1)

        # Start wallet tracker with transaction callback
        # transaction_callback will need to be safe for daemon (no console output ideally)
        await wallet_tracker.start(transaction_callback)

        # progress.update(task, advance=1)

        logger.info("Bot started successfully! Daemon running.")

        # Keep the bot running until interrupted (by stop command sending signal)
        # The async event loop will keep this alive
        # We don't need an explicit while True loop with asyncio.sleep(1)
        # unless there's other periodic tasks. The wallet_tracker.start
        # likely manages the main event loop tasks.

        # The event loop is likely started by wallet_tracker.start or needs explicit running
        # If wallet_tracker.start is a blocking call, this is fine.
        # If it returns immediately and sets up tasks, we need to run the loop.
        # Assuming wallet_tracker.start runs the loop or keeps tasks running.

        # The existing KeyboardInterrupt handling is for foreground. Daemon stops via signal.
        # The stop command sends SIGTERM, which will raise asyncio.CancelledError
        # or similar, allowing clean shutdown if handled in wallet_tracker.stop or start.

        # The clean up for PID file should be in a signal handler or a final cleanup block.
        # Let's use atexit for cleanup on normal exit or signal.
        import atexit
        atexit.register(self._cleanup_pid_file, pid_file) # Pass pid_file to cleanup function

        # The cleanup in the original try/finally block for KeyboardInterrupt
        # is no longer needed for daemon mode, but keep it for potential foreground runs.
        # We need a separate cleanup function registered with atexit.

    except Exception as e:
        logger.error(f"Error in daemon bot process: {e}", exc_info=True)
        # Clean up PID file on unexpected errors too
        if os.path.exists(pid_file):
             os.remove(pid_file)
        sys.exit(1)

# Add this helper function within the cli.py file, outside of any class or command function
def _cleanup_pid_file(pid_file):
    """Helper function to remove PID file on exit"""
    if os.path.exists(pid_file):
        try:
            os.remove(pid_file)
            logger.info(f"Removed PID file: {pid_file}")
        except Exception as e:
            logger.error(f"Error removing PID file {pid_file}: {e}")


@cli.command("stop", help=CLI_DESC_STOP)
async def stop():
    """Stop the bot"""
    # Setup dependencies needed for accessing config and data directory
    if not setup_dependencies():
        return

    pid_file = os.path.join(config.database_path, "bot.pid")

    if not os.path.exists(pid_file):
        console.print("[bold yellow]Bot is not running (PID file not found).[/bold yellow]")
        return

    try:
        with open(pid_file, "r") as f:
            daemon_pid = int(f.read().strip())

        import psutil
        if psutil.pid_exists(daemon_pid):
            try:
                p = psutil.Process(daemon_pid)
                 # Add a check to make sure we are killing our bot process
                if any('main.py' in s and 'start' in s and '--daemon' in s for s in p.cmdline()):

                    console.print(f"[bold yellow]Stopping bot process with PID {daemon_pid}...[/bold yellow]")

                    # Send termination signal (SIGTERM)
                    p.terminate()

                    # Wait a bit for it to terminate gracefully
                    try:
                        p.wait(timeout=5)
                        console.print("[bold green]Bot stopped.[/bold green]")
                    except psutil.TimeoutExpired:
                        console.print("[bold yellow]Bot did not terminate gracefully, sending SIGKILL...[/bold yellow]")
                        p.kill()
                        console.print("[bold green]Bot stopped (killed).[/bold green]")

                    # Remove PID file after successful termination
                    if os.path.exists(pid_file):
                         os.remove(pid_file)

                else:
                    console.print(f"[bold yellow]Warning: PID file found ({pid_file}) points to a non-bot process (PID {daemon_pid}). Not stopping. Removing stale PID file.[/bold yellow]")
                    os.remove(pid_file)

            except psutil.NoSuchProcess:
                console.print(f"[bold yellow]Bot process with PID {daemon_pid} not found. Removing stale PID file.[/bold yellow]")
                if os.path.exists(pid_file):
                     os.remove(pid_file)
            except Exception as e:
                 console.print(f"[bold red]Error stopping bot process with PID {daemon_pid}: {e}[/bold red]")


    except Exception as e:
        console.print(f"[bold red]Error reading PID file: {e}[/bold red]")


@cli.command("status", help=CLI_DESC_STATUS)
def status():
    """Show bot status"""
    # Setup dependencies needed for accessing config and data directory
    if not setup_dependencies():
        return

    pid_file = os.path.join(config.database_path, "bot.pid")
    is_daemon_running = False
    daemon_pid = None

    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                daemon_pid = int(f.read().strip())

            # Check if the process with this PID is running
            # This is a basic check and might not work perfectly on all systems
            import psutil
            if psutil.pid_exists(daemon_pid):
                 # Check if the process name looks like our bot
                 try:
                     p = psutil.Process(daemon_pid)
                     # Check if command line contains 'main.py start'
                     if any('main.py' in s and 'start' in s for s in p.cmdline()):
                         is_daemon_running = True
                     else:
                          # PID file exists, but it's not our bot process
                          console.print(f"[bold yellow]Warning: Stale PID file found ({pid_file}) pointing to a non-bot process. Removing.[/bold yellow]")
                          os.remove(pid_file)
                          daemon_pid = None # Clear stale PID
                 except psutil.NoSuchProcess:
                     is_daemon_running = False # Process died between check and access
                 except Exception as e:
                      console.print(f"[bold red]Error checking process details for PID {daemon_pid}: {e}[/bold red]")
                      is_daemon_running = False

            else:
                # PID file exists, but process is not running (stale PID)
                console.print(f"[bold yellow]Warning: Stale PID file found ({pid_file}). Removing.[/bold yellow]")
                os.remove(pid_file)
                daemon_pid = None # Clear stale PID

        except Exception as e:
            console.print(f"[bold red]Error reading or processing PID file: {e}[/bold red]")
            daemon_pid = None

    try:
        # Determine overall running status
        # The bot_running global is only true if running in the foreground in this terminal
        # If daemon is running, we rely on the PID file check
        overall_running_status = is_daemon_running # Assuming foreground run isn't typical when daemon exists

        wallets = wallet_tracker.get_tracked_wallets() if wallet_tracker else []

        # Create status panel
        status_text = f"""[bold white]Running:[/bold white] {'Yes (PID: {daemon_pid})' if is_daemon_running else 'No'}
[bold white]Trading Mode:[/bold white] {config.trading_mode.upper() if config else 'N/A'}
[bold white]Tracked Wallets:[/bold white] {len(wallets)}
[bold white]Max SOL per Trade:[/bold white] {config.max_sol_per_trade if config else 'N/A'}
[bold white]Web Interface:[/bold white] {'Running' if web_server_process else 'Not running'}"""

        status_panel = Panel(
            status_text,
            title="Bot Status",
            border_style="green" if overall_running_status else "yellow"
        )
        console.print(status_panel)

        # If bot is running (either foreground or daemon), show more details
        if overall_running_status:
            # Note: Accessing trade_store directly might only work in the foreground process
            # For daemon, you'd need a separate mechanism (e.g., API call) to get live trades
            console.print("[bold yellow]Note: Live trade data in status command is only available when running in the foreground.[/bold yellow]")
            # The existing code to show recent trades below this will only work
            # if the script is NOT run as a daemon process and bot_running is True
            pass # We won't try to show live trades here for the daemon case


    except Exception as e:
        console.print(f"[bold red]Error showing status: {e}[/bold red]")


@cli.command("web", help=CLI_DESC_WEB)
@click.option("--host", default="127.0.0.1", help="Host to bind the server to")
@click.option("--port", default=5000, type=int, help="Port to bind the server to")
def web(host: str, port: int):
    """Start the web interface"""
    global web_server_process
    
    if web_server_process:
        console.print("[bold yellow]Web interface is already running.[/bold yellow]")
        return
        
    if not setup_dependencies():
        return
    
    try:
        console.print(f"[bold green]Starting web interface on http://{host}:{port}[/bold green]")
        
        web_server_process = start_web_server(host, port, config, trade_store)
        
        console.print(f"[bold green]Web interface started. Press Ctrl+C to stop.[/bold green]")
        
        try:
            # Keep the process running until interrupted
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Stopping web interface...[/bold yellow]")
            if web_server_process:
                web_server_process.terminate()
                web_server_process = None
            console.print("[bold green]Web interface stopped.[/bold green]")
        
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