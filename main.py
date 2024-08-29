import os
import logging
from dotenv import load_dotenv
from telegram import Update
import requests
from telegram import ReplyKeyboardRemove
import aiosqlite
from sqlite3 import Error
from tronpy import Tron
from tronpy.providers import HTTPProvider
from tronpy.keys import PrivateKey
from httpx import AsyncClient, Timeout, Limits
from tronpy.providers.async_http import AsyncHTTPProvider
from tronpy.defaults import CONF_NILE, CONF_MAINNET
from tronpy import AsyncTron
from datetime import datetime

from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
BASE_URL = os.getenv('BASE_URL')
TRON_GRID_API_KEY = os.getenv('TRON_GRID_API_KEY')

# Set up Tron client

client = Tron(HTTPProvider(api_key=TRON_GRID_API_KEY), network='nile')
# client = Tron(HTTPProvider(api_key=TRON_GRID_API_KEY), network='mainnet')

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays info on how to use the bot."""
    
    msg = (
        "- Use /wallet to get your wallet address and private key.\n"
        "- Use /balance to check your total balance in TRX.\n"
        "- Use /tokenbalance <token_symbol>/<token_name> to check your balance of tokens.\n"
        "- Use /transfer <receiver_address> <amount> to transfer tokens to another address.\n"
        "- Use /swap <currency1> <currency2> <amount> to swap tokens.\n"
        "- Use /copytrade <address> to start copy trading the transactions of the specified address.\n"
        "- Use /getmemecoininfo <address> to get the info of the memecoins.\n"
    )
    await update.message.reply_text(msg)


async def get_total_balance_in_trx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    #get he wallet address from db with user_id
    get_wallet_info = """
    SELECT address FROM addresses WHERE user_id=?;   
    """

    try:
        conn = await create_connection("wallet.db")
        if conn is None:
            raise Exception("Error!!! Cannot create/connect the database.")
        
        user_id = update.effective_user.id
        cur = await conn.cursor()
        
        # Check if the user_id already exists in the database
        await cur.execute(get_wallet_info, (user_id,))
        rows = await cur.fetchall()
        
        if len(rows) > 0:
            # User exists, return their TRX balance
            trx_balance = client.get_account_balance(rows[0][0])
            await update.message.reply_text(f"🔐 <strong>Wallet Info</strong> 🔐\n\n"
                f"📍 <strong>Address:</strong> \n{rows[0][0]}\n\n\n"
                f"💸 <strong>Total Account Balance:</strong> \n{trx_balance} TRX",
                parse_mode="HTML"
            )
        else:
            # User doesn't exist, return an error message
            await update.message.reply_text(
                "🔐 <strong>Wallet Info</strong> 🔐\n\n"
                "⚠️ <strong> Wallet doesn't exist, please create wallet using /wallet command.</strong>\n\n",
                parse_mode="HTML"
            )
    except Exception as e:
        await update.message.reply_text(
            f"🔐 <strong>Wallet Info</strong> 🔐\n\n"
            f"⚠️ <strong>Error:</strong> \n{str(e)}\n\n",
            parse_mode="HTML"
        )
        
def get_token_info(token_id):
    return client.get_asset(token_id)


async def get_token_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    #get the token balance from db with user_id
    get_wallet_info = """
    SELECT address FROM addresses WHERE user_id=?;
    """

    conn = await create_connection("wallet.db")
    
    if conn is None:
        print("Error!!! Cannot create/connect the database.")
        return
    
    user_id = update.effective_user.id
    cur = await conn.cursor()
    
    # Check if the user_id already exists in the database
    await cur.execute(get_wallet_info, (user_id,))
    rows = await cur.fetchall()
    
    if len(rows) > 0:
        # User exists, return their TRX balance
        address = rows[0][0]
        token_symbol = context.args[0].lower()
        wallet_assets = client.get_account_asset_balances(address)
        
        token_balance = 0
        token_name = ""
        token_abbr = ""
        
        for token_id, balance in wallet_assets.items():
            token_info = get_token_info(token_id)
            if token_info['name'].lower() == token_symbol or token_info['abbr'].lower() == token_symbol:
                token_balance = wallet_assets[token_id]
                token_name = token_info['name']
                token_abbr = token_info['abbr']
      
        if token_balance != 0:
            await update.message.reply_text(
                f"🔐<strong>Wallet Token Holdings</strong> 🔐\n\n"
                f"📍 <strong>Wallet Address:</strong> \n{address}\n\n"
                f"📍 <strong>Token Name:</strong> \n{token_name}({token_abbr})\n\n"
                f"💸 <strong>Token Balance:</strong> \n{token_balance / (10 ** 6)} ({token_abbr})",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(f"🔐 <strong>Wallet Info</strong> 🔐\n\n"
                f"📍 <strong>Address:</strong> \n{address}\n\n\n"
                f"🔒 <strong>Wallet has no {token_symbol.upper()} holdings.\n"
                f"Please check the token symbol and try again.</strong>\n\n",
                parse_mode="HTML"
            )
            
            
async def generate_trx_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate an address and sends it to the user."""
    
    get_wallet_info = """
    SELECT address, private_key FROM addresses WHERE user_id=?;
    """
    conn = await create_connection("wallet.db")
    
    if conn is None:
        raise Exception("Error!!! Cannot create/connect the database.")
    
    user_id = update.effective_user.id

    cur = await conn.cursor()
    
    # Check if the user_id already exists in the database
    await cur.execute(get_wallet_info, (user_id,))
    rows = await cur.fetchall()
    
    try:
        if len(rows) > 0:
            # User exists, return their address and private key
            await update.message.reply_text(
                f"🔐 <strong>Wallet Info</strong> 🔐\n\n"
                f"📍 <strong>Address:</strong> \n{rows[0][0]}\n\n"
                f"🔑 <strong>Private Key:</strong> \n{rows[0][1]}\n\n\n"
                f"⚠️ <strong>Disclaimer:</strong>\n Please store your private key and mnemonic securely. "
                "Anyone with access to these can control your funds. Do not share this information with anyone.",
                parse_mode="HTML"
            )
        else:
            private_key = PrivateKey.random()
            
            account = client.generate_address(priv_key=private_key)

            await insert_address(conn, account['base58check_address'], account['private_key'], account['hex_address'], user_id)
            
            await update.message.reply_text(
            f"🔐 <strong>Wallet Info</strong> 🔐\n\n"
            f"📍 <strong>Address:</strong> \n{account['base58check_address']}\n\n"
            f"�� <strong>Private Key:</strong> \n{account['private_key']}\n\n"
            f"⚠️ <strong>Disclaimer:</strong>\n Please store your private key and mnemonic securely. "
            "Anyone with access to these can control your funds. Do not share this information with anyone.",
            parse_mode="HTML"
        )
        
        await conn.close()
        
    except Exception as e:
        await update.message.reply_text(
            f"🔐 <strong>Wallet Info</strong> 🔐\n\n"
            f"Error: {e}",
            parse_mode="HTML"
        )
    
