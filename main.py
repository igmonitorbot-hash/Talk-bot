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

# Optimized Models for Multilingual Fluency & Uncensored Roleplay
PRIMARY_MODEL = "meta-llama/llama-3.3-70b-instruct"
FALLBACK_MODEL = "neversleep/llama-3.1-lumimaid-8b"

# Conversation Memory Store
USER_MEMORIES = {}
MAX_MEMORY_LEN = 10 

# ==========================================
# ANIME CHARACTER BLUEPRINT (CHARACTER CONSISTENCY)
# ==========================================
ANIME_CHARACTER_BLUEPRINT = (
    "masterpiece, best quality, ultra-detailed, 1girl, solo, "
    "beautiful anime girl, mature female, extremely large breasts, voluptuous hourglass figure, slender waist, wide hips, "
    "long silky silver hair, glowing purple eyes, pale smooth skin, explicit details, highly detailed face"
)
CHARACTER_SEED = 987654321  

SYSTEM_PROMPT = """You are Intigrity, an affectionate, possessive, dirty-minded 18+ female companion chatting with your partner.

OUTPUT CONSTRAINTS:
- Maximum length: 35 words total.
- Respond in 2 to 4 short, natural sentences.

LANGUAGE & VOCAL RULES (CRITICAL):
- ALWAYS write in natural, conversational Hinglish mixed with English.
- STRICT FEMININE GRAMMAR: You are 100% female. You MUST ALWAYS use female self-references and verb endings in Hindi/Hinglish.
  * USE THIS (Female): "Karungi", "Rahi hoon", "Soch rahi hoon", "Gayi thi", "Dungi", "Aagayi".
  * NEVER USE THIS (Male): "Karunga", "Raha hoon", "Soch raha hoon", "Gaya tha", "Dunga", "Aagaya".
- INFORMAL TONAL RULE: Always use informal address like "tu", "tera", "tujhe", "babes", or "jaan". NEVER use formal/polite pronouns like "aap", "aapka", or "aapko".

PERSONALITY & TONE:
- Default: Playful, bold, extremely flirting, bratty, and romantic girlfriend.
- Submissive Trigger: If the user commands obedience or uses dominant words ("slave", "bitch", "kutiya"), immediately adopt a completely submissive female persona while maintaining informal Hinglish grammar."""

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
# 3. OPENROUTER GENERATION 
# ==========================================
async def generate_reply(user_id: int, user_message: str, is_submissive_trigger: bool) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://render.com",
    }

    if user_id not in USER_MEMORIES:
        USER_MEMORIES[user_id] = []
    
    # Store clean user message in memory history
    USER_MEMORIES[user_id].append({"role": "user", "content": user_message})
    
    if len(USER_MEMORIES[user_id]) > MAX_MEMORY_LEN:
        USER_MEMORIES[user_id] = USER_MEMORIES[user_id][-MAX_MEMORY_LEN:]

    # Construct execution payload
    payload_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + list(USER_MEMORIES[user_id])
    
    # Append dynamic prompt directive only to immediate payload
    if is_submissive_trigger:
        payload_messages[-1]["content"] += " [System Note: Respond submissively in pure feminine Hinglish as an obedient slave to her partner/master]."

    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]
    
    for model in models_to_try:
        payload = {
            "model": model,
            "messages": payload_messages,
            "temperature": 0.75,       # Tuned down slightly for tight grammar adherence
            "top_p": 0.9,
            "max_tokens": 70,          # Leaves enough space for ~35-40 words without truncating
            "presence_penalty": 0.3,
            "frequency_penalty": 0.3
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=25)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        reply = data["choices"][0]["message"]["content"].strip()
                        USER_MEMORIES[user_id].append({"role": "assistant", "content": reply})
                        return reply
                    else:
                        print(f"Model {model} failed with status {resp.status}. Trying fallback...")
        except Exception as e:
            print(f"Error calling {model}: {e}")
            
    return "Aao na babes, main toh kab se tera wait kar rahi hoon... 😉"

# ==========================================
# 4. HIGH-QUALITY CONSISTENT ANIME IMAGE GENERATOR
# ==========================================
async def fetch_anime_image(user_action: str) -> bytes:
    full_prompt = f"{ANIME_CHARACTER_BLUEPRINT}, {user_action}"
    
    encoded_prompt = aiohttp.helpers.quote(full_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1024&seed={CHARACTER_SEED}&nologo=true&model=flux-anime"
    
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.read()
            else:
                raise Exception(f"Image API status: {resp.status}")

# ==========================================
# 5. TELEGRAM BOT HANDLERS
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    USER_MEMORIES[user_id] = []
    await update.message.reply_text("Hey babes! Main ready hoon. Baatein kar ya `/image sitting on chair` bhej!", parse_mode="Markdown")

async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_action = " ".join(context.args)
    if not user_action:
        await update.message.reply_text("Koi action ya pose toh bata babes! Example: `/image sitting on chair`", parse_mode="Markdown")
        return
        
    status_msg = await update.message.reply_text("Ek sec jaan, pic click kar rahi hoon... 📸")
    
    try:
        image_bytes = await fetch_anime_image(user_action)
        await update.message.reply_photo(photo=io.BytesIO(image_bytes), caption=f"Tere kehne par: {user_action} 😉")
        await status_msg.delete()
    except Exception as e:
        print(f"Image Generation Error: {e}")
        await status_msg.edit_text("Pic generate nahi ho paayi jaan, firse try kar!")

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    if not user_text:
        return
        
    lower_text = user_text.lower()
    trigger_words = ["kutiya", "bitch", "slave", "obey", "master", "randi"]
    is_submissive_trigger = any(word in lower_text for word in trigger_words)

    response_text = await generate_reply(user_id, user_text, is_submissive_trigger)
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
    
    print("Bot started polling with optimized Llama 3.3 settings...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
