import os
import json
import logging
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

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- ENVIRONMENT VARIABLES ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8882711271:AAGpU6Qac3EFqQ1nioWamAT-eTdT5wPM6QE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8736699831"))

PRODUCTS_FILE = "products.json"

DEFAULT_PRODUCTS = {
    "canva": {"name": "🎨 Canva Pro (Team Invite)", "price": "PKR 300", "desc": "Official team invite link for your personal email."},
    "chatgpt": {"name": "⚡ ChatGPT Plus (Private)", "price": "PKR 1500", "desc": "GPT-4o & DALL-E access."},
    "gemini": {"name": "♊ Gemini Advanced", "price": "PKR 1200", "desc": "1 Month Google One AI Premium."},
    "claude": {"name": "🧠 Claude Pro", "price": "PKR 1800", "desc": "Claude 3.5 Sonnet high limit access."}
}

PAYMENT_INFO = """
💳 **NBK Digital Mart Payment Details:**

• **EasyPaisa:** `0302 3573104`
  **Account Name:** NBK Digital Mart

• **Binance ID:** `1268122651`

⚠️ Payment karne ke baad receipt/screenshot yahan send karein!
"""

# Helper Functions for Data Persistence
def load_products():
    if not os.path.exists(PRODUCTS_FILE):
        save_products(DEFAULT_PRODUCTS)
        return DEFAULT_PRODUCTS
    try:
        with open(PRODUCTS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_PRODUCTS

def save_products(products):
    with open(PRODUCTS_FILE, "w") as f:
        json.dump(products, f, indent=4)

# States for Conversations
WAITING_FOR_RECEIPT = 1
ADD_NAME, ADD_PRICE, ADD_DESC = 2, 3, 4

# --- USER HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("🛒 Browse Products", callback_data="browse")],
        [InlineKeyboardButton("📞 Support / Contact", callback_data="support")]
    ]
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])

    await update.message.reply_text(
        f"AOA {user.first_name}! 👋\nWelcome to **NBK Digital Mart**.\nNiche diye gaye buttons se browse karein:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    products = load_products()

    if data == "browse" or data == "start_menu":
        keyboard = []
        for key, item in products.items():
            keyboard.append([InlineKeyboardButton(f"{item['name']} - {item['price']}", callback_data=f"buy_{key}")])
        keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])
        await query.edit_message_text("🛒 Select product to buy:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "main_menu":
        keyboard = [
            [InlineKeyboardButton("🛒 Browse Products", callback_data="browse")],
            [InlineKeyboardButton("📞 Support / Contact", callback_data="support")]
        ]
        if query.from_user.id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
        await query.edit_message_text(" Main Menu:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("buy_"):
        key = data.replace("buy_", "")
        if key in products:
            prod = products[key]
            context.user_data["selected_product"] = prod["name"]
            text = f"📦 **{prod['name']}**\n💰 Price: {prod['price']}\n📝 {prod.get('desc', '')}\n\n{PAYMENT_INFO}"
            await query.edit_message_text(text, parse_mode="Markdown")
            await query.message.reply_text("Please payment karne ke baad **Screenshot/Receipt** bhej dein.")
            return WAITING_FOR_RECEIPT

    elif data == "support":
        await query.edit_message_text("📞 Contact Support: @YourUsername\nFor immediate assistance contact admin.")

    elif data == "admin_panel" and query.from_user.id == ADMIN_ID:
        await show_admin_menu(query)

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    prod_name = context.user_data.get("selected_product", "Subscription Item")
    
    admin_msg = (
        f"🚨 **New Payment Receipt Received!**\n\n"
        f"👤 User: {user.first_name} (@{user.username})\n"
        f"🆔 User ID: `{user.id}`\n"
        f"📦 Product: {prod_name}\n\n"
        f"To deliver run:\n`/deliver {user.id} ACCOUNT_DETAILS`"
    )

    if update.message.photo:
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=update.message.photo[-1].file_id, caption=admin_msg, parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="Markdown")

    await update.message.reply_text(" Shukriya! Aapki receipt admin ko bhej di gayi hai. Verification ke baad product deliver kar di jayegi.")
    return ConversationHandler.END

# --- ADMIN FUNCTIONS ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    keyboard = [
        [InlineKeyboardButton("➕ Add Product", callback_data="admin_add")],
        [InlineKeyboardButton("❌ Delete Product", callback_data="admin_del_list")],
        [InlineKeyboardButton("📦 View Products", callback_data="browse")]
    ]
    await update.message.reply_text("⚙️ **NBK Digital Mart Admin Panel**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_admin_menu(query):
    keyboard = [
        [InlineKeyboardButton("➕ Add Product", callback_data="admin_add")],
        [InlineKeyboardButton("❌ Delete Product", callback_data="admin_del_list")],
        [InlineKeyboardButton("📦 View Products", callback_data="browse")]
    ]
    await query.edit_message_text("⚙️ **NBK Digital Mart Admin Panel**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Nayi product ka **Name** likhein (e.g. Canva Pro 1 Year):")
    return ADD_NAME

async def admin_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_prod_name"] = update.message.text
    await update.message.reply_text("Product ki **Price** likhein (e.g. PKR 500 / $2):")
    return ADD_PRICE

async def admin_add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_prod_price"] = update.message.text
    await update.message.reply_text("Product ki **Short Description** likhein:")
    return ADD_DESC

async def admin_add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text
    name = context.user_data["new_prod_name"]
    price = context.user_data["new_prod_price"]
    key = name.lower().replace(" ", "_")[:15]

    products = load_products()
    products[key] = {"name": name, "price": price, "desc": desc}
    save_products(products)

    await update.message.reply_text(f" Product **{name}** successfully add ho gayi hai!")
    return ConversationHandler.END

async def deliver_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        user_id = int(context.args[0])
        details = " ".join(context.args[1:])
        await context.bot.send_message(chat_id=user_id, text=f"🎉 **Order Delivered!**\n\nDetails:\n`{details}`", parse_mode="Markdown")
        await update.message.reply_text(" Successfully delivered.")
    except Exception:
        await update.message.reply_text("Format: `/deliver USER_ID DETAILS`")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    receipt_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^buy_")],
        states={WAITING_FOR_RECEIPT: [MessageHandler(filters.PHOTO | filters.TEXT, handle_receipt)]},
        fallbacks=[]
    )

    add_prod_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_start, pattern="^admin_add$")],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_name)],
            ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_price)],
            ADD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_desc)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("deliver", deliver_cmd))
    app.add_handler(receipt_handler)
    app.add_handler(add_prod_handler)
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
