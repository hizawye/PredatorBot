# PumpFun Bot - Solana Memecoin Trading Bot

A Python-based bot that tracks specific Solana wallet addresses on Pump.fun platform and automatically copies their trades in real-time.

## Features

- **Wallet Tracking**: Monitor specific Solana wallet addresses for buy/sell activity on Pump.fun
- **Copy Trading**: Automatically copy trades performed by tracked wallets
- **Dual Trading Modes**:
  - Paper Trading: Simulate trades without using real SOL
  - Real Trading: Execute actual transactions using your Solana wallet
- **Terminal Interface**: Comprehensive CLI for managing the bot
- **Web Dashboard**: Simple web interface to monitor performance and trade history
- **JSON Data Storage**: Store all trade information in local JSON files

## Prerequisites

- Python 3.8+
- QuickNode account with Solana endpoints (RPC & WebSocket)
- (For real trading) Solana wallet with private key

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/your-username/pumpfun-bot.git
   cd pumpfun-bot
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create and configure your `.env` file (use `.env.example` as a template):
   ```
   cp .env.example .env
   # Edit .env with your own values
   ```

## Usage

### Running the Bot

Start the bot in paper trading mode:

```
python main.py start
```

### Managing Tracked Wallets

Add a wallet to track:

```
python main.py add-wallet <wallet_address>
```

Remove a tracked wallet:

```
python main.py remove-wallet <wallet_address>
```

List all tracked wallets:

```
python main.py list-wallets
```

### Switching Trading Modes

Switch between paper and real trading:

```
python main.py set-mode paper
python main.py set-mode real
```

### Viewing Trade Information

Show profit/loss statistics:

```
python main.py show-pnl
```

Show trade history:

```
python main.py show-trades
```

Filter trades by wallet or token:

```
python main.py show-trades --wallet <address>
python main.py show-trades --token <token_address>
```

### Starting the Web Interface

```
python main.py web
```

Then open http://127.0.0.1:5000 in your browser.

## Web Dashboard

The web dashboard provides:

- Real-time bot status
- Performance overview
- Trade history tables
- Token statistics

## Disclaimer

This bot is provided for educational purposes only. Trading cryptocurrencies carries significant risk. Always do your own research and never trade more than you can afford to lose.

## License

MIT 