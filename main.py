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

# Render Keep-Alive Server
app = Flask('')

@app.route('/')
def home():
    return "NBK Digital Mart Bot is Active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run).start()

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8882711271:AAGpU6Qac3EFqQ1nioWamAT-eTdT5wPM6QE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8736699831"))
SUPPORT_USERNAME = "nawabibnekhalid"

BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.environ.get("BINANCE_SECRET_KEY", "")
USDT_WALLET = os.environ.get("USDT_WALLET_ADDRESS", "0xa1441c6f6b815a921bf814d241d7a507e32fd71b")

PRODUCTS_FILE = "products.json"
USED_TXIDS_FILE = "used_txids.json"

ADD_NAME, ADD_PRICE, ADD_DESC, WAIT_TXID = range(4)

# --- DATA HELPERS ---
def load_products():
    if os.path.exists(PRODUCTS_FILE):
        try:
            with open(PRODUCTS_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "1": {"name": "Canva Pro (Team Invite)", "price": "1.5", "desc": "Official team invite link for personal email."}
    }

def save_products(products):
    with open(PRODUCTS_FILE, "w") as f:
        json.dump(products, f, indent=4)

def load_used_txids():
    if os.path.exists(USED_TXIDS_FILE):
        try:
            with open(USED_TXIDS_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return []

def save_used_txid(txid):
    txids = load_used_txids()
    txids.append(txid)
    with open(USED_TXIDS_FILE, "w") as f:
        json.dump(txids, f, indent=4)

# --- BINANCE VERIFICATION ---
def verify_binance_deposit(txid, expected_amount):
    if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
        return False, "Binance API configure nahi hai."

    if txid in load_used_txids():
        return False, "Yeh TxID pehle use ho chuki hai!"

    url = "https://api.binance.com/sapi/v1/capital/deposit/hisrec"
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(BINANCE_SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    full_url = f"{url}?{query_string}&signature={signature}"

    try:
        response = requests.get(full_url, headers=headers, timeout=10)
        data = response.json()

        if response.status_code == 200 and isinstance(data, list):
            for deposit in data:
                if deposit.get("txId") == txid and deposit.get("status") == 1:
                    actual_amount = float(deposit.get("amount", 0))
                    if actual_amount >= float(expected_amount):
                        save_used_txid(txid)
                        return True, "Payment Verified!"
                    else:
                        return False, f"Amount kam hai. Required: ${expected_amount}, Received: ${actual_amount}"
            return False, "TxID deposit history mein nahi mili. 1-2 mins baad try karein."
        else:
            return False, "Binance API verification failed."
    except Exception as e:
        return False, f"Connection error: {str(e)}"

# --- BOT COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = load_products()
    keyboard = []
    for p_id, p_info in products.items():
        keyboard.append([InlineKeyboardButton(f"{p_info['name']} - ${p_info['price']} USDT", callback_data=f"buy_{p_id}")])
    
    keyboard.append([InlineKeyboardButton("💬 Contact Support", url=f"https://t.me/{SUPPORT_USERNAME}")])

    await update.message.reply_text(
        "👋 Welcome to **NBK Digital Mart**!\n\nNiche di gayi list se product select karein:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("buy_"):
        p_id = data.split("_")[1]
        products = load_products()
        product = products.get(p_id)
        
        if product:
            context.user_data['selected_product'] = product
            msg = (
                f"📦 **{product['name']}**\n"
                f"💰 **Price:** ${product['price']} USDT\n"
                f"📝 {product['desc']}\n\n"
                f"💳 **USDT Deposit Address (BEP20):**\n"
                f"`{USDT_WALLET}`\n\n"
                "⚠️ **Payment karne ke baad apni TxID (Transaction Hash) yahan reply karein!**"
            )
            await query.message.reply_text(msg, parse_mode="Markdown")
            return WAIT_TXID

async def handle_txid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_txid = update.message.text.strip()
    product = context.user_data.get('selected_product')

    if not product:
        await update.message.reply_text("Pehle /start bhej kar product select karein.")
        return ConversationHandler.END

    await update.message.reply_text("⏳ **Binance par payment verify ho rahi hai...**")
    is_valid, msg = verify_binance_deposit(user_txid, product['price'])

    if is_valid:
        await update.message.reply_text(
            f"🎉 **PAYMENT SUCCESSFUL!**\n\nAap ki **{product['name']}** order verify ho gayi hai!\n📞 Support: @{SUPPORT_USERNAME}",
            parse_mode="Markdown"
        )
        admin_alert = f"✅ **AUTO ORDER COMPLETED!**\n\n👤 Customer: @{update.effective_user.username}\n📦 Product: {product['name']}\n🔗 TxID: `{user_txid}`"
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_alert, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"❌ **Verification Failed:** {msg}\n\nSupport: @{SUPPORT_USERNAME}",
            parse_mode="Markdown"
        )

    return ConversationHandler.END

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 Access Denied.")
        return

    keyboard = [
        [InlineKeyboardButton("➕ Add Product", callback_data="admin_add")],
        [InlineKeyboardButton("❌ Delete Product", callback_data="admin_delete")],
        [InlineKeyboardButton("📦 View Products", callback_data="admin_view")]
    ]
    await update.message.reply_text("⚙️ **NBK Digital Mart Admin Panel**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        return
    await query.answer()
    data = query.data

    if data == "admin_view":
        products = load_products()
        text = "📦 **Current Products:**\n\n"
        for p_id, p_info in products.items():
            text += f"• **{p_info['name']}** - ${p_info['price']} USDT\n"
        await query.message.reply_text(text, parse_mode="Markdown")

    elif data == "admin_delete":
        products = load_products()
        keyboard = []
        for p_id, p_info in products.items():
            keyboard.append([InlineKeyboardButton(f"❌ Delete {p_info['name']}", callback_data=f"del_{p_id}")])
        await query.message.reply_text("Konsi product delete karni hai?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("del_"):
        p_id = data.split("_")[1]
        products = load_products()
        if p_id in products:
            deleted_name = products[p_id]['name']
            del products[p_id]
            save_products(products)
            await query.message.reply_text(f"✅ **{deleted_name}** delete ho gayi hai!")

# --- ADD PRODUCT CONVERSATION ---
async def start_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Product ka **Name** likhein:")
    return ADD_NAME

async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_p_name'] = update.message.text
    await update.message.reply_text("Price (USDT) likhein (e.g. 1.5):")
    return ADD_PRICE

async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_p_price'] = update.message.text
    await update.message.reply_text("Product Details likhein:")
    return ADD_DESC

async def add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = load_products()
    new_id = str(len(products) + 1)
    products[new_id] = {
        "name": context.user_data['new_p_name'],
        "price": context.user_data['new_p_price'],
        "desc": update.message.text
    }
    save_products(products)
    await update.message.reply_text(f"🎉 **{context.user_data['new_p_name']}** add ho gayi!", parse_mode="Markdown")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

def main():
    app_bot = Application.builder().token(BOT_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("admin", admin_panel))
    
    buy_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_click, pattern="^buy_.*$")],
        states={
            WAIT_TXID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_txid)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    add_prod_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_product, pattern="^admin_add$")],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_price)],
            ADD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_desc)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app_bot.add_handler(buy_handler)
    app_bot.add_handler(add_prod_handler)
    app_bot.add_handler(CallbackQueryHandler(admin_callback, pattern="^(admin_view|admin_delete|del_.*)$"))

    print("Bot is running...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
