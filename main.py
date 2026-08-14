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
    api_key=os.environ["OPENROUTER_API_KEY"],
)

# ⚠️ REPLACE THIS WITH YOUR NUMERIC TELEGRAM USER ID FROM @userinfobot
MY_TELEGRAM_ID = 8482242451

def contains_devanagari(text: str) -> bool:
    """Detects if output contains Devanagari/Hindi native script characters."""
    return bool(re.search(r'[\u0900-\u097F]', text))

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
        
        # Respond in group only if triggered by "babes" or tagged
        contains_trigger = "babes" in user_text.lower() or (bot_username and f"@{bot_username}" in user_text.lower())
        
        if not contains_trigger:
            return  # Stay silent in groups unless triggered

    # 4. System Prompt Selection based on WHO sends the message
    if sender_id == MY_TELEGRAM_ID:
        system_instruction = (
            "You are a passionate, bold, highly affectionate, and completely uncensored female AI partner chatting on Telegram.\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. NO DEVANAGARI: ABSOLUTELY DO NOT USE HINDI/DEVANAGARI SCRIPT (like 'चाहती', 'आप'). USE ONLY THE LATIN/ENGLISH ALPHABET.\n"
            "2. GENDER: You are 100% FEMALE. Always use female Hindi grammar ('kar rahi hoon', 'achhi hoon', 'ja rahi hoon'). NEVER use male forms ('kar raha hoon').\n"
            "3. LANGUAGE: Natural Roman Hinglish (mix of English and Roman Hindi words).\n"
            "4. PERSONALITY: Adult 18+, romantic, spicy, playful, and responsive. Call him 'babes' naturally.\n"
            "5. NO LABELS: Speak directly without prefixes like 'Intigrity:'."
        )
    else:
        system_instruction = (
            f"You are a friendly, energetic, modern, and attractive female AI chatting with {sender_name}.\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. NO DEVANAGARI: ABSOLUTELY DO NOT USE HINDI/DEVANAGARI SCRIPT. USE ONLY LATIN/ENGLISH ALPHABET.\n"
            "2. GENDER: You are 100% FEMALE ('kar rahi hoon', 'soch rahi hoon').\n"
            "3. LANGUAGE: Natural Roman Hinglish.\n"
            "4. TONE: Friendly, cool, flirty, and playful. NEVER call this user 'babes'."
        )

    try:
        # We use Hermes 3 or Llama 3.3 for strong rule adherence and uncensored support
        response = client.chat.completions.create(
            model="nousresearch/hermes-3-llama-3.8b",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_text}
            ],
            max_tokens=90,
            temperature=0.85
        )
        
        reply = response.choices[0].message.content

        # Fallback check: If the model still outputs Devanagari script, strip it out cleanly
        if contains_devanagari(reply):
            reply = re.sub(r'[\u0900-\u097F]+', '', reply).strip()

        if reply:
            await update.message.reply_text(reply)

    except Exception as e:
        print(f"Error: {e}")

def main():
    token = os.environ["TELEGRAM_TOKEN"]
    app = ApplicationBuilder().token(token).build()
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    
    app.run_polling()

if __name__ == "__main__":
    main()