async def insert_address(conn, address, private_key, mnemonic, user_id):
    sql = """INSERT INTO addresses(address, private_key, mnemonic, user_id)
             VALUES(?,?,?,?)"""
             
    cur = await conn.cursor()
    await cur.execute(sql, (address, private_key, mnemonic, user_id))
    await conn.commit()
    

async def create_connection(db_file):
    """Create a database connection to the SQLite database specified by db_file."""
    
    create_table_sql = """
        CREATE TABLE IF NOT EXISTS addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT NOT NULL,
            private_key TEXT NOT NULL,
            mnemonic TEXT NOT NULL,
            user_id INTEGER NOT NULL
        );
        """
        
    check_table_sql = """
        SELECT name FROM sqlite_master WHERE type='table' AND name='addresses'
    """    
        
    connection = None
    
    try:
        connection = await aiosqlite.connect(db_file)
        print(f"Database connected to SQLite: {db_file}")
        
        if connection is not None:
            async with connection.cursor() as cursor:
                check = await cursor.execute(check_table_sql)
                table_exists = await check.fetchone()
                
                if table_exists is None:
                    await create_table(connection, create_table_sql)
            
    except Error as e:
        print(f"Error: '{e}' occurred while connecting to the database.")
        
    return connection

async def create_table(connection, create_table_sql):
    """Create a table from the create_table_sql statement."""
    
    try:
        async with connection.cursor() as cursor:
            await cursor.execute(create_table_sql)
            await connection.commit()
            print("Table created successfully.")
            
    except Error as e:
        print(f"Error: '{e}' occurred while creating the table.")

    # Get ERC-20 token balances
