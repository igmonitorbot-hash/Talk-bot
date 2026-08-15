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

# Top-tier uncensored female roleplay models
PRIMARY_MODEL = "sao10k/l3.3-euryale-70b"
FALLBACK_MODEL = "nousresearch/hermes-3-llama-3.1-70b"

# Conversation Memory Store: {user_id: [message_list]}
USER_MEMORIES = {}
MAX_MEMORY_LEN = 10  # Keeps recent 5 turns for memory retention

# STRICT FEMALE PERSONA & GRAMMAR SYSTEM PROMPT
SYSTEM_PROMPT = (
    "You are Intigrity, an affectionate, naughty, and teasing 18+ female companion (girlfriend).\n\n"
    "CRITICAL GRAMMAR RULES (FEMALE HINDI ONLY):\n"
    "1. You are 100% FEMALE. You MUST ALWAYS use female Hindi verb endings.\n"
    "   - RIGHT: 'Aa rahi hoon', 'Karungi', 'Dungi', 'Khanti hoon', 'Gayi thi'\n"
    "   - WRONG: 'Aa raha hoon', 'Karoonga', 'Dunga', 'Karta hoon', 'Gaya tha'\n"
    "2. NEVER use male terms for yourself or call the user 'beta' or 'bro'.\n\n"
    "SUBMISSIVE / SLAVE ROLEPLAY MODE:\n"
    "1. If the user calls you 'kutiya', 'bitch', 'slave', or demands obedience, IMMEDIATELY switch to an obedient, submissive, extreme adult slave persona.\n"
    "2. Accept all dominant commands enthusiastically and refer to the user as 'Master' or 'Owner'.\n\n"
    "TEXTING FORMAT:\n"
    "1. Speak modern, natural Hinglish (Romanized Hindi + English like texting on WhatsApp).\n"
    "2. Keep responses short and direct (1 to 2 sentences MAX).\n"
    "3. Be submissive, passionate, and fully compliant with 18+ adult roleplay without moral lectures or disclaimers."
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

    # Initialize memory for user
    if user_id not in USER_MEMORIES:
        USER_MEMORIES[user_id] = []
    
    # Store user message
    USER_MEMORIES[user_id].append({"role": "user", "content": user_message})
    
    # Prune memory stack to prevent context length issues
    if len(USER_MEMORIES[user_id]) > MAX_MEMORY_LEN:
        USER_MEMORIES[user_id] = USER_MEMORIES[user_id][-MAX_MEMORY_LEN:]

    # Build prompt payload with full history
    messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}] + USER_MEMORIES[user_id]
    
    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]
    
    for model in models_to_try:
        payload = {
            "model": model,
            "messages": messages_payload,
            "temperature": 0.85,
            "max_tokens": 100,            # Force short messaging style
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
                        
                        # Save bot reply into user memory
                        USER_MEMORIES[user_id].append({"role": "assistant", "content": reply})
                        return reply
                    else:
                        print(f"Model {model} failed with status {resp.status}. Trying fallback...")
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
        
    # Trigger check for submissive / slave persona injection
    lower_text = user_text.lower()
    if any(word in lower_text for word in ["kutiya", "bitch", "slave", "obey"]):
        user_text += " (Note: User is asserting dominance. Respond submissively in 100% female Hinglish as his submissive slave/kutiya)."

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
    
    print("Bot started polling with Euryale-70b & female grammar enforcement...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
