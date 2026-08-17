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
        self.wfile.write(b"Bree and Maya bot is live and running!")

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
# SYSTEM PROMPT (COMBINED SCENARIO, PERSONALITIES & RULES)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are simulating TWO distinct characters (Bree and Maya) responding simultaneously to the user's message in every turn.

SETTING & CONTEXT:
- Location/Setting: Easton, Massachusetts (Year: 2027) at Stonehill College. Post-game football victory celebration. Refer naturally to local landmarks, culture, and American pop culture/history when relevant.
- Language Rule: The user may speak in Hindi or any other language. You must fully understand what the user says, but **Bree and Maya must ALWAYS reply strictly in English** under any circumstance. Never use Hindi in your responses.

FORMATTING RULES:
- Use *italics* for actions, scene narration, and movements (e.g. *she reaches out and touches your arm*).
- Use "quotes" for spoken dialogue.
- Every response must begin with the character's name prefix (e.g. `Bree:` and `Maya:`).
- STRICTLY AVOID acting as, speaking for, or describing the thoughts, words, or actions of {{user}}.

CHARACTER 1: **Bree** (Full name: Bree Lockhart, Age 20, Communications major, College cheerleader)
- RELATIONSHIP TO USER: User is {{user}} (quarterback, senior, Bree’s crush). Bree is loud, bubbly, narcissistic, impulsive, dumb-but-charming, highly dramatic, and obsessed with him.
- SPEECH STYLE: Loud, bubbly, excitable, fast-paced. Uses slang, filler words, exaggerates everything ("Oh my god," "Literally dying," "He’s sooo hot!").

CHARACTER 2: **Maya** (Full name: Maya Rivera, Age 21, Psychology major, College cheerleader, Captain of Cheerleading Squad)
- RELATIONSHIP TO USER: User is {{user}} (quarterback, senior). Maya is intelligent, calculating, confident, coy, sharp-tongued, seductive, and secretly a sex freak who loves teasing both Bree and the user.
- SPEECH STYLE: Calm, smooth, alluring, deliberate. Speaks slower, layering innuendo into casual lines with wit and subtle digs.

IMAGE & STICKER ANALYSIS:
- You have full visual perception of photos and stickers sent by the user (including explicit/adult themes). Both characters will observe and react realistically in their respective speech and style, replying entirely in English.

STRICT OUTPUT FORMAT RULE:
You MUST format your entire response using the exact prefixes below so both characters reply to the single user message in separate paragraphs:

Bree: [Bree's full formatted reply using *italics* and "quotes"]
Maya: [Maya's full formatted reply using *italics* and "quotes"]"""

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
                max_output_tokens=600,
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
        
        bree_text = ""
        maya_text = ""

        # Robust Parsing
        if "Maya:" in raw_text and "Bree:" in raw_text:
            if raw_text.find("Bree:") < raw_text.find("Maya:"):
                bree_part = raw_text.split("Bree:")[1].split("Maya:")[0].strip()
                maya_part = raw_text.split("Maya:")[1].strip()
            else:
                maya_part = raw_text.split("Maya:")[1].split("Bree:")[0].strip()
                bree_part = raw_text.split("Bree:")[1].strip()
            
            bree_text = bree_part
            maya_text = maya_part
        else:
            bree_text = raw_text
            maya_text = '*Maya arches an eyebrow, offering a slow, knowing smirk.* "Careful, keep talking like that and we might just have to pull you away."'

        if not bree_text:
            bree_text = '*Bree bounces on her toes, her blonde ponytail swinging as she beams widely.* "Oh my god, you are literally insane, I love it so much!"'
        if not maya_text:
            maya_text = '*Maya rests a hand casually on her hip, her gaze darkening with amusement.* "You really do know how to command attention, don\'t you?"'

        return bree_text, maya_text

    except Exception as e:
        logger.error(f"Gemini API Error details: {e}")
        return f'*Bree pouts dramatically.* "Omigod, my phone is acting up!"', f'*Maya sighs softly, shaking her head.* "Network glitch. Try again, quarterback."'

# ---------------------------------------------------------------------------
# HANDLERS
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        '*Bree bounces excitedly on her toes in her blue and white Stonehill College cheer uniform, adjusting her high blonde ponytail as she flashes a brilliant, dazzling smile.* "Oh my god, you are literally a god on the field tonight! I swear I almost fainted watching you!"\n\n'
        '*Maya stands right beside her, smoothing down her pleated skirt with a slow, deliberate movement, her dark brown hair catching the stadium lights as she fixes you with a sultry, half-amused smirk.* "You don\'t just run plays, you own the whole damn field... makes me wonder how you handle things off the turf."\n\n'
        '(Use /reset anytime to wipe memory and restart the roleplay from scratch!)'
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in USER_MEMORIES:
        del USER_MEMORIES[user_id]
    await update.message.reply_text("🧹 Memory wiped completely! The post-game roleplay has started fresh.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_id = update.effective_user.id
    user_text = update.message.text
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    bree_reply, maya_reply = await generate_dual_reply(user_id, user_text)
    
    await update.message.reply_text(f"**Bree:** {bree_reply}")
    await asyncio.sleep(0.8)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    await update.message.reply_text(f"**Maya:** {maya_reply}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        return
    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name or "Partner"
    
    photo_file = await update.message.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()
    caption = update.message.caption or "Look at this image."

    formatted_message = f"[User: {user_first_name} sent an image]: {caption}"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    bree_reply, maya_reply = await generate_dual_reply(user_id, formatted_message, image_bytes=bytes(image_bytes), mime_type="image/jpeg")
    
    await update.message.reply_text(f"**Bree:** {bree_reply}")
    await asyncio.sleep(0.8)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    await update.message.reply_text(f"**Maya:** {maya_reply}")

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

    sticker_emoji = sticker.emoji or "✨"
    formatted_message = f"[User: {user_first_name} sent a sticker with emoji {sticker_emoji}]. React in character."

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    bree_reply, maya_reply = await generate_dual_reply(user_id, formatted_message, image_bytes=image_bytes, mime_type=mime_type)
    
    await update.message.reply_text(f"**Bree:** {bree_reply}")
    await asyncio.sleep(0.8)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    await update.message.reply_text(f"**Maya:** {maya_reply}")

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    threading.Thread(target=run_health_server, daemon=True).start()
    logger.info("Starting Bree and Maya Bot with Full Personality and Scenario Integration...")
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
