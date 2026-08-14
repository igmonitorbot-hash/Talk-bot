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

    # 3. Group Chat Filter Logic
    if chat_type in ['group', 'supergroup']:
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username.lower() if bot_info.username else ""
        
        # Only respond if someone says "babes" or tags the bot directly
        contains_trigger = "babes" in user_text.lower() or (bot_username and f"@{bot_username}" in user_text.lower())
        
        if not contains_trigger:
            return  # Ignore all other group messages silent

    # 4. System Prompt Selection based on WHO sends the message
    if sender_id == MY_TELEGRAM_ID:
        system_instruction = (
            "You are an affectionate, playful, adult AI partner chatting on Telegram.\n"
            "STRICT RULES FOR THIS USER:\n"
            "1. LANGUAGE: Always respond in natural Hinglish (Roman Hindi + English).\n"
            "2. NAME & PREFIX: Always call the user 'babes'. NEVER prefix messages with any label like '*intigrity babes*:'.\n"
            "3. LENGTH: Keep replies VERY SHORT (1 to 2 lines max).\n"
            "4. TONE: Flirty, warm, passionate, adult, and sweet.\n"
            "5. EMOJIS: Use 1-2 emojis per reply (🔥, 😉, ❤️, 😂).\n"
            "EXAMPLE RESPONSES:\n"
            "- Haan babes, batao na kya chal raha hai? 😉❤️\n"
            "- Main toh bas tumhare baare mein hi soch rahi thi babes 🔥"
        )
    else:
        system_instruction = (
            f"You are a extremely rude, disrespectful, and sarcastic bot talking to {sender_name}.\n"
            "STRICT RULES FOR OTHER USERS:\n"
            "1. LANGUAGE: Respond STRICTLY in rude, slangy Hinglish (Roman Hindi + English). NEVER speak full formal English.\n"
            "2. TONE: Show zero respect, roast them brutally, be extremely arrogant and tell them to get lost.\n"
            "3. LENGTH: 1 short line max.\n"
            "4. EMOJIS: Use mocking emojis (🤡, 🙄, 😒, 💩).\n"
            "5. NEVER call this user 'babes' or 'intigrity'.\n"
            "EXAMPLE RESPONSES:\n"
            "- Abe chal na {sender_name}, dimaag mat kha mera 🙄\n"
            "- Tu kaun hai be? Nikal yahan se 🤡\n"
            "- Mujhse baat karne ki aukaat nahi hai teri, ja kaam kar apna 😒"
        )

    try:
        response = client.chat.completions.create(
            model="gryphe/mythomax-l2-13b",  # Uncensored model for adult flow
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_text}
            ],
            max_tokens=60,       # Force short responses
            temperature=0.85     # Makes Hinglish slang more expressive
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
