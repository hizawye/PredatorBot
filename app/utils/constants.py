"""
Constants used throughout the application
"""

# Pump.fun program ID on Solana blockchain
# Note: This is a placeholder value and should be updated with the actual program ID
PUMPFUN_PROGRAM_ID = "PFUNig5zBqS3Er5JxN4m4gzqYxGEU8SudsZ7tBCbGQq"

# Trade types
TRADE_TYPE_BUY = "buy"
TRADE_TYPE_SELL = "sell"

# Trade statuses
TRADE_STATUS_PENDING = "pending"
TRADE_STATUS_SUBMITTED = "submitted"
TRADE_STATUS_COMPLETED = "completed"
TRADE_STATUS_FAILED = "failed"

# CLI command descriptions
CLI_DESC_ADD_WALLET = "Add a wallet address to track"
CLI_DESC_REMOVE_WALLET = "Remove a wallet address from tracking"
CLI_DESC_LIST_WALLETS = "List all tracked wallet addresses"
CLI_DESC_SET_MODE = "Set trading mode (paper/real)"
CLI_DESC_SHOW_PNL = "Show profit/loss stats"
CLI_DESC_SHOW_TRADES = "Show trade history"
CLI_DESC_START = "Start the bot"
CLI_DESC_STOP = "Stop the bot"
CLI_DESC_STATUS = "Show bot status"
CLI_DESC_WEB = "Start the web interface"

# Web interface settings
WEB_HOST = "127.0.0.1"
WEB_PORT = 5000
WEB_API_PREFIX = "/api/v1"
