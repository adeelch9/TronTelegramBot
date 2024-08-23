## Project Description

 This project is a Telegram bot designed for the TRON blockchain. The bot allows users to create a TRX wallet, check balances, transfer TRX, and swap tokens on SunSwap directly from Telegram.

## Requirements


* requests
* pandas
* emoji
* python-dotenv
* python-telegram-bot
* web3
* mnemonic
* aiosqlite
* httpcore[asyncio]
* tronpy
* trontxsize

You can refer to your `requirements.txt` file for this.

## Installation

1. Clone the repository: `git clone https://github.com/adeel09/TronTelegramBot.git`
2. Install dependencies: `pip install -r requirements.txt`
3. Set up your environment variables: `cp .env.example .env` and fill in the necessary values

## Usage

Configure your telgram bot using BotFather.

Run `python3 main.py`  in project directory.

Go to you bot on telegram and send /start to get the usage instructions.
- Use /wallet to get your wallet address and private key.
- Use /balance to check your total balance in TRX.
- Use /tokenbalance <token_symbol>/<token_name> to check your balance of tokens.
- Use /transfer <receiver_address> <amount> to transfer tokens to another address.
- Use /swap <currency1> <currency2> <amount> to swap tokens. (inprogress)
- Use /copytrade <address> to start copy trading the transactions of the specified address. (inprogress)

## Contributing

 If you want others to contribute to your project, you can add a section on how to do so. This can include information on how to submit pull requests, report issues, and more.

Here's an example of what your expanded README file could look like:

## Contributing

If you'd like to contribute to this project, please submit a pull request with your changes. You can also report any issues you encounter.

Feel free to add or remove sections as necessary to fit your project's needs!