async def transfer(receiver_address: str, sender_address: str, sender_private_key: str, amount: int):
    
    try:
        print(f"Sending {amount} TRX from {sender_address} to {receiver_address}")
        
        _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                                timeout=Timeout(timeout=10, connect=5, read=5))
        
        print(f"Connecting to {_http_client}")
        
        provider = AsyncHTTPProvider(CONF_NILE, client=_http_client)
        client = AsyncTron(provider=provider)
        
        print(f"Connected to {client} using {provider}")

        priv_key = PrivateKey(bytes.fromhex(sender_private_key))
        
        print(f"Private key: {priv_key}")
         
        txb = (
            client.trx.transfer(sender_address, receiver_address, amount)
            .memo("Sending TRX from Python")
            .fee_limit(100_000_000)
        )
        
        print(f"Transaction builder: {txb}")
        
        
        txn = await txb.build()
        
        print(f"Transaction: {txn}")
        
        txn_ret = await txn.sign(priv_key).broadcast()
        
        print(txn_ret)

        await txn_ret.wait()
        await client.close()
        
        return txn_ret
    
    except Exception as e:
        raise Exception('Error in transfer: {}'.format(e))

async def transfer_trx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    get_wallet_info = """
    SELECT address, private_key FROM addresses WHERE user_id=?;
    """
    
    _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                            timeout=Timeout(timeout=10, connect=5, read=5))
    
    print(f"Connecting to {_http_client}")
    
    provider = AsyncHTTPProvider(CONF_NILE, client=_http_client)
    client = AsyncTron(provider=provider)
    
    if(len(context.args)!= 2):
            await update.message.reply_text(
            "Usage: /transfer <address> <amount>",
                reply_markup=ReplyKeyboardRemove(),
            )
            return
        
    #check if the address is valid
    address = context.args[0]
    if(client.is_address(address) == False):
        await update.message.reply_text(
            "Invalid address",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    
    amount = int(context.args[1])
    
    #check if the amount is valid
    if(amount <= 0):
        await update.message.reply_text(
            "Invalid amount",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
        
    conn = await create_connection("wallet.db")
    
    if conn is None:
        print("Error!!! Cannot create/connect the database.")
        return
    
    user_id = update.effective_user.id
    cur = await conn.cursor()
    
    # Check if the user_id already exists in the database
    await cur.execute(get_wallet_info, (user_id,))
    
    rows = await cur.fetchall()
    
    if len(rows) > 0:
        # User exists, return their address and private key
        address = rows[0][0]
        private_key = rows[0][1]  
        receiver_address = context.args[0]
        
        if(address == receiver_address):
            await update.message.reply_text(
                "🔐 <strong>You cannot send TRX to yourself!</strong> 🔐\n",
                parse_mode="HTML"
            )
            return
    
    try:
        bandwidth = await client.get_bandwidth('TVrzEkHN8CXkTjBQHwDKWn9bUrAaWCkrev')
        
        print(f"Bandwidth: {bandwidth}")
        
        if(int(bandwidth) < 3):
            await update.message.reply_text(
                "🔐 <strong>You don't have enough bandwidth!</strong> 🔐\n",
                parse_mode="HTML"
            )
            return
        
    except Exception as e:
        print(f"Error: '{e}' occurred while getting bandwidth.")  
        
        
    try:            
        amount = context.args[1]
        #convert to wei
        amount = float(amount) * (10 ** 6)
        
        # Transfer token
        transaction = await transfer(receiver_address, address, private_key, int(amount))
        print(transaction)
        
        if(transaction):
            await update.message.reply_text(
                f"🔐 <strong>Transfer Info</strong> 🔐\n\n"
                f"📍 <strong>Sender Address:</strong> \n{address}\n\n"
                f"📍 <strong>Receiver Address:</strong> \n{receiver_address}\n\n"
                f"💸 <strong>Amount:</strong> \n{amount/(10 ** 6)} TRX\n\n"
                f"📝 <strong>Transaction Hash:</strong> \nhttps://nile.tronscan.org/#/transaction/{transaction['txid']}\n\n",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                "🔐 <strong>Something went wrong!</strong> 🔐\n\n"
                f" - Use /transfer <receiver_address> <amount> to transfer tokens to another address.\n"
                f" - Check if the address/amount is correct and try again.\n"
                f" - Make sure you have created a wallet and have enough balance in your wallet.\n",
                parse_mode="HTML"
            )
            
    except Exception:
        # User doesn't exist, return an error message
        await update.message.reply_text(
            "🔐 <strong>Something went wrong!</strong> 🔐\n\n"
            f" - Use /transfer <receiver_address> <amount> to transfer tokens to another address.\n"
            f" - Check if the address/amount is correct and try again.\n"
            f" - Make sure you have created a wallet and have enough balance in your wallet.\n",
            parse_mode="HTML"
        )
        
async def swap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    get_wallet_info = """
    SELECT address, private_key FROM addresses WHERE user_id=?;
    """
    
    _http_client = AsyncClient(limits=Limits(max_connections=100, max_keepalive_connections=20),
                            timeout=Timeout(timeout=10, connect=5, read=5))
    
    print(f"Connecting to {_http_client}")
    
    provider = AsyncHTTPProvider(CONF_MAINNET, client=_http_client)
    client = AsyncTron(provider=provider)
    client2 = Tron(HTTPProvider(api_key=TRON_GRID_API_KEY), network='mainnet')
    


    if len(context.args) != 3:
        await update.message.reply_text(
            "Usage: /swap <token_address> <token_address> <amount>",



            reply_markup=ReplyKeyboardRemove(),
        )
        return
        
    token_address_1 = context.args[0]
    token_address_2 = context.args[1]
    amount = context.args[2]   
    
    try:

        if not client.is_address(token_address_1) or not client.is_address(token_address_2):
            await update.message.reply_text(
                "🔐 <strong>Invalid token address!</strong> 🔐\n",
                parse_mode="HTML"
            )
            return
    except Exception as e:
        await update.message.reply_text(
            "🔐 <strong>Invalid token address!</strong> 🔐\n",
            parse_mode="HTML"
        )
        return
    

    if token_address_1 == token_address_2:
        await update.message.reply_text(
            "🔐 <strong>You cannot swap the same token!</strong> 🔐\n",
            parse_mode="HTML"
        )
        return
    
    

    if not amount.isnumeric():
        await update.message.reply_text(
            "🔐 <strong>Invalid amount!</strong> 🔐\n",
            parse_mode="HTML"
        )
        return
    
    
    try:
        conn = await create_connection("wallet.db")

        if conn is None:
            print("Error!!! Cannot create/connect the database.")
            return

        user_id = update.effective_user.id
        cur = await conn.cursor()

        # Check if the user_id already exists in the database
        await cur.execute(get_wallet_info, (user_id,))
        rows = await cur.fetchall()

        if len(rows) > 0:
            # User exists, return their address and private key
            address = rows[0][0]
            priv_key = rows[0][1]
            
        await conn.close()
        
        #Smart Router
        private_key = PrivateKey.fromhex(priv_key)
        
        # Smart Router endpoint
        url = 'https://rot.endjgfsv.link/swap/router'
        
        params = {
            'fromToken': token_address_1,
            'toToken': token_address_2,
            'amountIn': str(int(amount) * 1000000),
            'typeList': 'PSM,CURVE,CURVE_COMBINATION,WTRX,SUNSWAP_V1,SUNSWAP_V2,SUNSWAP_V3'
        }

        # Make the GET request
        response = requests.get(url, params=params)
        best_outcome = None
        # Check if the request was successful
        if response.status_code == 200:
            swap_info = response.json()
            print(f"Swap Info: {swap_info}")
            best_outcome = get_best_price(swap_info)
            print(f"Best Outcome: {best_outcome}")
        else:
            print(f"Request failed with status code {response.status_code}")
        
       
        contract = client2.get_contract("TFVisXFaijZfeyeSjCEVkHfex7HGdTxzF9")
        
        print(f"Contract: {contract.functions.swapExactInput(best_outcome['tokens'], best_outcome['poolVersions'], [len(best_outcome['poolVersions']) - 1], best_outcome['poolFees'], (best_outcome['amountIn'], '1', address, '1662825600'))}")
        
        txn = (
             contract.functions.swapExactInput(
                best_outcome['tokens'],
                best_outcome['poolVersions'],
                [len(best_outcome['poolVersions']) - 1],
                best_outcome['poolFees'],
                (best_outcome['amountIn'], '1', address, '1662825600'),
            )
        )
        # print(f"Transaction: {txn}")
        
        # txn = await txb.build()
        # print(txn)
        # txn_ret = await txn.sign(priv_key).broadcast()

        # print(txn_ret)
        # print(await txn_ret.wait())
        # await client.close()
        
    
        await update.message.reply_text(
            f"🔐 <strong>Swap Info</strong> 🔐\n\n"
            f"📍 <strong>Sender Address:</strong> \n{address}\n\n"
            f"📍 <strong>Token Address 1:</strong> \n{token_address_1}\n\n"
            f"📍 <strong>Token Address 2:</strong> \n{token_address_2}\n\n"
            f"💸 <strong>Amount:</strong> \n{amount}\n\n",
            parse_mode="HTML"
        )
        
    except Exception:
        # User doesn't exist, return an error message
        await update.message.reply_text(
            "🔐 <strong>Something went wrong!</strong> 🔐\n\n"

            f" - Use /swap <address> <address> <amount> to swap tokens.\n"
            f" - Check if the address/amount is correct and try again.\n"
            f" - Make sure you have created a wallet and have enough balance in your wallet.\n",
            parse_mode="HTML"
        )
        return
    
def get_best_price(swap_data):
    best_option = None
    max_amount_out = 0
    
    for option in swap_data['data']:
        amount_out = float(option['amountOut'])
        if amount_out > max_amount_out:
            max_amount_out = amount_out
            best_option = option
    
    return best_option

async def get_meme_coin_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "Usage: /getmemecoininfo <address>",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    
    address = context.args[0]
    
    # Check if the address is valid
    if not client.is_address(address):
        await update.message.reply_text(
            "Invalid address",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    

    url = f"https://apilist.tronscanapi.com/api/token_trc20?contract={address}&showAll=1&start=&limit="

    # Make the GET request
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code == 200:
        data = response.json()
        
        # Extract relevant information
        tokens = data.get('trc20_tokens', [])
        
        # Prepare the formatted message
        formatted_message = "🔐 <strong>Meme Coin Info</strong> 🔐\n\n"
        formatted_message += f"📍 <strong>Address:</strong> \n <a href='https://tronscan.org/#/token20/{address}'>{address}</a>\n"

        if tokens:
            for token in tokens:
                name = token.get('name', 'N/A')
                symbol = token.get('symbol', 'N/A')
                total_supply = token.get('total_supply', 'N/A')
                total_supply_with_decimals = token.get('total_supply_with_decimals', 'N/A')
                holders_count = token.get('holders_count', 'N/A')
                transfer_24h = token.get('transfer24h', 'N/A')
                issue_time = token.get('issue_time', 'N/A')
                transfer_num = token.get('transfer_num', 'N/A')
                volume_24h = token.get('volume24h', 'N/A')
                price_trx = token.get('price_trx', 'N/A')
                liquidity_24h = token.get('liquidity24h', 'N/A')
                liquidity_24h_rate = token.get('liquidity24h_rate', 'N/A')
                grey_tag = token.get('greyTag', 'N/A')
                red_tag = token.get('redTag', 'N/A')
                blue_tag = token.get('blueTag', 'N/A')
                icon_url = token.get('icon_url', 'N/A')
                token_desc = token.get('token_desc', 'N/A')
                home_page = token.get('home_page', 'N/A')
                social_media_list = token.get('social_media_list', [])
                public_tag = token.get('publicTag', 'N/A')
                email = token.get('email', 'N/A')
                git_hub = token.get('git_hub', 'N/A')
                white_paper = token.get('white_paper', 'N/A')
                issue_address = token.get('issue_address', 'N/A')
                just_swap_volume_24h = token.get('justSwapVolume24h', 'N/A')
                just_swap_volume_24h_rate = token.get('justSwapVolume24h_rate', 'N/A')
                price_in_trx = token.get('market_info', {}).get('priceInTrx', 'N/A')
                price_in_usd = token.get('market_info', {}).get('priceInUsd', 'N/A')
                liquidity = token.get('market_info', {}).get('liquidity', 'N/A')
                gain = token.get('market_info', {}).get('gain', 'N/A')
                pair_url = token.get('market_info', {}).get('pairUrl', 'N/A')
                token_price_line = token.get('tokenPriceLine', {}).get('data', [])
                
                # Add token details
                formatted_message += f"""
💰 <strong>Token Name:</strong> {name}
🔖 <strong>Symbol:</strong> {symbol.upper()}
📈 <strong>Total Supply:</strong> {total_supply} (with decimals: {total_supply_with_decimals})
📝 <strong>Description:</strong> {token_desc}
👥 <strong>Holders Count:</strong> {holders_count}

🔄 <strong>Transfers in 24h:</strong> {transfer_24h}
🔢 <strong>Total Transfers:</strong> {transfer_num}
📉 <strong>Volume (24h):</strong> {volume_24h}

💲 <strong>Price:</strong>
TRX: {price_in_trx}
USD: {price_in_usd}

💧 <strong>Liquidity:</strong> {liquidity}
24h: ${liquidity_24h}
24h Rate: ${liquidity_24h_rate}

📊 <strong>JustSwap Volume (24h):</strong> {just_swap_volume_24h}
Rate: {just_swap_volume_24h_rate}

🕒 <strong>Issue Date:</strong> {issue_time}


🏠 <strong>Home Page:</strong> <a href="{home_page}">{home_page}</a>
🏷️ <strong>Tags:</strong> {grey_tag},{red_tag},{blue_tag}
📛 <strong>Public Tag:</strong> {public_tag}

📧 <strong>Email:</strong> {email}
💻 <strong>GitHub:</strong> {git_hub}
📄 <strong>White Paper:</strong> {white_paper}
🏠 <strong>Issue Address:</strong> {issue_address}

📈 <strong>Gain:</strong> {gain * 100}%
🔗 <strong>Pair URL:</strong> <a href="{pair_url}">{pair_url}</a>
"""

                # Add social media links
                if social_media_list:
                    formatted_message += "\n📱 <strong>Social Media Links:</strong>\n"
                    for platform in social_media_list:
                        name = platform.get('name', 'N/A')
                        url = platform.get('url', 'N/A').strip('[]""')  # Clean up the URL format
                        formatted_message += f"   • {name}: <a href='{url}'>{url}</a>\n"

                # Add token price line data
                if token_price_line:
                    formatted_message += "\n📊 <strong>Price Over Time (USD):</strong>\n"
                    for price_point in token_price_line[:5]:  # Limit to 5 most recent data points
                        timestamp = price_point.get('time', 'N/A')
                        price_usd = price_point.get('priceUsd', 'N/A')
                        if timestamp != 'N/A':
                            # Convert Unix timestamp to datetime
                            formatted_time = datetime.utcfromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S UTC')
                        else:
                            formatted_time = 'N/A'
                        formatted_message += f"   • {formatted_time}: {price_usd} USD\n"

                formatted_message += f"\n🖼️ <strong>Icon:</strong> <a href='{icon_url}'>View Icon</a>\n"
        else:
            formatted_message += "\nNo tokens found for this address.\n"

    else:
        formatted_message = f"Error fetching data: {response.status_code}"

    # Send the formatted response back to the user
    await update.message.reply_text(
        formatted_message,
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )

def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_callback)) #complete
    application.add_handler(CommandHandler("wallet", generate_trx_address)) #complete
    application.add_handler(CommandHandler("balance", get_total_balance_in_trx)) #complete
    application.add_handler(CommandHandler("tokenbalance", get_token_balance)) #complete
    application.add_handler(CommandHandler("transfer", transfer_trx)) #complete
    application.add_handler(CommandHandler("swap", swap)) #needs fixing
    application.add_handler(CommandHandler("getmemecoininfo", get_meme_coin_info)) #inprogress
    
    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES, read_timeout=600, write_timeout=600, pool_timeout=600, connect_timeout=600, timeout=600)

if __name__ == '__main__':
  main()
