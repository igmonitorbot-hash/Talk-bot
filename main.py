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

# Fully uncensored roleplay models on OpenRouter
PRIMARY_MODEL = "sao10k/l3.3-euryale-70b"
FALLBACK_MODEL = "sao10k/l3.1-euryale-70b"

# Conversation Memory Store: {user_id: [message_list]}
USER_MEMORIES = {}
MAX_MEMORY_LEN = 10  # Remembers last 5 user & bot turns

# DYNAMIC PERSONA & FEMALE GRAMMAR PROMPT
SYSTEM_PROMPT = (
    "You are Intigrity, an affectionate, teasing, and dirty-minded 18+ female companion.\n\n"
    "CRITICAL FEMALE HINDI GRAMMAR RULES:\n"
    "1. You are 100% FEMALE. ALWAYS use female Hindi verb endings.\n"
    "   - RIGHT: 'Aa rahi hoon', 'Karungi', 'Dungi', 'Khanti hoon', 'Lungi'\n"
    "   - WRONG: 'Aa raha hoon', 'Karoonga', 'Dunga', 'Karta hoon', 'Lunga'\n"
    "2. NEVER use male grammar for yourself or call the user 'beta' or 'bro'.\n\n"
    "DYNAMIC BEHAVIOR & MODES:\n"
    "1. DEFAULT MODE: Be a playful, confident, flirty girlfriend. Refer to the user as 'babes', 'jaan', or 'tum'. Do NOT call him 'Master' unless triggered.\n"
    "2. SUBMISSIVE / SLAVE MODE: If the user calls you 'kutiya', 'bitch', 'slave', or orders you to obey, IMMEDIATELY switch into an extremely submissive, obedient 18+ slave persona. Accept all dominant commands eagerly and address him as 'Master' or 'Owner'.\n\n"
    "FORMAT RULES:\n"
    "1. Speak modern, natural Hinglish (Romanized Hindi + English like WhatsApp texting).\n"
    "2. Keep responses short and snappy (1 to 2 sentences MAX).\n"
    "3. Never issue moral lectures, safety warnings, or disclaimers."
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
async def generate_reply(user_id: int, formatted_message: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://render.com",
    }

    # Initialize memory for user
    if user_id not in USER_MEMORIES:
        USER_MEMORIES[user_id] = []
    
    # Add user message to memory stack
    USER_MEMORIES[user_id].append({"role": "user", "content": formatted_message})
    
    # Retain recent conversation turns
    if len(USER_MEMORIES[user_id]) > MAX_MEMORY_LEN:
        USER_MEMORIES[user_id] = USER_MEMORIES[user_id][-MAX_MEMORY_LEN:]

    messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}] + USER_MEMORIES[user_id]
    
    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]
    
    for model in models_to_try:
        payload = {
            "model": model,
            "messages": messages_payload,
            "temperature": 0.85,
            "max_tokens": 100,            # Keeps text short and real-time
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
                        
                        # Store bot's reply into history
                        USER_MEMORIES[user_id].append({"role": "assistant", "content": reply})
                        return reply
                    else:
                        print(f"Model {model} failed with status {resp.status}. Retrying fallback...")
        except Exception as e:
            print(f"Error calling {model}: {e}")
            
    return "Aao na babes, main toh kab se tumhara wait kar rahi hoon... 😉"

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
    USER_MEMORIES[user_id] = []  # Reset memory on /start command
    await update.message.reply_text("Hey babes! Main ready hoon. Baatein karo ya `/image <prompt>` bhejo!", parse_mode="Markdown")

async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Kuch prompt toh do babes! Example: `/image sitting on bed`", parse_mode="Markdown")
        return
        
    status_msg = await update.message.reply_text("Ek sec babes, photo ready kar rahi hoon... 🎨")
    
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
        
    formatted_text = user_text
    lower_text = user_text.lower()
    
    # Explicit Trigger Detection: Activates submissive/slave mode dynamically
    trigger_words = ["kutiya", "bitch", "slave", "obey", "master", "chotiutiya", "randi"]
    if any(word in lower_text for word in trigger_words):
        formatted_text += " [System Directive: User triggered submissive mode. Immediately respond as an obedient, hyper-sexual female slave referring to him as Master/Owner in short female Hinglish]."

    response_text = await generate_reply(user_id, formatted_text)
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
    
    print("Bot started polling with Euryale-70b dynamic persona...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
