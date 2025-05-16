"""
Wallet Tracker - Monitor specific Solana wallet addresses for transactions on Pump.fun
"""

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Set, Callable

import aiohttp
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient

from ..utils.config import Config
from ..utils.constants import PUMPFUN_PROGRAM_ID

logger = logging.getLogger(__name__)


class WalletTracker:
    def __init__(self, config: Config):
        self.config = config
        self.rpc_client = AsyncClient(config.quicknode_rpc_url)
        self.ws_url = config.quicknode_wss_url
        self.tracked_wallets_file = os.path.join(config.database_path, "tracked_wallets.json")
        self.tracked_wallets: Set[str] = set()
        self._load_tracked_wallets()
        self.subscription_id: Optional[int] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
        self.callback: Optional[Callable] = None

    def _load_tracked_wallets(self):
        if os.path.exists(self.tracked_wallets_file):
            try:
                with open(self.tracked_wallets_file, "r") as f:
                    data = json.load(f)
                    self.tracked_wallets = set(data)
            except Exception as e:
                logger.error(f"Failed to load tracked wallets: {e}")

    def _save_tracked_wallets(self):
        try:
            os.makedirs(os.path.dirname(self.tracked_wallets_file), exist_ok=True)
            with open(self.tracked_wallets_file, "w") as f:
                json.dump(list(self.tracked_wallets), f)
        except Exception as e:
            logger.error(f"Failed to save tracked wallets: {e}")

    async def start(self, callback: Callable):
        """Start tracking wallets for transactions"""
        if self.running:
            logger.warning("Wallet tracker is already running")
            return

        self.callback = callback
        self.running = True
        self.session = aiohttp.ClientSession()
        await self._connect_websocket()
        await self._subscribe_to_program()

        asyncio.create_task(self._heartbeat())
        asyncio.create_task(self._listen_for_transactions())

        logger.info(f"Started tracking wallets: {', '.join(self.tracked_wallets)}")

    async def stop(self):
        """Stop tracking wallets"""
        if not self.running:
            return

        self.running = False

        if self.subscription_id is not None and self.ws is not None:
            await self._unsubscribe()

        if self.ws is not None:
            await self.ws.close()

        if self.session is not None:
            await self.session.close()

        self.ws = None
        self.session = None
        self.subscription_id = None
        logger.info("Stopped wallet tracker")

    def add_wallet(self, wallet_address: str):
        """Add a wallet to track"""
        self.tracked_wallets.add(wallet_address)
        self._save_tracked_wallets()
        logger.info(f"Added wallet to tracking: {wallet_address}")

    def remove_wallet(self, wallet_address: str):
        """Remove a wallet from tracking"""
        if wallet_address in self.tracked_wallets:
            self.tracked_wallets.remove(wallet_address)
            self._save_tracked_wallets()
            logger.info(f"Removed wallet from tracking: {wallet_address}")
        else:
            logger.warning(f"Wallet not found in tracking list: {wallet_address}")

    def get_tracked_wallets(self) -> List[str]:
        """Get list of tracked wallets"""
        return list(self.tracked_wallets)

    async def _connect_websocket(self):
        """Connect to QuickNode WebSocket"""
        self.ws = await self.session.ws_connect(self.ws_url)
        logger.info("Connected to QuickNode WebSocket")

    async def _subscribe_to_program(self):
        """Subscribe to program transactions"""
        if self.ws is None:
            logger.error("WebSocket not connected")
            return

        subscribe_message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "programSubscribe",
            "params": [
                PUMPFUN_PROGRAM_ID,
                {"encoding": "jsonParsed", "commitment": "confirmed"},
            ],
        }

        await self.ws.send_json(subscribe_message)
        response = await self.ws.receive_json()

        if "result" in response:
            self.subscription_id = response["result"]
            logger.info(f"Subscribed to program events with ID: {self.subscription_id}")
        else:
            logger.error(f"Failed to subscribe: {response}")

    async def _unsubscribe(self):
        """Unsubscribe from program events"""
        if self.ws is None or self.subscription_id is None:
            return

        unsubscribe_message = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "programUnsubscribe",
            "params": [self.subscription_id],
        }

        await self.ws.send_json(unsubscribe_message)
        response = await self.ws.receive_json()

        if "result" in response and response["result"]:
            logger.info(f"Unsubscribed from program events: {self.subscription_id}")
        else:
            logger.error(f"Failed to unsubscribe: {response}")

    async def _heartbeat(self):
        """Send periodic heartbeat to maintain connection"""
        while self.running and self.ws is not None:
            try:
                await self.ws.send_json({"jsonrpc": "2.0", "id": 999, "method": "ping"})
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                if self.running:
                    await self._reconnect()

    async def _reconnect(self):
        """Reconnect websocket if disconnected"""
        try:
            if self.ws is not None:
                await self.ws.close()

            await self._connect_websocket()
            await self._subscribe_to_program()
            logger.info("Successfully reconnected to WebSocket")
        except Exception as e:
            logger.error(f"Failed to reconnect: {e}")
            await asyncio.sleep(5)  # Wait before trying again

    async def _listen_for_transactions(self):
        """Listen for program transactions and filter by tracked wallets"""
        while self.running and self.ws is not None:
            try:
                msg = await self.ws.receive()

                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)

                    if "method" in data and data["method"] == "programNotification":
                        await self._process_transaction(data["params"]["result"])
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    logger.warning("WebSocket connection closed or error")
                    if self.running:
                        await self._reconnect()
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await asyncio.sleep(1)

    async def _process_transaction(self, transaction_data):
        """Process a transaction notification and check if it's from a tracked wallet"""
        try:
            # Extract transaction data
            tx_signature = transaction_data.get("signature", "unknown")

            # Get transaction details
            tx_info = await self.rpc_client.get_transaction(tx_signature)

            if tx_info.value is None:
                return

            # Check if transaction involves any tracked wallets
            accounts = []
            if tx_info.value.transaction.message.account_keys:
                accounts = [
                    str(account)
                    for account in tx_info.value.transaction.message.account_keys
                ]

            for wallet in self.tracked_wallets:
                if wallet in accounts:
                    # Transaction is from a tracked wallet, process it
                    if self.callback:
                        await self.callback(wallet, tx_signature, tx_info.value)
                    break

        except Exception as e:
            logger.error(
                f"Error processing transaction {transaction_data.get('signature', 'unknown')}: {e}"
            )
