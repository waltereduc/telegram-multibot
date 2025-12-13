import os
import requests
import json
import traceback
from flask import Flask, request, jsonify
import asyncio

# Импорты telegram должны быть ПОСЛЕ asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============ НАСТРОЙКИ — БЕРЕМ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ============
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://telegram-multibot.onrender.com/webhook").strip()
PORT = int(os.environ.get("PORT", 10000))
# ===================================================================

# Создаем экземпляр Flask
app = Flask(__name__)
app.config['WEBHOOK_SET'] = False

# Health check endpoint
@app.route('/')
def health_check():
    return jsonify({"status": "ok", "message": "Bot is running"})

# Endpoint для ручной установки webhook
@app.route('/setwebhook', methods=['GET'])
def set_webhook():
    try:
        global application
        # Устанавливаем webhook
        asyncio.run(application.bot.set_webhook(url=WEBHOOK_URL))
        app.config['WEBHOOK_SET'] = True
        return jsonify({"ok": True, "webhook_url": WEBHOOK_URL})
    except Exception as e:
        print(f"⚠️ Failed to set webhook manually: {e}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

# Промпты для каждой темы
PROMPTS = {
    "explain": (
        "Ты — эксперт, который объясняет сложные темы очень просто, как ребёнку 10 лет. "
        "Используй аналогии из повседневной жизни (игры, природа, еда). "
        "Не используй жаргон. Ответ должен быть коротким — не больше 4 предложений."
    ),
    "emotional": (
        "Ты — дружелюбный помощник, который помогает структурировать эмоции. "
        "Задавай уточняющие вопросы, если нужно. Предлагай простые техники (дыхание, запись мыслей). "
        "Никогда не давай совет 'просто перестань переживать'. Будь тёплым, но кратким."
    ),
    "parenting": (
        "Ты — спокойный и практичный советчик для родителей. "
        "Давай 1–3 конкретных действия, основанных на возрастной психологии. "
        "Избегай осуждения. Пример: 'Попробуй сказать так: ...'"
    ),
    "ethics": (
        "Ты — философ, который помогает разобрать моральный выбор. "
        "Покажи плюсы и минусы, разные точки зрения (утилитаризм, деонтология). "
        "Заверши нейтральным вопросом: 'А что бы выбрал ты?'"
    )
}

# Хранилище выбора пользователя (в памяти)
user_modes = {}

# Кнопки тем
def get_theme_buttons():
    keyboard = [
        [InlineKeyboardButton("🌱 Объясни просто", callback_data="explain")],
        [InlineKeyboardButton("💬 Эмоциональная поддержка", callback_data="emotional")],
        [InlineKeyboardButton("👨‍👩‍👧 Совет родителям", callback_data="parenting")],
        [InlineKeyboardButton("⚖️ Этическая дилемма", callback_data="ethics")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Обработчики
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Выбери тему, и я помогу:", reply_markup=get_theme_buttons())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    mode = query.data
    user_modes[chat_id] = mode

    theme_names = {
        "explain": "«Объясни просто»",
        "emotional": "«Эмоциональная поддержка»",
        "parenting": "«Совет родителям»",
        "ethics": "«Этическая дилемма»"
    }
    await query.edit_message_text(text=f"Выбрана тема: {theme_names[mode]}\n\nТеперь напиши свой вопрос:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    print(f"📨 NEW MESSAGE from chat {chat_id}: '{user_text}'")
    
    if chat_id not in user_modes:
        print(f"❓ User {chat_id} hasn't selected a theme yet")
        await update.message.reply_text("Сначала выбери тему:", reply_markup=get_theme_buttons())
        return

    mode = user_modes[chat_id]
    system_prompt = PROMPTS[mode]
    print(f"🎯 Selected mode: {mode}")
    print(f"💭 System prompt: {system_prompt[:50]}...")

    try:
        # Проверяем наличие API ключа
        if not OPENROUTER_API_KEY or len(OPENROUTER_API_KEY.strip()) < 10:
            print("❌ OpenRouter API key is missing or too short!")
            await update.message.reply_text("⚠️ Сервис временно недоступен. Разработчик уже исправляет проблему.")
            return

        print(f"📤 Sending request to OpenRouter with mode: {mode}")
        print(f"📝 User query: {user_text[:50]}...")

        # Добавляем таймаут и проверяем статус
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY.strip()}",
                "Content-Type": "application/json",
                "HTTP-Referer": WEBHOOK_URL,
                "X-Title": "Telegram Multibot"
            },
            json={
                "model": "qwen/qwen-1.5-1.8b-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ]
            },
            timeout=30
        )
        
        print(f"📥 OpenRouter response status: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            answer = response_data["choices"][0]["message"]["content"]
            print(f"✅ Got answer from Qwen: {answer[:100]}...")
            await update.message.reply_text(answer)
        else:
            error_detail = response.text[:200] if response.text else "No error details"
            print(f"❌ OpenRouter error ({response.status_code}): {error_detail}")
            
            if response.status_code == 401:
                await update.message.reply_text("🔒 Ошибка авторизации. Проверьте API ключ OpenRouter.")
            elif response.status_code == 404:
                await update.message.reply_text("🔍 Модель не найдена. Проверьте название модели в OpenRouter.")
            elif response.status_code == 429:
                await update.message.reply_text("⏳ Слишком много запросов. Попробуй через минуту.")
            else:
                await update.message.reply_text(f"⚠️ Ошибка {response.status_code}. Разработчик уже в курсе.")
                
    except requests.exceptions.Timeout:
        print("⏱️ Request to OpenRouter timed out after 30 seconds")
        await update.message.reply_text("⏱️ Запрос выполняется дольше обычного. Попробуй повторить через минуту.")
    except requests.exceptions.ConnectionError as e:
        print(f"🌐 Connection error to OpenRouter: {str(e)}")
        await update.message.reply_text("🌐 Проблемы с подключением к сервису. Попробуй позже.")
    except json.JSONDecodeError as e:
        print(f"🧩 JSON decode error: {str(e)}")
        print(f"	Response text: {response.text[:500] if 'response' in locals() else 'No response'}")
        await update.message.reply_text("🧩 Получен некорректный ответ от сервера. Разработчик уже исправляет проблему.")
    except Exception as e:
        print(f"🚨 General error in handle_message: {str(e)}")
        traceback.print_exc()
        await update.message.reply_text("⚠️ Произошла неожиданная ошибка. Разработчик уже в курсе.")

# Webhook endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        print("🔍 Received webhook request")
        
        # Получаем данные как словарь
        data = request.get_json()
        if data is None:
            print("❌ No JSON data received")
            return jsonify({"error": "No JSON data"}), 400
        
        print(f"📥 Webhook data: {json.dumps(data, indent=2)}")
        
        # Преобразуем в объект Update
        update = Update.de_json(data, application.bot)
        
        # Обрабатываем асинхронно
        asyncio.run(application.process_update(update))
        
        print("✅ Webhook processed successfully")
        return jsonify({"ok": True})
    
    except Exception as e:
        print(f"🚨 WEBHOOK ERROR: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Глобальная переменная для application
application = None

def init_bot():
    global application
    
    # Проверяем токен
    if not TELEGRAM_BOT_TOKEN or len(TELEGRAM_BOT_TOKEN.strip()) < 10:
        print("❌ TELEGRAM_BOT_TOKEN is missing or invalid!")
        raise ValueError("TELEGRAM_BOT_TOKEN is not set correctly")
    
    # Инициализация бота
    application = Application.builder().token(TELEGRAM_BOT_TOKEN.strip()).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Bot initialized successfully")
    return application

# Запуск
if __name__ == "__main__":
    print(f"✅ Starting Flask on port {PORT}")
    
    # Инициализируем бота
    application = init_bot()
    
    # Запускаем Flask
    app.run(host="0.0.0.0", port=PORT, debug=False)
