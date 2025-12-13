import os
import asyncio
import requests
import json
import traceback
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============ НАСТРОЙКИ — БЕРЕМ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ============
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# Убираем пробелы в URL с помощью strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://telegram-multibot.onrender.com/webhook").strip()
# ===================================================================

app = Flask(__name__)
app.config['WEBHOOK_SET'] = False

# Health check endpoint
@app.route('/')
def health_check():
    return jsonify({"status": "ok", "message": "Bot is running"})

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

    if chat_id not in user_modes:
        await update.message.reply_text("Сначала выбери тему:", reply_markup=get_theme_buttons())
        return

    mode = user_modes[chat_id]
    system_prompt = PROMPTS[mode]

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://t.me/your_bot",
                "X-Title": "Telegram Multibot"
            },
            json={
                "model": "qwen/qwen-1_8b-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ]
            },
            timeout=15
        )
        if response.status_code == 200:
            answer = response.json()["choices"][0]["message"]["content"]
            await update.message.reply_text(answer)
        else:
            await update.message.reply_text("⚠️ Не удалось получить ответ. Попробуй позже.")
    except Exception as e:
        await update.message.reply_text("⚠️ Ошибка соединения. Попробуй снова.")

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
        
        # Логируем для отладки
        print(f"📥 Webhook  {json.dumps(data, indent=2)}")
        
        # Преобразуем в объект Update
        update = Update.de_json(data, application.bot)
        
        # Асинхронная обработка
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(application.process_update(update))
        finally:
            loop.close()
        
        print("✅ Webhook processed successfully")
        return jsonify({"ok": True})
    
    except Exception as e:
        print(f"🚨 WEBHOOK ERROR: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Глобальная переменная для бота
application = None

# Функция инициализации бота
def init_bot():
    global application
    
    # Инициализация бота
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Инициализация приложения
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(application.initialize())
    
    print("✅ Bot initialized successfully")

# Функция установки webhook
def setup_webhook():
    global application
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(application.bot.set_webhook(url=WEBHOOK_URL))
        print(f"✅ Webhook correctly set to: '{WEBHOOK_URL}'")
        app.config['WEBHOOK_SET'] = True
    except Exception as e:
        print(f"⚠️ Failed to set webhook: {e}")
        traceback.print_exc()

# Запуск
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"✅ Starting Flask on port {port}")
    
    # Инициализируем бота
    init_bot()
    
    # Устанавливаем webhook
    setup_webhook()
    
    app.run(host="0.0.0.0", port=port, debug=False)
