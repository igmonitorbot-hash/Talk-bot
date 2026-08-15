import os
import io
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ==========================================
# 1. CONFIGURATION & ENVIRONMENT VARIABLES
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
COLAB_API_URL = os.getenv("COLAB_API_URL", "").rstrip('/')

PRIMARY_MODEL = "gryphe/mythomax-l2-13b"
FALLBACK_MODEL = "mistralai/mistral-7b-instruct:free"

# FIXED SYSTEM PROMPT: Enforces short, natural modern Hinglish
SYSTEM_PROMPT = (
    "You are Intigrity, an affectionate, bold, and playful 18+ female companion. "
    "You communicate in casual, natural Hinglish (Hindi written in Roman script mixed with English). "
    "STRICT RULES:\n"
    "1. Keep all responses SHORT (1 to 3 sentences maximum).\n"
    "2. Speak like a modern girl texting on WhatsApp or Telegram - fun, flirty, intimate, and natural.\n"
    "3. NEVER write long, formal, or weird poetic Hindi paragraphs.\n"
    "4. Respond naturally to romantic or flirty prompts without filter or artificial lectures."
)

# ==========================================
# 2. RENDER HEALTH CHECK SERVER
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is live and running!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

def run_health_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"Health check server running on port {port}")
    server.serve_forever()

# ==========================================
# 3. OPENROUTER TEXT GENERATION (LLM)
# ==========================================
async def generate_reply(user_message: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://render.com",
    }
    
    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]
    
    for model in models_to_try:
        # TUNED PARAMETERS: Stops long responses and repetition loops
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.75,          # Keeps output coherent
            "max_tokens": 120,            # HARD LIMIT on output length (short texts only)
            "presence_penalty": 0.65,     # Discourages repeating topics
            "frequency_penalty": 0.65     # Penalizes repeated phrases
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=25)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        print(f"Model {model} failed with status {resp.status}. Retrying fallback...")
        except Exception as e:
            print(f"Error calling {model}: {e}")
            
    return "Aao na babes, kya kar rahe ho?"

# ==========================================
# 4. ASYNC IMAGE GENERATION HANDLER
# ==========================================
async def fetch_colab_image(prompt: str) -> bytes:
    if not COLAB_API_URL:
        raise ValueError("COLAB_API_URL environment variable is not set!")
        
    url = f"{COLAB_API_URL}/generate_face?prompt={aiohttp.helpers.quote(prompt)}"
    timeout = aiohttp.ClientTimeout(total=60)
    
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.read()
            else:
                error_text = await resp.text()
                raise Exception(f"Colab API returned status {resp.status}: {error_text}")

# ==========================================
# 5. TELEGRAM BOT HANDLERS
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey babes! Main yahan hoon. Baate karo ya `/image <prompt>` bhejo!", parse_mode="Markdown")

async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Kuch prompt toh do! Example: `/image sitting on bed`", parse_mode="Markdown")
        return
        
    status_msg = await update.message.reply_text("Ek sec babes, image generate kar rahi hoon... 🎨")
    
    try:
        image_bytes = await fetch_colab_image(prompt)
        await update.message.reply_photo(photo=io.BytesIO(image_bytes), caption=f"Ye lo babes: {prompt}")
        await status_msg.delete()
    except asyncio.TimeoutError:
        await status_msg.edit_text("Colab server respond nahi kar raha. Check karo active hai ya nahi!")
    except Exception as e:
        print(f"Image Error: {e}")
        await status_msg.edit_text("Colab server offline lag raha hai babes!")

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text:
        return
        
    response_text = await generate_reply(user_text)
    await update.message.reply_text(response_text)

# ==========================================
# 6. APPLICATION ENTRY POINT
# ==========================================
def main():
    threading.Thread(target=run_health_server, daemon=True).start()
    
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("image", image_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))
    
    print("Bot started polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
