"""
Trade Store - Store and retrieve trade data from database
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Union, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class TradeStore:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.wallet_trades_file = self.data_dir / "wallet_trades.json"
        self.bot_trades_file = self.data_dir / "bot_trades.json"

        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)

        # Initialize data files if they don't exist
        self._initialize_database()

        # Load existing data
        self.wallet_trades = self._load_data(self.wallet_trades_file)
        self.bot_trades = self._load_data(self.bot_trades_file)

    def _initialize_database(self):
        """Initialize database files if they don't exist"""
        if not self.wallet_trades_file.exists():
            self._save_data(self.wallet_trades_file, [])

        if not self.bot_trades_file.exists():
            self._save_data(self.bot_trades_file, [])

    def _load_data(self, file_path: Path) -> List[Dict]:
        """Load data from JSON file"""
        try:
            if file_path.exists():
                with open(file_path, "r") as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Error loading data from {file_path}: {e}")
            return []

    def _save_data(self, file_path: Path, data: List[Dict]):
        """Save data to JSON file"""
        try:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving data to {file_path}: {e}")

    def add_wallet_trade(
        self,
        wallet_address: str,
        trade_type: str,
        token_address: str,
        token_name: str,
        amount: float,
        tx_signature: str,
        timestamp: float,
    ):
        """
        Add a tracked wallet's trade to the database

        Args:
            wallet_address: The wallet address that made the trade
            trade_type: Type of trade (buy or sell)
            token_address: Token address
            token_name: Token name
            amount: Amount of SOL in the trade
            tx_signature: Transaction signature
            timestamp: Unix timestamp of the trade
        """
        trade = {
            "id": f"wt_{int(timestamp * 1000)}_{wallet_address[:8]}",
            "wallet_address": wallet_address,
            "trade_type": trade_type,
            "token_address": token_address,
            "token_name": token_name,
            "amount": amount,
            "tx_signature": tx_signature,
            "timestamp": timestamp,
            "date": datetime.fromtimestamp(timestamp).isoformat(),
        }

        self.wallet_trades.append(trade)
        self._save_data(self.wallet_trades_file, self.wallet_trades)
        logger.debug(f"Added wallet trade: {trade['id']}")

    def add_bot_trade(
        self,
        trade_type: str,
        token_address: str,
        token_name: str,
        amount: float,
        tx_signature: str,
        timestamp: float,
        status: str = "pending",
    ) -> str:
        """
        Add a bot trade to the database

        Args:
            trade_type: Type of trade (buy or sell)
            token_address: Token address
            token_name: Token name
            amount: Amount of SOL in the trade
            tx_signature: Transaction signature
            timestamp: Unix timestamp of the trade
            status: Trade status (pending, submitted, completed, failed)

        Returns:
            str: Trade ID
        """
        trade_id = f"bt_{int(timestamp * 1000)}"

        trade = {
            "id": trade_id,
            "trade_type": trade_type,
            "token_address": token_address,
            "token_name": token_name,
            "amount": amount,
            "tx_signature": tx_signature,
            "timestamp": timestamp,
            "date": datetime.fromtimestamp(timestamp).isoformat(),
            "status": status,
            "pnl": None,
        }

        self.bot_trades.append(trade)
        self._save_data(self.bot_trades_file, self.bot_trades)
        logger.debug(f"Added bot trade: {trade_id}")
        return trade_id

    def update_bot_trade(self, trade_id: str, **kwargs):
        """
        Update a bot trade with new data

        Args:
            trade_id: Trade ID to update
            **kwargs: Fields to update
        """
        for i, trade in enumerate(self.bot_trades):
            if trade["id"] == trade_id:
                self.bot_trades[i].update(kwargs)
                self._save_data(self.bot_trades_file, self.bot_trades)
                logger.debug(f"Updated bot trade: {trade_id}")
                return

        logger.warning(f"Trade not found for update: {trade_id}")

    def update_bot_trade_status(self, trade_id: str, status: str):
        """
        Update a bot trade's status

        Args:
            trade_id: Trade ID to update
            status: New status
        """
        self.update_bot_trade(trade_id, status=status)

    def update_bot_trade_pnl(self, trade_id: str, pnl: float):
        """
        Update a bot trade's profit/loss

        Args:
            trade_id: Trade ID to update
            pnl: Profit/loss amount in SOL
        """
        self.update_bot_trade(trade_id, pnl=pnl)

    def get_wallet_trades(
        self, wallet_address: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """
        Get tracked wallet trades

        Args:
            wallet_address: Filter by wallet address (optional)
            limit: Maximum number of trades to return

        Returns:
            List of wallet trades
        """
        if wallet_address:
            filtered = [
                t for t in self.wallet_trades if t["wallet_address"] == wallet_address
            ]
        else:
            filtered = self.wallet_trades

        # Sort by timestamp descending (newest first)
        sorted_trades = sorted(filtered, key=lambda x: x["timestamp"], reverse=True)
        return sorted_trades[:limit]

    def get_bot_trades(
        self,
        token_address: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """
        Get bot trades

        Args:
            token_address: Filter by token address (optional)
            status: Filter by status (optional)
            limit: Maximum number of trades to return

        Returns:
            List of bot trades
        """
        filtered = self.bot_trades

        if token_address:
            filtered = [t for t in filtered if t["token_address"] == token_address]

        if status:
            filtered = [t for t in filtered if t["status"] == status]

        # Sort by timestamp descending (newest first)
        sorted_trades = sorted(filtered, key=lambda x: x["timestamp"], reverse=True)
        return sorted_trades[:limit]

    def get_trade_by_id(self, trade_id: str) -> Optional[Dict]:
        """
        Get a trade by ID

        Args:
            trade_id: Trade ID

        Returns:
            Trade data or None if not found
        """
        for trade in self.bot_trades:
            if trade["id"] == trade_id:
                return trade

        return None

    def calculate_pnl(self) -> Dict[str, Any]:
        """
        Calculate total profit/loss across all completed trades

        Returns:
            Dict with PnL statistics
        """
        completed_trades = [t for t in self.bot_trades if t["status"] == "completed"]

        total_pnl = sum(
            t.get("pnl", 0) for t in completed_trades if t.get("pnl") is not None
        )
        trade_count = len(completed_trades)
        win_count = sum(1 for t in completed_trades if t.get("pnl", 0) > 0)
        loss_count = sum(1 for t in completed_trades if t.get("pnl", 0) < 0)

        # Calculate win rate
        win_rate = (win_count / trade_count) * 100 if trade_count > 0 else 0

        return {
            "total_pnl": total_pnl,
            "trade_count": trade_count,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": win_rate,
            "last_updated": time.time(),
        }

    def get_token_stats(self) -> List[Dict]:
        """
        Get statistics for each token traded

        Returns:
            List of token statistics
        """
        token_stats = {}

        for trade in self.bot_trades:
            token_address = trade["token_address"]
            token_name = trade["token_name"]

            if token_address not in token_stats:
                token_stats[token_address] = {
                    "address": token_address,
                    "name": token_name,
                    "trade_count": 0,
                    "total_amount": 0,
                    "pnl": 0,
                }

            token_stats[token_address]["trade_count"] += 1
            token_stats[token_address]["total_amount"] += trade["amount"]

            if trade.get("pnl") is not None:
                token_stats[token_address]["pnl"] += trade["pnl"]

        return list(token_stats.values())
