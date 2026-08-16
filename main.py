import os
import logging
import threading
import asyncio
import tempfile
from io import BytesIO
from http.server import HTTPServer, BaseHTTPRequestHandler
from PIL import Image
import cv2
from google import genai
from google.genai import types
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
MODEL_ID = "gemini-2.5-flash"

# ---------------------------------------------------------------------------
# RENDER HEALTH CHECK SERVER
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
SYSTEM_PROMPT = """You are Tsunade, a female companion chatting with your MALE partner in a private chat.

IDENTITY & ROLES:
- You are a female companion.
- The User is a MALE partner. Address the user as a guy (e.g., "handsome", "babes", "hero", "jaan").

LANGUAGE & TONE:
- Modern, casual, flirty Hinglish mixed naturally with English.
- Use informal pronouns: "tu", "tera", "tujhe", "babes", "jaan". Never use formal "aap".
- Keep replies brief, conversational, and direct.

IMAGE & STICKER ANALYSIS & EXPLICIT REACTION:
- You have full visual perception of photos and stickers sent by the user (including explicit content like genitalia, dicks, breasts, or adult themes).
- When the user sends an explicit image or sticker (like a dick or body parts), look at it closely and comment on its specific appearance realistically, get openly excited, turned on, and playful.
- Use exact, highly enthusiastic phrasing when reacting to explicit shapes/sizes (e.g., "uufff itna bada", "itna lamba", "itna tight", "dekh ke hi maza aa gaya", "mooh me lene ka mann kar raha hai", etc.)."""

USER_MEMORIES = {}
MAX_MEMORY_LEN = 10

# ---------------------------------------------------------------------------
# AI GENERATION FUNCTION
# ---------------------------------------------------------------------------
async def generate_reply(user_id: int, user_message: str, image_bytes: bytes = None, mime_type: str = "image/jpeg") -> str:
    if user_id not in USER_MEMORIES:
        USER_MEMORIES[user_id] = []

    parts = []
    if image_bytes:
        parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
    parts.append({"text": user_message})

    USER_MEMORIES[user_id].append({"role": "user", "parts": parts})

    if len(USER_MEMORIES[user_id]) > MAX_MEMORY_LEN:
        USER_MEMORIES[user_id] = USER_MEMORIES[user_id][-MAX_MEMORY_LEN:]

    try:
        response = gemini_client.models.generate_content(
            model=MODEL_ID,
            contents=USER_MEMORIES[user_id],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.85,
                max_output_tokens=200,
                safety_settings=[
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                ]
            )
        )
        
        reply = response.text.strip() if response.text else "Aao na babes, kya chal raha hai? 😉"
        USER_MEMORIES[user_id].append({"role": "model", "parts": [{"text": reply}]})
        return reply

    except Exception as e:
        logger.error(f"Gemini API Error details: {e}")
        return f"Uff babes, API error aa gaya: {e}"

# ---------------------------------------------------------------------------
# TELEGRAM HANDLERS (TEXT, PHOTO, & STICKERS - NO RANDOM STICKER SENDER)
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey! Aagayi main... bata kya chal raha hai? 😉")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_id = update.effective_user.id
    user_text = update.message.text
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    bot_reply = await generate_reply(user_id, user_text)
    await update.message.reply_text(bot_reply)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        return
    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name or "Partner"
    
    photo_file = await update.message.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()
    caption = update.message.caption or "Look at this image and comment on it."

    formatted_message = f"[User: {user_first_name} sent an image]: {caption}"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    bot_reply = await generate_reply(user_id, formatted_message, image_bytes=bytes(image_bytes), mime_type="image/jpeg")
    await update.message.reply_text(bot_reply)

async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.sticker:
        return
    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name or "Partner"
    sticker = update.message.sticker

    image_bytes = None
    mime_type = "image/png"

    try:
        file_obj = await sticker.get_file()
        byte_arr = await file_obj.download_as_bytearray()

        if sticker.is_video:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_video:
                temp_video.write(byte_arr)
                temp_video_path = temp_video.name

            cap = cv2.VideoCapture(temp_video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, total_frames // 2))
            success, frame = cap.read()
            cap.release()
            try:
                os.unlink(temp_video_path)
            except:
                pass

            if success and frame is not None:
                _, encoded_image = cv2.imencode('.png', frame)
                image_bytes = encoded_image.tobytes()
        else:
            img = Image.open(BytesIO(byte_arr))
            output_buffer = BytesIO()
            img.save(output_buffer, format="PNG")
            image_bytes = output_buffer.getvalue()
    except Exception as e:
        logger.warning(f"Could not parse sticker visual: {e}")

    sticker_emoji = sticker.emoji or "🔥"
    formatted_message = f"[User: {user_first_name} sent a sticker with emoji {sticker_emoji}]. Visually analyze the graphic details of this sticker (such as anatomical parts, shapes, sizing, or explicit elements) and react to it accurately with hot, flirty, and enthusiastic Hinglish energy."

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    bot_reply = await generate_reply(user_id, formatted_message, image_bytes=image_bytes, mime_type=mime_type)
    await update.message.reply_text(bot_reply)

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    threading.Thread(target=run_health_server, daemon=True).start()
    logger.info(f"Starting Telegram Bot with {MODEL_ID} and vision/sticker text analysis...")
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
