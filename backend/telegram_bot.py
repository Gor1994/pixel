from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pymongo import MongoClient
from datetime import datetime
import random
import asyncio

# Telegram Bot Token
TELEGRAM_APP_TOKEN = "8076325725:AAHqtb8Z7mJu56NEceWYtLTvD1h-2rI3_Wg"

# MongoDB Configuration
MONGO_URI = 'mongodb+srv://nershakobyan:QkmcuOAhHba7C4q8@cluster0.1rwwk.mongodb.net/Grid_Game?retryWrites=true&w=majority'
client = MongoClient(MONGO_URI)
db = client["Grid_Game"]
users_collection = db["users"]

# Generate random color
def generate_random_color_hex():
    return f"#{random.randint(0, 0xFFFFFF):06x}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command to store Telegram user details and initialize energy."""
    telegram_user_id = update.effective_user.id
    telegram_username = update.effective_user.username or "Unknown"
    print(f"Handling /start command for user {telegram_user_id}...")

    initial_energy = {
        "charges": 4,
        "clicks_per_charge": 500,
        "last_click_timestamp": datetime.utcnow(),
        "last_recharge_timestamp": datetime.utcnow(),
    }

    random_color_hex = generate_random_color_hex()

    existing_user = users_collection.find_one({"telegram_user_id": telegram_user_id})

    if existing_user:
        await update.message.reply_text(f"Welcome back, {telegram_username}!")
        update_fields = {}
        if "energy" not in existing_user:
            update_fields["energy"] = initial_energy
        if "color" not in existing_user:
            update_fields["color"] = random_color_hex
        if update_fields:
            users_collection.update_one(
                {"telegram_user_id": telegram_user_id},
                {"$set": update_fields}
            )
            await update.message.reply_text("Your profile has been updated!")
    else:
        user_data = {
            "telegram_user_id": telegram_user_id,
            "telegram_username": telegram_username,
            "registered_at": datetime.utcnow().isoformat(),
            "energy": initial_energy,
            "color": random_color_hex,
        }
        users_collection.insert_one(user_data)
        await update.message.reply_text(
            f"Welcome, {telegram_username}! Your energy system and profile color are ready."
        )

def run_telegram_bot():
    """Run the Telegram bot."""
    application = Application.builder().token(TELEGRAM_APP_TOKEN).build()
    application.add_handler(CommandHandler("start", start))

    print("Starting Telegram bot...")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(application.run_polling())

if __name__ == "__main__":
    run_telegram_bot()
