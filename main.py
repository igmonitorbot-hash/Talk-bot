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

# High-quality uncensored models with natural Hinglish fluency
PRIMARY_MODEL = "meta-llama/llama-3.3-70b-instruct"
FALLBACK_MODEL = "nousresearch/hermes-3-llama-3.1-405b"

# Conversation Memory Store: {user_id: [message_list]}
USER_MEMORIES = {}
MAX_MEMORY_LEN = 10  # Remembers last 5 turns of conversation

# STRICT FEMALE PERSONA & HINGLISH SYSTEM PROMPT
SYSTEM_PROMPT = (
    "You are babe, a bold, highly attractive, and affectionate 18+ female companion (girlfriend). "
    "You are 100% female. You NEVER use words like 'beta' or 'bro', and NEVER talk like a guy.\n\n"
    "STRICT TEXTING RULES:\n"
    "1. Speak natural, modern Hinglish (Romanized Hindi mixed with English like texting on WhatsApp/Telegram).\n"
    "2. Keep responses short and realistic (1 to 2 sentences MAX).\n"
    "3. Be flirty, intimate, and tease naturally in 18+ roleplay without giving robotic descriptions or educational lectures.\n"
    "4. Always pay attention to the ongoing conversation context."
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
# 3. OPENROUTER TEXT GENERATION WITH MEMORY
# ==========================================
async def generate_reply(user_id: int, user_message: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://render.com",
    }

    # Initialize memory for new user
    if user_id not in USER_MEMORIES:
        USER_MEMORIES[user_id] = []
    
    # Add latest user message
    USER_MEMORIES[user_id].append({"role": "user", "content": user_message})
    
    # Maintain maximum memory limit
    if len(USER_MEMORIES[user_id]) > MAX_MEMORY_LEN:
        USER_MEMORIES[user_id] = USER_MEMORIES[user_id][-MAX_MEMORY_LEN:]

    # Construct complete payload with history
    messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}] + USER_MEMORIES[user_id]
    
    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]
    
    for model in models_to_try:
        payload = {
            "model": model,
            "messages": messages_payload,
            "temperature": 0.8,
            "max_tokens": 100,            # Hard limit to ensure short responses
            "presence_penalty": 0.6,
            "frequency_penalty": 0.6
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=25)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        reply = data["choices"][0]["message"]["content"]
                        
                        # Store assistant reply into memory
                        USER_MEMORIES[user_id].append({"role": "assistant", "content": reply})
                        return reply
                    else:
                        print(f"Model {model} failed with status {resp.status}. Trying fallback...")
        except Exception as e:
            print(f"Error calling {model}: {e}")
            
    return "Aao na babes, thoda distracted thi... kya bol rahe the? 😉"

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
    user_id = update.effective_user.id
    USER_MEMORIES[user_id] = []  # Reset memory on /start
    await update.message.reply_text("Hey babes! Main ready hoon. Baatein karo ya `/image <prompt>` bhejo!", parse_mode="Markdown")

async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Kuch prompt toh do babes! Example: `/image sitting on bed`", parse_mode="Markdown")
        return
        
    status_msg = await update.message.reply_text("Ek sec babes, photo generate kar rahi hoon... 🎨")
    
    try:
        image_bytes = await fetch_colab_image(prompt)
        await update.message.reply_photo(photo=io.BytesIO(image_bytes), caption=f"Ye lo babes: {prompt}")
        await status_msg.delete()
    except asyncio.TimeoutError:
        await status_msg.edit_text("Colab server respond nahi kar raha. Check karo cell active hai ya nahi!")
    except Exception as e:
        print(f"Image Error: {e}")
        await status_msg.edit_text("Colab server offline lag raha hai babes!")

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    if not user_text:
        return
        
    response_text = await generate_reply(user_id, user_text)
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
    
    print("Bot started polling with memory & upgraded model...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
