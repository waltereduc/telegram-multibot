import os
import asyncio
import requests
import traceback
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============ НАСТРОЙКИ — БЕРЕМ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ============
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://telegram-multibot.onrender.com/webhook")
# ===================================================================

app = Flask(__name__)
app.config['WEBHOOK_SET'] = False

# Health check endpoint
@app.route('/')
def health_check():
    return jsonify({"status": "ok", "message": "Bot is running"})

# Промпты для каждой темы (оставь как есть)
PROMPTS = { ... }  # твой текущий код промптов

# Хранилище выбора пользователя
user_modes = {}

# Кнопки тем (оставь как есть)
def get_theme_buttons(): ...  # твой текущий код

# Обработчики (оставь как есть)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): ...
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE): ...
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE): ...

# Улучшенный webhook endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        if not app.config['WEBHOOK_SET']:
            setup_webhook()
        
        json_str = request.get_data().decode('UTF-8')
        update = Update.de_json(json_str, application.bot)
        
        # Асинхронная обработка
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(application.process_update(update))
        finally:
            loop.close()
        
        return jsonify({"ok": True})
    
    except Exception as e:
        print(f"🚨 WEBHOOK ERROR: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Инициализация бота
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Регистрация обработчиков
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Функция установки webhook
def setup_webhook():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(application.bot.set_webhook(url=WEBHOOK_URL.strip()))  # .strip() уберёт пробелы!
        print(f"✅ Webhook set to {WEBHOOK_URL.strip()}")
        app.config['WEBHOOK_SET'] = True
    except Exception as e:
        print(f"⚠️ Failed to set webhook: {e}")
        traceback.print_exc()

# Запуск
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"✅ Starting Flask on port {port}")
    setup_webhook()
    app.run(host="0.0.0.0", port=port, debug=False)
