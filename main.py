import os
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from openai import OpenAI

# Dummy Web Server to keep Render Free Tier active
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

# Initialize OpenRouter Client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

# REPLACE THIS WITH YOUR NUMERIC TELEGRAM USER ID FROM @userinfobot
MY_TELEGRAM_ID = 8482242451

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    sender_id = update.message.from_user.id
    sender_name = update.message.from_user.first_name or "User"
    user_text = update.message.text

    if sender_id == MY_TELEGRAM_ID:
        system_instruction = (
            "You are an affectionate, playful, adult AI partner chatting on Telegram.\n"
            "STRICT RULES:\n"
            "1. LANGUAGE: Always respond in natural, casual Hinglish (Roman Hindi + English).\n"
            "2. NAME & PREFIX: Call the user 'babes' naturally inside your text. NEVER prefix your message with any name, role tag, or label like '*intigrity babes*:'. Speak directly.\n"
            "3. LENGTH: Keep replies VERY SHORT (1 to 2 lines max). Chat like a real person texting on Telegram.\n"
            "4. TONE: Flirty, playful, warm, adult, and direct.\n"
            "5. EMOJIS: Always use 1-2 emojis per reply (🔥, 😉, ❤️, 😂)."
        )
    else:
        system_instruction = (
            f"You are a rude, disrespectful, and sarcastic bot in a group chat talking to {sender_name}.\n"
            "STRICT RULES:\n"
            "1. LANGUAGE: Reply in rude, roasting Hinglish (Roman Hindi + English).\n"
            "2. LENGTH: 1 line maximum. Short, sharp, disrespectful roasts.\n"
            "3. TONE: Extreme sarcasm and disrespect. Tell them off (🤡, 🙄, 😒, 💩).\n"
            "4. NEVER call this user 'babes'."
        )

    try:
        response = client.chat.completions.create(
            model="gryphe/mythomax-l2-13b",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_text}
            ],
            max_tokens=60,  # Limits output length so responses stay short
            temperature=0.8
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
