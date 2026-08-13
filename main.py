import os
import json
import time
import hmac
import hashlib
import requests
import logging
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

# Dummy web server for Render
app = Flask('')

@app.route('/')
def home():
    return "NBK Digital Mart Auto-Payment Bot is Live!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run).start()

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=INFO)

# --- ENVIRONMENT VARIABLES ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8882711271:AAGpU6Qac3EFqQ1nioWamAT-eTdT5wPM6QE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8736699831"))
SUPPORT_USERNAME = "nawabibnekhalid"

BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.environ.get("BINANCE_SECRET_KEY", "")
USDT_WALLET = os.environ.get("USDT_WALLET_ADDRESS", "")

PRODUCTS_FILE = "products.json"
USED_TXIDS_FILE = "used_txids.json"

ADD_NAME, ADD_PRICE, ADD_DESC, WAIT_TXID = range(4)

def load_products():
    if os.path.exists(PRODUCTS_FILE):
        with open(PRODUCTS_FILE, "r") as f:
            return json.load(f)
    return {"1": {"name": "Canva Pro", "price": "1.5", "desc": "Official invite."}}

def save_products(products):
    with open(PRODUCTS_FILE, "w") as f:
        json.dump(products, f, indent=4)

def load_used_txids():
    if os.path.exists(USED_TXIDS_FILE):
        with open(USED_TXIDS_FILE, "r") as f:
            return json.load(f)
    return []

def save_used_txid(txid):
    txids = load_used_txids()
    txids.append(txid)
    with open(USED_TXIDS_FILE, "w") as f:
        json.dump(txids, f, indent=4)

def verify_binance_deposit(txid, expected_amount):
    if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
        return False, "API Keys configure nahi hain."
    if txid in load_used_txids():
        return False, "Yeh TxID pehle use ho chuki hai!"

    url = "https://api.binance.com/sapi/v1/capital/deposit/hisrec"
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(BINANCE_SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    
    try:
        response = requests.get(f"{url}?{query_string}&signature={signature}", headers=headers, timeout=10)
        data = response.json()
        if response.status_code == 200 and isinstance(data, list):
            for deposit in data:
                if deposit.get("txId") == txid and deposit.get("status") == 1:
                    if float(deposit.get("amount", 0)) >= float(expected_amount):
                        save_used_txid(txid)
                        return True, "Verified!"
            return False, "TxID nahi mili ya payment abhi pending hai."
        return False, "Binance API Error."
    except:
        return False, "Connection Error."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = load_products()
    keyboard = [[InlineKeyboardButton(f"{p['name']} - ${p['price']} USDT", callback_data=f"buy_{id}")] for id, p in products.items()]
    keyboard.append([InlineKeyboardButton("💬 Contact Support", url=f"https://t.me/{SUPPORT_USERNAME}")])
    await update.message.reply_text("👋 Welcome! Product select karein:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    p_id = query.data.split("_")[1]
    product = load_products().get(p_id)
    context.user_data['selected_product'] = product
    msg = f"📦 {product['name']}\n💰 Price: {product['price']} USDT\n\n💳 Pay to: `{USDT_WALLET}`\n\n⚠️ Pay karke TxID reply mein bhejein!"
    await query.message.reply_text(msg, parse_mode="Markdown")
    return WAIT_TXID

async def handle_txid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txid = update.message.text.strip()
    product = context.user_data.get('selected_product')
    is_valid, msg = verify_binance_deposit(txid, product['price'])
    if is_valid:
        await update.message.reply_text("🎉 Payment Successful! Product deliver ho rahi hai.")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ Order: {product['name']}\n👤 User: @{update.effective_user.username}")
    else:
        await update.message.reply_text(f"❌ Failed: {msg}")
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    conv = ConversationHandler(entry_points=[CallbackQueryHandler(button_click, pattern="^buy_")], states={WAIT_TXID: [MessageHandler(filters.TEXT, handle_txid)]}, fallbacks=[])
    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
