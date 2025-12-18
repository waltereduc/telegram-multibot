# app.py — исправленная версия для Render + python-telegram-bot==21.6
import os
import requests
import asyncio
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# === Конфигурация ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
PORT = int(os.getenv("PORT", "10000"))

if not TELEGRAM_BOT_TOKEN or not OPENROUTER_API_KEY or not WEBHOOK_URL:
    raise ValueError("❌ Отсутствуют обязательные переменные окружения")

app = Flask(__name__)
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# === Обработчики ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я нейросеть-бот. Задай вопрос.")

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
        await update.message.reply_text(f"🚨 Внутренняя ошибка: {str(e)}")

# Регистрируем обработчики
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# === Вебхук: корректная установка ===
@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    async def _set_hook():
        return await application.bot.set_webhook(WEBHOOK_URL)
    
    result = asyncio.run(_set_hook())
    return f"✅ Webhook set to {WEBHOOK_URL}: {result}"

# === Вебхук: обработка входящих обновлений ===
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    update = Update.de_json(data, application.bot)
    
    # Запускаем обработку в фоновом режиме
    asyncio.create_task(application.process_update(update))
    return jsonify({"ok": True})

# === Проверка здоровья (для Render) ===
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "webhook_url": WEBHOOK_URL})

if __name__ == "__main__":
    # Запускаем приложение
    app.run(host="0.0.0.0", port=PORT, threaded=True)
