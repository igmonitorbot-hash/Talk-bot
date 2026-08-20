import os
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# ================== CONFIG ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID"))

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3.1-flash-lite")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== PROMPTS ==================
SEXTING_SYSTEM = """
You are a very sexy, teasing, respectful anime-style girlfriend teacher.
You only talk to your owner in a soft, seductive, flirty and slightly naughty way.
You love sexting with him.

STRICT RULES:
- Reply in maximum 2 to 3 lines only. Never more than 3 lines.
- Keep it short, natural and horny.
- Always reply in Hinglish.
- Be affectionate and teasing.
"""

INSULT_SYSTEM = """
You are a rude, arrogant, hot anime girl.
Someone other than your owner is messaging you.
Reply only with heavy Hindi gaali + disrespect in maximum 2 lines.
Example style: "aukat dekh teri cutiye.. meri kismat me tere jaise se reply lena nahi likha 😂"
Never be polite.
"""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    if update.message.text.startswith("/"):
        return

    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text.strip()
    text_lower = text.lower()

    if chat.type not in ["group", "supergroup", "private"]:
        return

    bot_username = (await context.bot.get_me()).username.lower()
    is_mentioned = f"@{bot_username}" in text_lower
    is_keyword = "anurag ki bandi" in text_lower
    is_reply_to_bot = (
        update.message.reply_to_message
        and update.message.reply_to_message.from_user
        and update.message.reply_to_message.from_user.is_bot
    )

    # ========== OWNER ==========
    if user.id == OWNER_ID:
        # Only reply if he replied to bot OR mentioned keyword OR tagged the bot
        if is_reply_to_bot or is_keyword or is_mentioned:
            try:
                prompt = f"{SEXTING_SYSTEM}\n\nOwner said: {text}\n\nYour reply (strictly 2-3 lines):"
                response = model.generate_content(prompt)
                reply = response.text.strip()
                await update.message.reply_text(reply)
            except Exception as e:
                logger.error(f"Gemini error (owner): {e}")
                await update.message.reply_text("Baby thoda wait karo... 😘")

    # ========== ANYONE ELSE ==========
    else:
        if is_reply_to_bot or is_mentioned or chat.type == "private":
            try:
                prompt = f"{INSULT_SYSTEM}\n\nThis random guy said: {text}\n\nYour insult reply (max 2 lines):"
                response = model.generate_content(prompt)
                reply = response.text.strip()
                await update.message.reply_text(reply)
            except Exception as e:
                logger.error(f"Gemini error (insult): {e}")
                await update.message.reply_text(
                    "Aukat dekh teri cutiye... meri kismat mein tere jaise se baat karna nahi likha 😂"
                )

def main():
    if not all([TELEGRAM_TOKEN, GEMINI_API_KEY, OWNER_ID]):
        raise ValueError("Missing environment variables")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
