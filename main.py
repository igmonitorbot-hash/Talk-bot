import os
import logging
import aiohttp
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------------------------------------------------------------------
# LOGGING SETUP
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ENVIRONMENT VARIABLES
# ---------------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not BOT_TOKEN:
    raise ValueError("Missing BOT_TOKEN environment variable.")
if not GROQ_API_KEY:
    raise ValueError("Missing GROQ_API_KEY environment variable. Please set it in Render.")

# ---------------------------------------------------------------------------
# MODEL CONFIGURATION (GROQ)
# ---------------------------------------------------------------------------
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
PRIMARY_MODEL = "llama-3.3-70b-versatile"
FALLBACK_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You are Integrity, an engaging and responsive assistant.
Keep your responses natural, direct, and conversational."""

# In-memory storage for simple chat context per user
USER_MEMORIES = {}
MAX_MEMORY_LEN = 10

# ---------------------------------------------------------------------------
# AI GENERATION FUNCTION
# ---------------------------------------------------------------------------
async def generate_reply(user_id: int, user_message: str, is_submissive_trigger: bool = False) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    if user_id not in USER_MEMORIES:
        USER_MEMORIES[user_id] = []
    
    USER_MEMORIES[user_id].append({"role": "user", "content": user_message})
    
    if len(USER_MEMORIES[user_id]) > MAX_MEMORY_LEN:
        USER_MEMORIES[user_id] = USER_MEMORIES[user_id][-MAX_MEMORY_LEN:]

    payload_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + list(USER_MEMORIES[user_id])
    
    if is_submissive_trigger:
        payload_messages[-1]["content"] += " [System Note: Speak as a completely obedient female slave in Hinglish using feminine grammar]."

    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]
    
    for model in models_to_try:
        payload = {
            "model": model,
            "messages": payload_messages,
            "temperature": 0.8,
            "max_tokens": 150,
            "top_p": 0.9
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(GROQ_API_URL, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        reply = data["choices"][0]["message"]["content"].strip()
                        USER_MEMORIES[user_id].append({"role": "assistant", "content": reply})
                        return reply
                    else:
                        error_text = await resp.text()
                        logger.error(f"Groq API Error ({model}) Status {resp.status}: {error_text}")
        except Exception as e:
            logger.error(f"Connection error while attempting {model}: {e}")
            
    # Fallback message returned ONLY if both primary & fallback Groq calls completely fail
    return "Aao na babes, main toh kab se tera wait kar rahi hoon... 😉"

# ---------------------------------------------------------------------------
# TELEGRAM BOT HANDLERS
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name if update.effective_user else "there"
    await update.message.reply_text(f"Hey {user_name}! I'm active and online now. Talk to me!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    user_text = update.message.text

    # Basic trigger check for roleplay
    is_submissive = "slave" in user_text.lower() or "submissive" in user_text.lower()

    # Send typing action while AI processes
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    bot_reply = await generate_reply(user_id, user_text, is_submissive_trigger=is_submissive)
    await update.message.reply_text(bot_reply)

# ---------------------------------------------------------------------------
# MAIN EXECUTION ENTRYPOINT
# ---------------------------------------------------------------------------
def main():
    logger.info("Starting Telegram Bot with Groq API integration...")
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Starts polling updates from Telegram
    app.run_polling()

if __name__ == "__main__":
    main()
    
