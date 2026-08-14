import os
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from groq import Groq

# Dummy Web Server so Render Free Tier stays happy
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is live!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()

# Start dummy server in background
threading.Thread(target=run_health_server, daemon=True).start()

# Initialize Groq
groq_client = Groq(api_key=os.environ["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"])

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    # Send user message to Groq
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a supportive, non-judgmental friend. Swearing and adult language are completely welcome. Keep answers concise."},
            {"role": "user", "content": update.message.text}
        ]
    )
    
    # Reply back on Telegram
    await update.message.reply_text(response.choices[0].message.content)

def main():
    token = os.environ["8839652051:AAFCpW_KpMagsKQxDpQlZ-0LUpoRfa5BSNI"]
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.run_polling()

if __name__ == "__main__":
    main()
