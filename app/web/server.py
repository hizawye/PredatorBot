"""
Web server for PumpFun Bot - Provides a simple dashboard and API endpoints
"""

import json
import logging
import multiprocessing
import time
from datetime import datetime
from typing import Dict, List, Optional

from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS

from ..data.trade_store import TradeStore
from ..utils.config import Config
from ..utils.constants import WEB_API_PREFIX
from ..core.wallet_tracker import WalletTracker

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# Global references
trade_store: Optional[TradeStore] = None
config: Optional[Config] = None
wallet_tracker = None


@app.route("/")
def index():
    """Render the main dashboard page"""
    return render_template("index.html")


@app.route("/static/<path:path>")
def serve_static(path):
    """Serve static files"""
    return send_from_directory(app.static_folder, path)


@app.route(f"{WEB_API_PREFIX}/status", methods=["GET"])
def api_status():
    """API endpoint for bot status"""
    if not config or not trade_store:
        return jsonify({"error": "Bot not properly configured"}), 500

    try:
        pnl_stats = trade_store.calculate_pnl()

        return jsonify(
            {
                "status": "ok",
                "config": {
                    "trading_mode": config.trading_mode,
                    "max_sol_per_trade": config.max_sol_per_trade,
                },
                "stats": pnl_stats,
                "last_update": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route(f"{WEB_API_PREFIX}/trades/wallet", methods=["GET"])
def api_wallet_trades():
    """API endpoint for wallet trades"""
    if not trade_store:
        return jsonify({"error": "Trade store not initialized"}), 500

    try:
        wallet = request.args.get("wallet")
        limit = int(request.args.get("limit", 100))

        trades = trade_store.get_wallet_trades(wallet_address=wallet, limit=limit)
        return jsonify(trades)
    except Exception as e:
        logger.error(f"Error getting wallet trades: {e}")
        return jsonify({"error": str(e)}), 500


@app.route(f"{WEB_API_PREFIX}/trades/bot", methods=["GET"])
def api_bot_trades():
    """API endpoint for bot trades"""
    if not trade_store:
        return jsonify({"error": "Trade store not initialized"}), 500

    try:
        token = request.args.get("token")
        status = request.args.get("status")
        limit = int(request.args.get("limit", 100))

        trades = trade_store.get_bot_trades(
            token_address=token, status=status, limit=limit
        )
        return jsonify(trades)
    except Exception as e:
        logger.error(f"Error getting bot trades: {e}")
        return jsonify({"error": str(e)}), 500


@app.route(f"{WEB_API_PREFIX}/tokens", methods=["GET"])
def api_tokens():
    """API endpoint for token statistics"""
    if not trade_store:
        return jsonify({"error": "Trade store not initialized"}), 500

    try:
        token_stats = trade_store.get_token_stats()
        return jsonify(token_stats)
    except Exception as e:
        logger.error(f"Error getting token stats: {e}")
        return jsonify({"error": str(e)}), 500


@app.route(f"{WEB_API_PREFIX}/wallets/add", methods=["POST"])
def api_add_wallet():
    """API endpoint to add a tracked wallet"""
    global wallet_tracker # Need to access the global wallet_tracker instance

    if not wallet_tracker:
        return jsonify({"error": "Wallet tracker not initialized"}), 500

    try:
        data = request.get_json()
        wallet_address = data.get("wallet_address")

        if not wallet_address:
            return jsonify({"error": "Missing wallet_address in request"}), 400

        # Basic validation (can add more robust validation here)
        if len(wallet_address) != 44 or not wallet_address.isalnum():
             return jsonify({"error": "Invalid wallet address format."}), 400

        wallet_tracker.add_wallet(wallet_address)

        return jsonify({"status": "success", "message": f"Added wallet: {wallet_address}"}), 200
    except Exception as e:
        logger.error(f"Error adding wallet via API: {e}")
        return jsonify({"error": str(e)}), 500


@app.route(f"{WEB_API_PREFIX}/wallets", methods=["GET"])
def api_tracked_wallets():
    """API endpoint for tracked wallets and tracking status"""
    if not config or not trade_store:
        return jsonify({"error": "Bot not properly configured"}), 500

    try:
        # Load tracked wallets from file (same as WalletTracker)
        import os, json
        tracked_wallets_file = os.path.join(config.database_path, "tracked_wallets.json")
        tracked_wallets = []
        if os.path.exists(tracked_wallets_file):
            with open(tracked_wallets_file, "r") as f:
                tracked_wallets = json.load(f)

        # You can add more status info here if needed
        return jsonify({
            "tracked_wallets": tracked_wallets,
            "tracking_count": len(tracked_wallets),
            # Optionally add more status info here
        })
    except Exception as e:
        logger.error(f"Error getting tracked wallets: {e}")
        return jsonify({"error": str(e)}), 500


def web_server_process(host: str, port: int, config_dict: Dict, trade_store_path: str):
    """Function to run in a separate process for the web server"""
    try:
        global config, trade_store, wallet_tracker

        # Recreate config from dict
        config = Config(**config_dict)

        # Initialize data store
        trade_store = TradeStore(trade_store_path)

        # Initialize wallet tracker in the web process
        wallet_tracker = WalletTracker(config)

        # Start the web server
        app.run(host=host, port=port, debug=False)
    except Exception as e:
        logger.error(f"Error in web server process: {e}")


def start_web_server(
    host: str, port: int, bot_config: Config, bot_trade_store: TradeStore
):
    """
    Start the web server in a separate process

    Args:
        host: Host to bind to
        port: Port to bind to
        bot_config: Bot configuration
        bot_trade_store: Trade store instance

    Returns:
        multiprocessing.Process: Process running the web server
    """
    # Convert config to dict for passing to the process
    config_dict = {
        "quicknode_rpc_url": bot_config.quicknode_rpc_url,
        "quicknode_wss_url": bot_config.quicknode_wss_url,
        "wallet_private_key": None,  # Don't pass private key to web process
        "database_path": bot_config.database_path,
        "trading_mode": bot_config.trading_mode,
        "max_sol_per_trade": bot_config.max_sol_per_trade,
        "slippage_tolerance": bot_config.slippage_tolerance,
    }

    # Start web server in a separate process
    process = multiprocessing.Process(
        target=web_server_process,
        args=(host, port, config_dict, bot_config.database_path),
    )

    process.start()
    logger.info(f"Web server started on http://{host}:{port}")

    return process
