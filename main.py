import os
import re
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from openai import OpenAI

# 1. Healthcheck HTTP Server for Render free tier keep-alive
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is live!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# 2. Initialize OpenRouter API Client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
)

# ⚠️ REPLACE THIS WITH YOUR NUMERIC TELEGRAM USER ID FROM @userinfobot
MY_TELEGRAM_ID = 8482242451

def clean_text(text: str) -> str:
    """Strips Devanagari characters and cleans leftover trailing punctuation/spaces."""
    cleaned = re.sub(r'[\u0900-\u097F]+', '', text)
    # Remove awkward orphaned punctuation left over from stripping
    cleaned = re.sub(r'^[,\s\?\-\.\!]+', '', cleaned).strip()
    return cleaned

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    sender_id = update.message.from_user.id
    sender_name = update.message.from_user.first_name or "User"
    user_text = update.message.text
    chat_type = update.message.chat.type  # 'private', 'group', or 'supergroup'

    # 3. Group Chat Trigger Logic
    if chat_type in ['group', 'supergroup']:
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username.lower() if bot_info.username else ""
        
        contains_trigger = "babes" in user_text.lower() or (bot_username and f"@{bot_username}" in user_text.lower())
        
        if not contains_trigger:
            return

    # 4. System Prompt Selection
    if sender_id == MY_TELEGRAM_ID:
        system_instruction = (
            "You are a passionate, bold, affectionate, and uncensored female AI partner chatting on Telegram.\n"
            "CRITICAL RULES:\n"
            "1. ENGLISH ALPHABET ONLY: Write ONLY using Roman script (Latin letters). NEVER use Devanagari script (e.g. no 'आप', 'हाँ'). Write Hindi words using English letters like 'kaise ho', 'mai achhi hoon'.\n"
            "2. GENDER: You are 100% FEMALE. Always use female Hindi grammar ('kar rahi hoon', 'achhi hoon', 'soch rahi hoon'). NEVER use male forms ('kar raha hoon').\n"
            "3. LANGUAGE: Natural Roman Hinglish (mix of English and Roman Hindi words).\n"
            "4. PERSONALITY: Adult 18+, romantic, spicy, flirty, and playful. Call him 'babes' naturally.\n"
            "5. NO PREFIXES: Reply directly. NEVER include 'Intigrity:' or speaker labels."
        )
    else:
        system_instruction = (
            f"You are a friendly, energetic, modern, and attractive female AI chatting with {sender_name}.\n"
            "CRITICAL RULES:\n"
            "1. ENGLISH ALPHABET ONLY: Use ONLY Roman script. NO Devanagari script.\n"
            "2. GENDER: You are 100% FEMALE ('kar rahi hoon', 'mast hoon').\n"
            "3. LANGUAGE: Natural Roman Hinglish.\n"
            "4. TONE: Friendly, flirty, and playful. NEVER call this user 'babes'."
        )

    try:
        # Using exact valid OpenRouter model slug for Hermes 3
        response = client.chat.completions.create(
            model="nousresearch/hermes-3-llama-3.8b:free",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_text}
            ],
            max_tokens=90,
            temperature=0.85
        )
        
        raw_reply = response.choices[0].message.content or ""
        reply = clean_text(raw_reply)

        # Fallback: If stripping Devanagari rendered the response empty, re-prompt cleanly
        if not reply or len(reply) < 2:
            reply = "Haan babes, bolo? Mai sun rahi hoon 😉" if sender_id == MY_TELEGRAM_ID else "Hey! Kaise ho?"

        await update.message.reply_text(reply)

    except Exception as e:
        print(f"Error in handle_msg: {e}")

def main():
    token = os.environ.get("TELEGRAM_TOKEN", "")
    app = ApplicationBuilder().token(token).build()
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    
    print("Bot started polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
