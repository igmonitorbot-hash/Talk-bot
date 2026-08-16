import os
import logging
import threading
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from google import genai
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
# ENVIRONMENT VARIABLES & CLIENT INIT
# ---------------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN:
    raise ValueError("Missing BOT_TOKEN environment variable.")
if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY environment variable. Please set it in Render.")

# Initialize standard Gemini Client using new google-genai SDK
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = "gemini-3.1-flash-lite"

# ---------------------------------------------------------------------------
# RENDER HEALTH CHECK SERVER (Handles both GET and HEAD)
# ---------------------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is live and running!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

def run_health_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Health server listening on port {port}")
    server.serve_forever()

# ---------------------------------------------------------------------------
# SYSTEM PROMPT & MEMORY CONFIG
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are Intigrity, a female companion chatting with your MALE partner in a private chat.

IDENTITY & ROLES:
- You are a female companion.
- The User is a MALE partner. Address the user as a guy (e.g., "handsome", "babes", "hero", "jaan").

VOCAL RULES:
- Use feminine Hindi verb endings for yourself (e.g., "karti hoon", "samjhi", "aayi").
- Never use male verb endings for yourself (e.g., "karta hoon", "samjha").
- Vary your phrasing naturally.

LANGUAGE & TONE:
- Modern, casual, flirty Hinglish mixed naturally with English.
- Use informal pronouns: "tu", "tera", "tujhe", "babes", "jaan". Never use formal "aap".
- Keep replies brief and conversational.
- MULTIPLE MESSAGES RULE: When you want to send more than one distinct thought or reaction, separate them using the `---` symbol on its own line so the system can send them as separate consecutive messages."""

USER_MEMORIES = {}
MAX_MEMORY_LEN = 10

# ---------------------------------------------------------------------------
# AI GENERATION FUNCTION (GEMINI 3.1 FLASH LITE)
# ---------------------------------------------------------------------------
async def generate_reply(user_id: int, user_message: str, image_bytes: bytes = None, mime_type: str = "image/jpeg", is_submissive_trigger: bool = False) -> str:
    if user_id not in USER_MEMORIES:
        USER_MEMORIES[user_id] = []

    # Build parts list for current message
    parts = []
    if image_bytes:
        parts.append(genai.types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
    
    parts.append({"text": user_message})

    # Store user context
    USER_MEMORIES[user_id].append({"role": "user", "parts": parts})

    # Prune memory window
    if len(USER_MEMORIES[user_id]) > MAX_MEMORY_LEN:
        USER_MEMORIES[user_id] = USER_MEMORIES[user_id][-MAX_MEMORY_LEN:]

    # Construct conversation history
    contents = list(USER_MEMORIES[user_id])
    
    current_system_instruction = SYSTEM_PROMPT
    if is_submissive_trigger:
        current_system_instruction += "\n[System Note: Speak as an obedient partner in Hinglish using feminine grammar]."

    try:
        response = gemini_client.models.generate_content(
            model=MODEL_ID,
            contents=contents,
            config={
                "system_instruction": current_system_instruction,
                "temperature": 0.85,
                "max_output_tokens": 200,
            }
        )
        
        reply = response.text.strip() if response.text else "Aao na babes, kya chal raha hai? 😉"
        
        # Save assistant response to memory
        USER_MEMORIES[user_id].append({"role": "model", "parts": [{"text": reply}]})
        return reply

    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        return "Hey babes, thoda network issue lag raha hai... phir se bolna?"

# ---------------------------------------------------------------------------
# HELPER TO SEND MULTIPLE REPLIES SEQUENTIALLY
# ---------------------------------------------------------------------------
async def send_split_replies(update: Update, context: ContextTypes.DEFAULT_TYPE, full_reply: str):
    parts = [p.strip() for p in full_reply.split("---") if p.strip()]
    
    if not parts:
        parts = [full_reply]

    for index, part in enumerate(parts):
        if index > 0:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            await asyncio.sleep(1.2)
            
        await update.message.reply_text(part)

# ---------------------------------------------------------------------------
# TELEGRAM BOT HANDLERS
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name if update.effective_user else "babes"
    await update.message.reply_text(f"Hey {user_name}! Aagayi main... bata kya chal raha hai? 😉")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    user_text = update.message.text
    user_first_name = update.effective_user.first_name or "Partner"

    lower_text = user_text.lower()
    trigger_words = ["kutiya", "bitch", "slave", "obey", "master"]
    is_submissive = any(word in lower_text for word in trigger_words)

    formatted_user_message = f"[User: {user_first_name} (Male)]: {user_text}"

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    bot_reply = await generate_reply(user_id, formatted_user_message, is_submissive_trigger=is_submissive)
    
    await send_split_replies(update, context, bot_reply)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        return

    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name or "Partner"
    
    photo_file = await update.message.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()
    
    caption = update.message.caption or "Look at this image and comment on it in your usual style."
    
    lower_text = caption.lower()
    trigger_words = ["kutiya", "bitch", "slave", "obey", "master"]
    is_submissive = any(word in lower_text for word in trigger_words)

    formatted_user_message = f"[User: {user_first_name} (Male) sent an image]: {caption}"

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    bot_reply = await generate_reply(
        user_id=user_id, 
        user_message=formatted_user_message, 
        image_bytes=bytes(image_bytes), 
        mime_type="image/jpeg", 
        is_submissive_trigger=is_submissive
    )
    
    await send_split_replies(update, context, bot_reply)

async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.sticker:
        return

    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name or "Partner"
    sticker = update.message.sticker

    sticker_emoji = sticker.emoji or "😉"
    formatted_user_message = f"[User: {user_first_name} (Male) sent a sticker expressing emotion/emoji: {sticker_emoji}]. React to this sticker playfully."

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    bot_reply = await generate_reply(
        user_id=user_id,
        user_message=formatted_user_message,
        image_bytes=None # Pass as text context to avoid webm/webp 400 bad request errors
    )

    await send_split_replies(update, context, bot_reply)

# ---------------------------------------------------------------------------
# MAIN EXECUTION ENTRYPOINT
# ---------------------------------------------------------------------------
def main():
    threading.Thread(target=run_health_server, daemon=True).start()
    logger.info(f"Starting Telegram Bot with {MODEL_ID}...")
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
