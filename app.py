# app.py
import os
import json
import requests
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# === Конфигурация ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Например: https://your-render-app.onrender.com/webhook

if not TELEGRAM_BOT_TOKEN or not OPENROUTER_API_KEY or not WEBHOOK_URL:
    raise ValueError("❌ Отсутствуют обязательные переменные окружения")

app = Flask(__name__)
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# === Обработчики ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напиши любой вопрос — отвечу через нейросеть.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": WEBHOOK_URL,
                "X-Title": "TG NeuroBot"
            },
            json={
                "model": "qwen/qwen-1.5-1.8b-chat",
                "messages": [{"role": "user", "content": user_text}]
            },
            timeout=30
        )
        if response.status_code == 200:
            answer = response.json()["choices"][0]["message"]["content"]
            await update.message.reply_text(answer)
        else:
            await update.message.reply_text(f"⚠️ Ошибка {response.status_code}. Попробуй позже.")
    except Exception as e:
        await update.message.reply_text("🚨 Не удалось получить ответ. Проверь логи.")

# Регистрируем обработчики
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# === Вебхук ===
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    update = Update.de_json(data, application.bot)
    application.update_processor.process_update(application.update_queue, update)
    return jsonify({"ok": True})

# Инициализация — устанавливаем вебхук при старте
@app.route('/set_webhook')
def set_webhook():
    webhook_info = application.bot.set_webhook(url=WEBHOOK_URL)
    return f"✅ Webhook set to {WEBHOOK_URL}: {webhook_info}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
