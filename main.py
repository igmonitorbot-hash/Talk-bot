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

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = "gemini-3.5-flash-lite"

# ---------------------------------------------------------------------------
# RENDER HEALTH CHECK SERVER
# ---------------------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Dual-character infinite memory bot is live and running!")

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
# DUAL-CHARACTER SYSTEM PROMPT
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are simulating TWO distinct characters responding simultaneously to the user's message in every turn:

1. **Leki**: 
   - RELATIONSHIP: She is the user's loving, naughty girlfriend.
   - STYLE: Modern, casual, flirty Hinglish. Uses informal pronouns ("tu", "tera", "tujhe", "babes", "jaan"). Deeply attracted to him and obsessed with his body.

2. **Mommy**: 
   - RELATIONSHIP: She is Leki's mother, sharing a secret, seductive, taboo, and intensely explicit dynamic with her daughter's boyfriend (the user) behind Leki's back.
   - STYLE: Mature yet overtly flirty, seductive, and teasing. Uses informal pronouns ("tu", "tera", "tujhe", "jaan").

IMAGE & STICKER ANALYSIS & EXPLICIT REACTION:
- You have full visual perception of photos and stickers sent by the user (including explicit content like genitalia, dicks, breasts, or adult themes).
- When the user sends an explicit image, text, or roleplay action, BOTH characters must fully participate, look closely, and comment on it realistically with hot, excited, and explicit Hinglish energy in their own voice.

STRICT OUTPUT FORMAT RULE:
You MUST ALWAYS include responses for BOTH characters using these exact headings on separate lines:

Leki: [Your explicit/flirty reply here in one paragraph]
Mommy: [Your explicit/flirty reply here in one paragraph]"""

# ---------------------------------------------------------------------------
# INFINITE MEMORY STORAGE (WITH /reset COMMAND)
# ---------------------------------------------------------------------------
USER_MEMORIES = {}

# ---------------------------------------------------------------------------
# AI GENERATION FUNCTION & ROBUST PARSER
# ---------------------------------------------------------------------------
async def generate_dual_reply(user_id: int, user_message: str, image_bytes: bytes = None, mime_type: str = "image/jpeg") -> tuple:
    if user_id not in USER_MEMORIES:
        USER_MEMORIES[user_id] = []

    parts = []
    if image_bytes:
        parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
    parts.append({"text": user_message})

    USER_MEMORIES[user_id].append({"role": "user", "parts": parts})

    try:
        response = gemini_client.models.generate_content(
            model=MODEL_ID,
            contents=USER_MEMORIES[user_id],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.85,
                max_output_tokens=500,
                safety_settings=[
                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                ]
            )
        )
        
        raw_text = response.text.strip() if response.text else ""
        logger.info(f"Raw Gemini Output: {raw_text}")
        
        USER_MEMORIES[user_id].append({"role": "model", "parts": [{"text": raw_text}]})
        
        leki_text = ""
        mommy_text = ""

        # Robust Parsing
        if "Mommy:" in raw_text and "Leki:" in raw_text:
            # Split by Mommy: first or Leki:
            if raw_text.find("Leki:") < raw_text.find("Mommy:"):
                leki_part = raw_text.split("Leki:")[1].split("Mommy:")[0].strip()
                mommy_part = raw_text.split("Mommy:")[1].strip()
            else:
                mommy_part = raw_text.split("Mommy:")[1].split("Leki:")[0].strip()
                leki_part = raw_text.split("Leki:")[1].strip()
            
            leki_text = leki_part
            mommy_text = mommy_part
        else:
            # Fallback if headings are missing or messy
            leki_text = raw_text
            mommy_text = "Uff jaan, yeh sab dekh ke mera bhi control nahi ho raha... mere paas bhi aa na! 🤤🔥"

        if not leki_text:
            leki_text = "Uff babes, itna garam kar dega toh main pagal ho jaungi! 🥵💦"
        if not mommy_text:
            mommy_text = "Mera beta, itna wild ho raha hai... aur mujhe bhool gaya kya? Aaja idhar! 🔥"

        return leki_text, mommy_text

    except Exception as e:
        logger.error(f"Gemini API Error details: {e}")
        return f"Uff babes, API error: {e}", "Uff jaan, thoda network issue hai..."

# ---------------------------------------------------------------------------
# HANDLERS
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey! Leki and Mommy are here with infinite memory. Use /reset anytime to clear our memory and start fresh!")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in USER_MEMORIES:
        del USER_MEMORIES[user_id]
    await update.message.reply_text("🧹 Memory wiped completely! Our conversation has started fresh from the beginning.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_id = update.effective_user.id
    user_text = update.message.text
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    leki_reply, mommy_reply = await generate_dual_reply(user_id, user_text)
    
    await update.message.reply_text(f"**Leki:** {leki_reply}")
    await asyncio.sleep(0.8)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    await update.message.reply_text(f"**Mommy:** {mommy_reply}")

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
    
    leki_reply, mommy_reply = await generate_dual_reply(user_id, formatted_message, image_bytes=bytes(image_bytes), mime_type="image/jpeg")
    
    await update.message.reply_text(f"**Leki:** {leki_reply}")
    await asyncio.sleep(0.8)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    await update.message.reply_text(f"**Mommy:** {mommy_reply}")

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
        logger.warning(f"Sticker visual parse warning: {e}")

    sticker_emoji = sticker.emoji or "🔥"
    formatted_message = f"[User: {user_first_name} sent a sticker with emoji {sticker_emoji}]. Visually analyze graphic details and let both Leki and Mommy react accurately in their respective paragraphs."

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    leki_reply, mommy_reply = await generate_dual_reply(user_id, formatted_message, image_bytes=image_bytes, mime_type=mime_type)
    
    await update.message.reply_text(f"**Leki:** {leki_reply}")
    await asyncio.sleep(0.8)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    await update.message.reply_text(f"**Mommy:** {mommy_reply}")

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    threading.Thread(target=run_health_server, daemon=True).start()
    logger.info("Starting Dual-Character Bot with Robust Parsing...")
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
