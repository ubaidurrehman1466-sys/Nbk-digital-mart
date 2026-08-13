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

# --- KEEP ALIVE WEB SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "NBK Digital Mart Bot is 100% Running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web).start()

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- DIRECT HARDCODED CONFIG (To Avoid Environment Variable Errors) ---
BOT_TOKEN = "8882711271:AAGpU6Qac3EFqQ1nioWamAT-eTdT5wPM6QE"
ADMIN_ID = 8736699831
SUPPORT_USERNAME = "nawabibnekhalid"

BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.environ.get("BINANCE_SECRET_KEY", "")
USDT_WALLET = "0xa1441c6f6b815a921bf814d241d7a507e32fd71b"

PRODUCTS_FILE = "products.json"
USED_TXIDS_FILE = "used_txids.json"

WAIT_TXID = 1
ADD_NAME, ADD_PRICE, ADD_DESC = 2, 3, 4

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

def verify_binance_deposit(txid, expected_amount):
    if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
        return False, "Binance API Key configured nahi hai."

    if txid in load_used_txids():
        return False, "Yeh TxID pehle use ho chuki hai!"

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
                        return True, "Verified!"
                    else:
                        return False, f"Amount kam hai. Required: ${expected_amount}"
            return False, "TxID deposit history mein nahi mili."
        return False, "Binance API Error."
    except Exception as e:
        return False, f"Connection Error: {str(e)}"

# --- COMMAND HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = load_products()
    if not products:
        msg_text = "👋 Welcome to **NBK Digital Mart**!\n\nAbhi koi product available nahi hai."
        keyboard = [[InlineKeyboardButton("💬 Contact Support", url=f"https://t.me/{SUPPORT_USERNAME}")]]
    else:
        msg_text = "👋 Welcome to **NBK Digital Mart**!\n\nNiche di gayi list se product select karein:"
        keyboard = [[InlineKeyboardButton(f"{p['name']} - ${p['price']} USDT", callback_data=f"buy_{p_id}")] for p_id, p in products.items()]
        keyboard.append([InlineKeyboardButton("💬 Contact Support", url=f"https://t.me/{SUPPORT_USERNAME}")])

    await update.message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def btn_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    p_id = query.data.split("_")[1]
    product = load_products().get(p_id)
    
    if product:
        context.user_data['buy_product'] = product
        msg = (
            f"📦 **{product['name']}**\n"
            f"💰 **Price:** ${product['price']} USDT\n\n"
            f"💳 **USDT Address (BEP20 / BSC):**\n"
            f"`{USDT_WALLET}`\n\n"
            "⚠️ Payment karke **TxID (Transaction Hash)** yahan send karein!"
        )
        await query.message.reply_text(msg, parse_mode="Markdown")
        return WAIT_TXID

async def handle_txid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_txid = update.message.text.strip()
    product = context.user_data.get('buy_product')

    if not product:
        await update.message.reply_text("Pehle /start bhej kar product select karein.")
        return ConversationHandler.END

    await update.message.reply_text("⏳ **Verifying TxID with Binance...**")
    is_valid, msg = verify_binance_deposit(user_txid, product['price'])

    if is_valid:
        delivery_text = f"🎉 **PAYMENT SUCCESSFUL!**\n\n📦 **{product['name']}**\n\n📝 Details:\n{product['desc']}"
        await update.message.reply_text(delivery_text, parse_mode="Markdown")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ **NEW ORDER!**\nUser: @{update.effective_user.username}\nProduct: {product['name']}")
    else:
        await update.message.reply_text(f"❌ **Failed:** {msg}\nSupport: @{SUPPORT_USERNAME}")

    return ConversationHandler.END

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text(f"🚫 Access Denied. Your ID: {user_id}")
        return

    keyboard = [
        [InlineKeyboardButton("➕ Add Product", callback_data="admin_add")],
        [InlineKeyboardButton("❌ Delete Product", callback_data="admin_delete")],
        [InlineKeyboardButton("📦 View Products", callback_data="admin_view")]
    ]
    await update.message.reply_text("⚙️ **NBK Digital Mart Admin Panel**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID: return
    await query.answer()

    if query.data == "admin_view":
        prods = load_products()
        text = "📦 **Products:**\n\n" + "\n".join([f"• {p['name']} - ${p['price']}" for p in prods.values()]) if prods else "Store khali hai."
        await query.message.reply_text(text)

    elif query.data == "admin_delete":
        prods = load_products()
        if not prods:
            await query.message.reply_text("Koi product nahi hai.")
            return
        keyboard = [[InlineKeyboardButton(f"❌ Delete {p['name']}", callback_data=f"del_{p_id}")] for p_id, p in prods.items()]
        await query.message.reply_text("Select product to delete:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("del_"):
        p_id = query.data.split("_")[1]
        prods = load_products()
        if p_id in prods:
            name = prods[p_id]['name']
            del prods[p_id]
            save_products(prods)
            await query.message.reply_text(f"✅ {name} deleted!")

async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Product ka **Name** likhein:")
    return ADD_NAME

async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_name'] = update.message.text
    await update.message.reply_text("Price (USDT) likhein:")
    return ADD_PRICE

async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_price'] = update.message.text
    await update.message.reply_text("Delivery Details/Link likhein:")
    return ADD_DESC

async def add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prods = load_products()
    new_id = str(len(prods) + 1)
    prods[new_id] = {
        "name": context.user_data['new_name'],
        "price": context.user_data['new_price'],
        "desc": update.message.text
    }
    save_products(prods)
    await update.message.reply_text(f"🎉 **{context.user_data['new_name']}** added!")
    return ConversationHandler.END

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

def main():
    app_bot = Application.builder().token(BOT_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("admin", admin_panel))
    app_bot.add_handler(CommandHandler("cancel", cancel_cmd))

    buy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(btn_buy, pattern="^buy_")],
        states={WAIT_TXID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_txid)]},
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
        allow_reentry=True
    )

    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add, pattern="^admin_add$")],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_price)],
            ADD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_desc)]
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
        allow_reentry=True
    )

    app_bot.add_handler(buy_conv)
    app_bot.add_handler(add_conv)
    app_bot.add_handler(CallbackQueryHandler(admin_callback, pattern="^(admin_view|admin_delete|del_.*)$"))

    print("Bot is starting polling...")
    app_bot.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
