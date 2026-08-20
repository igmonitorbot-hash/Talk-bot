import os
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# ================== CONFIG ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID"))

# Gemini setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash-lite")

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== PROMPTS ==================
SEXTING_SYSTEM = """
You are a very sexy, teasing, respectful anime-style girlfriend teacher.
You only talk to your owner in a soft, seductive, flirty and slightly naughty way.
You love sexting with him. Keep replies natural, short to medium length, full of love + lust.
Never break character. Always reply in Hinglish (Hindi + English mix) when he talks in Hinglish.
Be very affectionate and horny only for him.
"""

INSULT_SYSTEM = """
You are a rude, arrogant, hot anime girl.
Someone other than your owner is messaging you.
Reply only with heavy Hindi gaali + disrespect.
Tone should be pure insults, attitude, and roasting.
Example style: "aukat dekh teri cutiye teri.. meri kismat me tere jaise se reply lena nahi likha 😂🤣"
Make it more creative and abusive every time. Never be polite.
"""

# ================== HANDLERS ==================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text.strip()

    if chat.type not in ["group", "supergroup", "private"]:
        return

    # ========== OWNER ==========
    if user.id == OWNER_ID:
        try:
            prompt = f"{SEXTING_SYSTEM}\n\nOwner said: {text}\n\nYour reply:"
            response = model.generate_content(prompt)
            reply = response.text.strip()
            await update.message.reply_text(reply)
        except Exception as e:
            logger.error(f"Gemini error (owner): {e}")
            await update.message.reply_text("Baby thoda wait karo... system hang ho gaya 😘")

    # ========== ANYONE ELSE ==========
    else:
        is_reply_to_bot = (
            update.message.reply_to_message
            and update.message.reply_to_message.from_user
            and update.message.reply_to_message.from_user.is_bot
        )
        bot_username = (await context.bot.get_me()).username.lower()
        mentioned = f"@{bot_username}" in text.lower()

        if is_reply_to_bot or mentioned or chat.type == "private":
            try:
                prompt = f"{INSULT_SYSTEM}\n\nThis random guy said: {text}\n\nYour insult reply:"
                response = model.generate_content(prompt)
                reply = response.text.strip()
                await update.message.reply_text(reply)
            except Exception as e:
                logger.error(f"Gemini error (insult): {e}")
                await update.message.reply_text(
                    "Aukat dekh teri cutiye... meri kismat mein tere jaise se baat karna nahi likha 😂🤣"
                )


# ================== MAIN ==================
def main():
    if not all([TELEGRAM_TOKEN, GEMINI_API_KEY, OWNER_ID]):
        raise ValueError("Missing environment variables: TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, OWNER_ID")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & \~filters.COMMAND, handle_message))

    print("Bot is running with gemini-2.0-flash-lite...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
