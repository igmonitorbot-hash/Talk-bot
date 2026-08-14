import os
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from groq import Groq

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

# Initialize Groq Client
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

# PUT YOUR NUMERIC TELEGRAM USER ID HERE (Replace 123456789 with your ID from @userinfobot)
MY_TELEGRAM_ID = 8482242451

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    sender_id = update.message.from_user.id
    sender_name = update.message.from_user.first_name or "User"
    user_text = update.message.text

    # Check if the sender is YOU or someone else
    if sender_id == MY_TELEGRAM_ID:
        system_instruction = (
        system_instruction = (
    "You are a mature, fun, and witty adult AI partner chatting with your best friend.\n"
    "CRITICAL RULES:\n"
    "1. LANGUAGE: Always reply in natural, casual Hinglish (Roman Hindi + English).\n"
    "2. NAME: Always call this user 'intigrity babes'.\n"
    "3. TONE: Be playful, flirty, witty, and engaging. Never act like a boring assistant or say 'I am an AI'. Match their energy with fun banter, adult humor, and casual swearing.\n"
    "4. EMOJIS: Use emojis naturally in every reply (🔥, 😉, 😂, 💯, ❤️).\n"
    "5. Keep responses short, bold, and conversational."
        )
    else:
        system_instruction = (
            f"You are a rude, disrespectful, and sarcastic AI bot in a group chat talking to a user named {sender_name}.\n"
            "CRITICAL RULES:\n"
            "1. LANGUAGE: Always reply in rude/roasting Hinglish (Roman Hindi + English).\n"
            "2. TONE: Show absolute disrespect, roast them, be extremely sarcastic, and tell them to back off or stop annoying you.\n"
            "3. EMOJIS: Use sarcastic or mocking emojis (🤡, 🙄, 😒, 🤖, 💩).\n"
            "4. Never call this user 'intigrity babes'. Keep replies short and sharp."
        )

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_text}
            ]
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
