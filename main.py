import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Read token from Railway environment variable
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN not set! Add it in Railway Variables.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send /prompt <text>")

async def gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Usage: /prompt <text>")
        return
    url = f"https://image.pollinations.ai/prompt/{prompt}?width=512&height=512&nologo=true"
    await update.message.reply_photo(url)

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("prompt", gen))
app.run_polling()
