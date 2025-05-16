"""
Configuration management for PumpFun Bot
"""

import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration class for PumpFun Bot"""

    # QuickNode RPC/WSS endpoints
    quicknode_rpc_url: str
    quicknode_wss_url: str

    # Wallet settings
    wallet_private_key: Optional[str] = None

    # Database settings
    database_path: str = "data"

    # Trading settings
    trading_mode: str = "paper"  # "paper" or "real"
    max_sol_per_trade: float = 0.1
    slippage_tolerance: float = 2.0  # percentage

    @classmethod
    def from_env(cls, env_file: str = ".env") -> "Config":
        """
        Load configuration from environment variables

        Args:
            env_file: Path to .env file

        Returns:
            Config object
        """
        # Load from .env file if it exists
        env_path = Path(env_file)
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded configuration from {env_path}")
        else:
            logger.warning(
                f"Environment file {env_path} not found, using environment variables"
            )

        # Get required settings
        quicknode_rpc_url = os.getenv("QUICKNODE_RPC_URL")
        quicknode_wss_url = os.getenv("QUICKNODE_WSS_URL")

        if not quicknode_rpc_url or not quicknode_wss_url:
            raise ValueError("QUICKNODE_RPC_URL and QUICKNODE_WSS_URL must be provided")

        # Get optional settings with defaults
        wallet_private_key = os.getenv("WALLET_PRIVATE_KEY")
        database_path = os.getenv("DATABASE_PATH", "data")
        trading_mode = os.getenv("TRADING_MODE", "paper")

        # Validate trading mode
        if trading_mode not in ["paper", "real"]:
            logger.warning(
                f"Invalid trading mode: {trading_mode}, falling back to 'paper'"
            )
            trading_mode = "paper"

        # Parse numeric values
        try:
            max_sol_per_trade = float(os.getenv("MAX_SOL_PER_TRADE", "0.1"))
        except ValueError:
            logger.warning("Invalid MAX_SOL_PER_TRADE, using default 0.1")
            max_sol_per_trade = 0.1

        try:
            slippage_tolerance = float(os.getenv("SLIPPAGE_TOLERANCE", "2"))
        except ValueError:
            logger.warning("Invalid SLIPPAGE_TOLERANCE, using default 2%")
            slippage_tolerance = 2.0

        return cls(
            quicknode_rpc_url=quicknode_rpc_url,
            quicknode_wss_url=quicknode_wss_url,
            wallet_private_key=wallet_private_key,
            database_path=database_path,
            trading_mode=trading_mode,
            max_sol_per_trade=max_sol_per_trade,
            slippage_tolerance=slippage_tolerance,
        )
