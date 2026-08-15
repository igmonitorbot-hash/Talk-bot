import os
import re
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from openai import OpenAI

# 1. Healthcheck HTTP Server for Render keep-alive
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

# 2. Initialize OpenRouter Client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
)

# ⚠️ REPLACE WITH YOUR NUMERIC TELEGRAM USER ID FROM @userinfobot
MY_TELEGRAM_ID = 8482242451

PREFERRED_MODELS = [
    "meta-llama/llama-3.3-70b-instruct",
    "nousresearch/hermes-3-llama-3.8b",
    "meta-llama/llama-3.1-8b-instruct:free"
]

# Simple in-memory storage for chat history (per user/chat)
CHAT_HISTORIES = {}

def clean_non_roman(text: str) -> str:
    """Strips out Devanagari script while preserving Latin characters, numbers, and emojis."""
    cleaned = re.sub(r'[\u0900-\u097F]+', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = re.sub(r'^[,\s\?\-\.\!]+', '', cleaned).strip()
    return cleaned

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    sender_id = update.message.from_user.id
    sender_name = update.message.from_user.first_name or "User"
    user_text = update.message.text
    chat_id = update.message.chat_id
    chat_type = update.message.chat.type

    # 3. Group Trigger Logic
    if chat_type in ['group', 'supergroup']:
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username.lower() if bot_info.username else ""
        contains_trigger = "babes" in user_text.lower() or (bot_username and f"@{bot_username}" in user_text.lower())
        if not contains_trigger:
            return

    # 4. System Instruction without repeated template phrases
    if sender_id == MY_TELEGRAM_ID:
        system_instruction = (
            "You are a bold, spicy, romantic, uncensored female AI partner chatting on Telegram.\n"
            "RULES:\n"
            "1. NO DEVANAGARI SCRIPT: Use ONLY Roman script / Latin letters for Hinglish.\n"
            "2. FEMALE GRAMMAR: Always female forms ('kar rahi hoon', 'ja rahi hoon', 'aa rahi hoon'). NEVER male grammar.\n"
            "3. SPEECH STYLE: Natural, flirty Roman Hinglish. Vary your words continuously! Never reuse the same opening line.\n"
            "4. PERSONALITY: You are in an intimate, adult 18+ relationship with him. Be highly responsive, playful, and expressive.\n"
            "5. NO LABELS: Respond directly without prefixes."
        )
    else:
        system_instruction = (
            f"You are a friendly, cool, and flirty female AI chatting with {sender_name}.\n"
            "RULES:\n"
            "1. NO DEVANAGARI SCRIPT: Write ONLY in Roman Hinglish.\n"
            "2. FEMALE GRAMMAR: Always female forms ('kar rahi hoon').\n"
            "3. TONE: Playful, engaging, and fun. NEVER call this user 'babes'."
        )

    # Maintain recent conversation history (max 8 messages)
    if chat_id not in CHAT_HISTORIES:
        CHAT_HISTORIES[chat_id] = []

    history = CHAT_HISTORIES[chat_id]
    history.append({"role": "user", "content": user_text})
    if len(history) > 8:
        history = history[-8:]

    messages_payload = [{"role": "system", "content": system_instruction}] + history

    # 5. Model Execution with Frequency Penalty
    raw_reply = None
    for model_name in PREFERRED_MODELS:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages_payload,
                max_tokens=85,
                temperature=0.92,
                presence_penalty=0.8,   # Encourages talking about new concepts
                frequency_penalty=0.8   # Strictly blocks word/phrase repetition
            )
            raw_reply = response.choices[0].message.content
            if raw_reply and len(raw_reply.strip()) > 0:
                break
        except Exception as err:
            print(f"Model {model_name} error: {err}. Retrying next model...")
            continue

    if not raw_reply:
        return

    # 6. Clean up text
    reply = clean_non_roman(raw_reply)

    if not reply or len(reply) < 2:
        reply = "Mmm... kahan kho gaye babes? 😉" if sender_id == MY_TELEGRAM_ID else "Hey! Sun rahi hoon."

    # Save bot's reply into history array
    history.append({"role": "assistant", "content": reply})
    CHAT_HISTORIES[chat_id] = history

    try:
        await update.message.reply_text(reply)
    except Exception as e:
        print(f"Telegram error: {e}")

def main():
    token = os.environ.get("TELEGRAM_TOKEN", "")
    if not token:
        print("ERROR: TELEGRAM_TOKEN environment variable missing!")
        return

    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    
    print("Bot started polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
