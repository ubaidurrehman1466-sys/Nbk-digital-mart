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
    filters,
    ContextTypes,
)

# --- FLASK KEEP-ALIVE SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "NBK Digital Mart Ready-Made Bot is Active!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web).start()

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- CONFIGURATION ---
BOT_TOKEN = "8882711271:AAGpU6Qac3EFqQ1nioWamAT-eTdT5wPM6QE"
ADMIN_ID = 8736699831
SUPPORT_USERNAME = "nawabibnekhalid"

BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.environ.get("BINANCE_SECRET_KEY", "")
USDT_WALLET = "0xa1441c6f6b815a921bf814d241d7a507e32fd71b"

PRODUCTS_FILE = "products.json"
USED_TXIDS_FILE = "used_txids.json"

# In-memory simple user states (Prevents ConversationHandler freezing)
USER_STATES = {}

# --- HELPER FUNCTIONS ---
def load_products():
    if os.path.exists(PRODUCTS_FILE):
        try:
            with open(PRODUCTS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_products(products):
    with open(PRODUCTS_FILE, "w") as f:
        json.dump(products, f, indent=4)

def load_used_txids():
    if os.path.exists(USED_TXIDS_FILE):
        try:
            with open(USED_TXIDS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_used_txid(txid):
    txids = load_used_txids()
    txids.append(txid)
    with open(USED_TXIDS_FILE, "w") as f:
        json.dump(txids, f, indent=4)

# --- LIVE BINANCE AUTO-VERIFICATION ---
def verify_binance_deposit(txid, expected_amount):
    if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
        return False, "Binance API Keys missing hain."

    if txid in load_used_txids():
        return False, "Yeh TxID pehle se verify ho chuki hai!"

    url = "https://api.binance.com/sapi/v1/capital/deposit/hisrec"
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    
    try:
        signature = hmac.new(BINANCE_SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
        full_url = f"{url}?{query_string}&signature={signature}"

        response = requests.get(full_url, headers=headers, timeout=10)
        data = response.json()

        if response.status_code == 200 and isinstance(data, list):
            for deposit in data:
                if deposit.get("txId") == txid and deposit.get("status") == 1:
                    actual_amount = float(deposit.get("amount", 0))
                    if actual_amount >= (float(expected_amount) * 0.95):
                        save_used_txid(txid)
                        return True, "Payment Verified!"
                    else:
                        return False, f"Amount Kam hai. Required: ${expected_amount}, Paid: ${actual_amount}"
            return False, "TxID deposit history mein nahi mili. 1-2 mins baad try karein."
        return False, "Binance API Response Error."
    except Exception as e:
        return False, f"Connection Error: {str(e)}"

# --- COMMANDS ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    USER_STATES.pop(chat_id, None)
    
    products = load_products()
    if not products:
        text = "👋 Welcome to **NBK Digital Mart**!\n\nAbhi store mein koi product nahi hai."
        keyboard = [[InlineKeyboardButton("💬 Contact Support", url=f"https://t.me/{SUPPORT_USERNAME}")]]
    else:
        text = "👋 Welcome to **NBK Digital Mart**!\n\nNiche list se product select karein (100% Auto Binance Verification):"
        keyboard = [[InlineKeyboardButton(f"{p['name']} - ${p['price']} USDT", callback_data=f"buy_{p_id}")] for p_id, p in products.items()]
        keyboard.append([InlineKeyboardButton("💬 Contact Support", url=f"https://t.me/{SUPPORT_USERNAME}")])

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("🚫 Access Denied.")
        return

    USER_STATES.pop(user_id, None)
    keyboard = [
        [InlineKeyboardButton("➕ Add Product", callback_data="admin_add")],
        [InlineKeyboardButton("❌ Delete Product", callback_data="admin_delete")],
        [InlineKeyboardButton("📦 View Products", callback_data="admin_view")]
    ]
    await update.message.reply_text("⚙️ **NBK Digital Mart Admin Panel**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_STATES.pop(update.effective_chat.id, None)
    await update.message.reply_text("✅ Action Cancelled. Clear state.")

# --- CALLBACK BUTTONS ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    if data.startswith("buy_"):
        p_id = data.split("_")[1]
        product = load_products().get(p_id)
        if product:
            USER_STATES[chat_id] = {"action": "WAIT_TXID", "product": product}
            msg = (
                f"📦 **{product['name']}**\n"
                f"💰 **Price:** ${product['price']} USDT\n\n"
                f"💳 **USDT Deposit Address (BEP20 / BSC):**\n"
                f"`{USDT_WALLET}`\n\n"
                "⚠️ Payment bhejney ke baad **TxID (Transaction Hash)** reply mein send karein!"
            )
            await query.message.reply_text(msg, parse_mode="Markdown")

    elif data == "admin_add" and user_id == ADMIN_ID:
        USER_STATES[chat_id] = {"action": "ADD_NAME"}
        await query.message.reply_text("Product ka **Name** likhein:")

    elif data == "admin_view" and user_id == ADMIN_ID:
        prods = load_products()
        text = "📦 **Current Products:**\n\n" + "\n".join([f"• {p['name']} - ${p['price']} USDT" for p in prods.values()]) if prods else "Store khali hai."
        await query.message.reply_text(text)

    elif data == "admin_delete" and user_id == ADMIN_ID:
        prods = load_products()
        if not prods:
            await query.message.reply_text("Koi product delete karne ke liye nahi hai.")
            return
        keyboard = [[InlineKeyboardButton(f"❌ Delete {p['name']}", callback_data=f"del_{p_id}")] for p_id, p in prods.items()]
        await query.message.reply_text("Select product to delete:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("del_") and user_id == ADMIN_ID:
        p_id = data.split("_")[1]
        prods = load_products()
        if p_id in prods:
            name = prods[p_id]['name']
            del prods[p_id]
            save_products(prods)
            await query.message.reply_text(f"✅ **{name}** delete ho gayi!")

# --- TEXT MESSAGE HANDLER ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    state = USER_STATES.get(chat_id)

    if not state:
        return

    action = state.get("action")

    if action == "WAIT_TXID":
        product = state.get("product")
        await update.message.reply_text("⏳ **Binance Blockchain se Live TxID Verify ho rahi hai... Wait karein.**")
        
        is_valid, msg = verify_binance_deposit(text, product['price'])
        if is_valid:
            USER_STATES.pop(chat_id, None)
            delivery_text = (
                f"🎉 **PAYMENT AUTO-VERIFIED!**\n\n"
                f"📦 **Product:** {product['name']}\n\n"
                f"📝 **Your Details / Link:**\n"
                f"{product['desc']}\n\n"
                f"Thank you for shopping with NBK Digital Mart! ❤️"
            )
            await update.message.reply_text(delivery_text, parse_mode="Markdown")
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⚡ **AUTO ORDER DELIVERED!**\nUser: @{update.effective_user.username}\nProduct: {product['name']}\nTxID: `{text}`",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"❌ **Verification Failed:** {msg}\nSupport: @{SUPPORT_USERNAME}")

    elif action == "ADD_NAME":
        USER_STATES[chat_id] = {"action": "ADD_PRICE", "name": text}
        await update.message.reply_text("Product ki **Price (USDT mein)** likhein (e.g. 1.5):")

    elif action == "ADD_PRICE":
        USER_STATES[chat_id]["price"] = text
        USER_STATES[chat_id]["action"] = "ADD_DESC"
        await update.message.reply_text("Product ka **Link / Account Details** likhein (Jo auto-delivery par milega):")

    elif action == "ADD_DESC":
        p_name = USER_STATES[chat_id]["name"]
        p_price = USER_STATES[chat_id]["price"]
        
        prods = load_products()
        new_id = str(len(prods) + 1)
        prods[new_id] = {"name": p_name, "price": p_price, "desc": text}
        save_products(prods)
        
        USER_STATES.pop(chat_id, None)
        await update.message.reply_text(f"🎉 **{p_name}** successfully add ho gayi!", parse_mode="Markdown")

def main():
    app_bot = Application.builder().token(BOT_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start_cmd))
    app_bot.add_handler(CommandHandler("admin", admin_cmd))
    app_bot.add_handler(CommandHandler("cancel", cancel_cmd))
    
    app_bot.add_handler(CallbackQueryHandler(handle_callback))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot starting with zero-freeze architecture...")
    app_bot.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
