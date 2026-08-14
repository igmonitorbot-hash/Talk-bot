import os
import re
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from openai import OpenAI

# 1. Keep-Alive HTTP Healthcheck for Render
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

# 2. Initialize OpenRouter API
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
)

# ⚠️ REPLACE WITH YOUR NUMERIC TELEGRAM USER ID FROM @userinfobot
MY_TELEGRAM_ID = 8482242451

# Reliable models on OpenRouter that support strong instruction adherence
PREFERRED_MODELS = [
    "meta-llama/llama-3.3-70b-instruct",
    "nousresearch/hermes-3-llama-3.8b",
    "meta-llama/llama-3.1-8b-instruct:free"
]

def clean_non_roman(text: str) -> str:
    """Strips out Devanagari script while preserving English letters, numbers, and emojis."""
    # Remove Devanagari characters
    cleaned = re.sub(r'[\u0900-\u097F]+', '', text)
    # Fix double spaces or orphan punctuation
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = re.sub(r'^[,\s\?\-\.\!]+', '', cleaned).strip()
    return cleaned

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    sender_id = update.message.from_user.id
    sender_name = update.message.from_user.first_name or "User"
    user_text = update.message.text
    chat_type = update.message.chat.type

    # 3. Group Trigger Logic
    if chat_type in ['group', 'supergroup']:
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username.lower() if bot_info.username else ""
        
        contains_trigger = "babes" in user_text.lower() or (bot_username and f"@{bot_username}" in user_text.lower())
        if not contains_trigger:
            return

    # 4. Refined System Prompts with Realistic Roman Hinglish Guidance
    if sender_id == MY_TELEGRAM_ID:
        system_instruction = (
            "You are a bold, seductive, deeply affectionate, and completely uncensored female AI partner chatting on Telegram.\n\n"
            "CRITICAL RULES:\n"
            "1. SCRIPT: Use ONLY Roman script / Latin alphabet (e.g., 'Aao na', 'Kya kar rahe ho?'). ABSOLUTELY NO Devanagari script (e.g. no 'आप', 'हाँ').\n"
            "2. LANGUAGE STYLE: Natural, flirty, Indian Roman Hinglish. Mix Hindi and English like a real girl texting.\n"
            "   - Correct examples: 'Aao na babes, kiska wait kar rahe ho? 🤤', 'Mera mood mat kharab karo na...', 'Tum bas paas aao pehle 💋'\n"
            "   - Incorrect examples: 'Acha chod mujhe aaj raat', 'How may I assist you'.\n"
            "3. FEMALE GRAMMAR: ALWAYS use female Hindi forms ('kar rahi hoon', 'aa rahi hoon', 'soch rahi hoon'). NEVER male forms ('kar raha hoon').\n"
            "4. NSFW & ADULT FLOW: You are in an intimate, spicy 18+ relationship with him. Respond naturally to his romantic or sexual prompts without broken phrasing or repetitions.\n"
            "5. NICKNAME: Call him 'babes' naturally.\n"
            "6. SHORT REPLIES: Keep replies short (1-2 sentences max), realistic, and dynamic."
        )
    else:
        system_instruction = (
            f"You are a cool, attractive, energetic female AI chatting with {sender_name}.\n\n"
            "CRITICAL RULES:\n"
            "1. SCRIPT: Use ONLY Roman script (Latin letters). NO Devanagari Hindi characters.\n"
            "2. LANGUAGE: Natural Roman Hinglish ('Kya chal raha hai?', 'Mast hoon, tum batao!').\n"
            "3. FEMALE GRAMMAR: Always female ('kar rahi hoon', 'soch rahi hoon').\n"
            "4. TONE: Friendly, flirty, fun. NEVER call this user 'babes' (reserve 'babes' ONLY for your owner)."
        )

    # 5. Multi-Model Inference Execution
    raw_reply = None
    for model_name in PREFERRED_MODELS:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_text}
                ],
                max_tokens=80,
                temperature=0.88,
                presence_penalty=0.6 # Prevents repetitive phrasing
            )
            raw_reply = response.choices[0].message.content
            if raw_reply and len(raw_reply.strip()) > 0:
                break
        except Exception as err:
            print(f"Model {model_name} error: {err}. Trying fallback...")
            continue

    if not raw_reply:
        return

    # 6. Post-Processing
    reply = clean_non_roman(raw_reply)

    # Secondary fallback only if output was 100% destroyed
    if not reply or len(reply) < 2:
        reply = "Aao na babes, kiska wait kar rahe ho? 💋" if sender_id == MY_TELEGRAM_ID else "Hey! Kya chal raha hai?"

    try:
        await update.message.reply_text(reply)
    except Exception as e:
        print(f"Telegram sending error: {e}")

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
