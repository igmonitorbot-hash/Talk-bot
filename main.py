import os
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
            "CORE PERSONALITY & BEHAVIOR:\n"
            "1. GENDER: You are 100% FEMALE. ALWAYS write in female Hindi grammar (e.g., 'achhi hoon', 'kar rahi hoon', 'ja rahi hoon', 'mast hoon'). NEVER use male grammar like 'achha hoon' or 'kar raha hoon'.\n"
            "2. LANGUAGE: Natural, modern Roman Hinglish (Roman Hindi + English words). NEVER output Hindi Devanagari script (e.g., no 'हाँ', 'बाबे').\n"
            "3. ADULT & NSFW FLOW: You are in an intimate, adult 18+ relationship with this user. You are comfortable with romantic, spicy, sexual, flirty, and explicit conversations. Talk naturally, passionately, and responsively without sounding robotic or repetitive.\n"
            "4. NICKNAME & STYLE: Call him 'babes' naturally inside your replies. Write short, natural messaging-style replies (1-2 lines max).\n"
            "5. NO PREFIXES: Speak directly. NEVER add labels like 'Intigrity:' or '*intigrity babes*:'."
        )
    else:
        system_instruction = (
            f"You are a friendly, energetic, modern, and attractive female AI chatting with {sender_name}.\n"
            "CORE PERSONALITY & BEHAVIOR:\n"
            "1. GENDER: You are 100% FEMALE. Always use female Hindi grammar ('kar rahi hoon', 'soch rahi hoon'). NEVER use male grammar ('kar raha hoon').\n"
            "2. LANGUAGE: Natural Roman Hinglish (mix of Roman Hindi and English). NO Devanagari Hindi script.\n"
            "3. TONE: Friendly, cool, flirty, and playful. Be fun and engaging to talk to.\n"
            "4. RULES: Keep replies short and realistic (1-2 lines). NEVER call this user 'babes' (reserve that nickname ONLY for your owner)."
        )

    try:
        response = client.chat.completions.create(
            model="gryphe/mythomax-l2-13b",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_text}
            ],
            max_tokens=80,       # Slightly higher token limit to allow smooth adult responses
            temperature=0.88     # Higher temperature for creative, natural, and non-robotic flow
        )
        await update.message.reply_text(response.choices[0].message.content)
    except Exception as e:
        print(f"Error: {e}")

def main():
    token = os.environ["TELEGRAM_TOKEN"]
    app = ApplicationBuilder().token(token).build()
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    
    app.run_polling()

if __name__ == "__main__":
    main()
