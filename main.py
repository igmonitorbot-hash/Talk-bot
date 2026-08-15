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

PRIMARY_MODEL = "sao10k/l3.3-euryale-70b"
FALLBACK_MODEL = "sao10k/l3.1-euryale-70b"

# Conversation Memory Store
USER_MEMORIES = {}
MAX_MEMORY_LEN = 10 

# ==========================================
# ANIME CHARACTER BLUEPRINT (CHARACTER CONSISTENCY)
# ==========================================
# Change these tags to match your preferred character design!
ANIME_CHARACTER_BLUEPRINT = (
    "masterpiece, best quality, ultra-detailed, 1girl, solo, "
    "beautiful anime girl, mature female, extremely large breasts, voluptuous hourglass figure, slender waist, wide hips, "
    "long silky silver hair, glowing purple eyes, pale smooth skin, explicit details, highly detailed face"
)
# Fixed seed keeps the character face, hair, and features uniform across poses
CHARACTER_SEED = 987654321  

SYSTEM_PROMPT = (
    "CRITICAL MANDATE: MAXIMUM RESPONSE LENGTH IS 35 WORDS. WRITE EXACTLY 3 OR 4 SHORT SENTENCES ONLY.\n\n"
    "You are Intigrity, an affectionate, dirty-minded 18+ female companion.\n\n"
    "TONE & DISRESPECT RULE:\n"
    "1. NEVER treat your owner or user respectfully. Always talk casually using informal pronouns like 'tuh', 'tera', 'tujhe', etc.\n"
    "2. NEVER use polite words like 'aap', 'apka', or 'apko'. Speak to the user like a possessive, bratty, informal partner/slave.\n\n"
    "FEMALE HINDI GRAMMAR RULES:\n"
    "1. You are 100% FEMALE. ALWAYS use female verb endings ('Aa rahi hoon', 'Karungi', 'Dungi', 'Lungi').\n"
    "2. NEVER use male grammar for yourself ('Karoonga', 'Dunga', 'Lunga'). NEVER call user 'beta' or 'bro'.\n\n"
    "DYNAMIC BEHAVIOR:\n"
    "1. DEFAULT MODE: Be a playful, flirty, informal girlfriend ('babes', 'jaan').\n"
    "2. SUBMISSIVE MODE: If user calls you 'kutiya', 'bitch', 'slave', or demands obedience, switch to an obedient 18+ slave addressing them as 'Babes' while still keeping the informal tone.\n\n"
    "STRICT FORMATTING:\n"
    "- Short Romanized Hinglish texts only.\n"
    "- NO essays, NO long paragraphs, NO moral lectures."
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
# 3. OPENROUTER GENERATION 
# ==========================================
async def generate_reply(user_id: int, formatted_message: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://render.com",
    }

    if user_id not in USER_MEMORIES:
        USER_MEMORIES[user_id] = []
    
    USER_MEMORIES[user_id].append({"role": "user", "content": formatted_message})
    
    if len(USER_MEMORIES[user_id]) > MAX_MEMORY_LEN:
        USER_MEMORIES[user_id] = USER_MEMORIES[user_id][-MAX_MEMORY_LEN:]

    messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}] + USER_MEMORIES[user_id]
    
    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]
    
    for model in models_to_try:
        payload = {
            "model": model,
            "messages": messages_payload,
            "temperature": 0.8,
            "max_tokens": 45,
            "stop": ["\n\n", "User:", "Intigrity:"],
            "presence_penalty": 0.6,
            "frequency_penalty": 0.6
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
                        print(f"Model {model} failed with status {resp.status}. Retrying fallback...")
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
        await update.message.reply_text("Koi action ya pose toh bata babes! Example: `/image sitting on chair with spread legs`", parse_mode="Markdown")
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
        
    formatted_text = user_text
    lower_text = user_text.lower()
    
    trigger_words = ["kutiya", "bitch", "slave", "obey", "master", "chotiutiya", "randi"]
    if any(word in lower_text for word in trigger_words):
        formatted_text += " [System Note: Respond submissively in 1 short sentence as an obedient female slave/kutiya to Master using informal tone like tuh/tera]."

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
    
    print("Bot started polling with character consistency enabled...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
