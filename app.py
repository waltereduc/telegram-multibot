# app.py
import os
import requests
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============ НАСТРОЙКИ — ВСТАВЬ СВОИ ТОКЕНЫ ЗДЕСЬ ============
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # ← сюда вставь токен от @BotFather
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")  # ← сюда вставь ключ от OpenRouter
# =============================================================

app = Flask(__name__)

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

# Хранилище выбора пользователя (в памяти — без БД)
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

# Обработка /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Выбери тему, и я помогу:",
        reply_markup=get_theme_buttons()
    )

# Обработка выбора темы
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
    await query.edit_message_text(
        text=f"Выбрана тема: {theme_names[mode]}\n\nТеперь напиши свой вопрос:"
    )

# Обработка текстового сообщения
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    # Если тема не выбрана — напомним
    if chat_id not in user_modes:
        await update.message.reply_text(
            "Сначала выбери тему:",
            reply_markup=get_theme_buttons()
        )
        return

    mode = user_modes[chat_id]
    system_prompt = PROMPTS[mode]

    # Запрос к OpenRouter (Qwen)
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://t.me/your_bot",  # можно оставить как есть
                "X-Title": "Telegram Multibot"
            },
            json={
                "model": "qwen/qwen-1_8b-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ]
            }
        )
        if response.status_code == 200:
            answer = response.json()["choices"][0]["message"]["content"]
            await update.message.reply_text(answer)
        else:
            await update.message.reply_text("⚠️ Не удалось получить ответ. Попробуй позже.")
    except Exception as e:
        await update.message.reply_text("⚠️ Ошибка соединения. Попробуй снова.")

# Flask webhook endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = Update.de_json(json_str, application.bot)
    application.process_update(update)
    return jsonify({"ok": True})

# Инициализация Telegram-бота
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == "__main__":
    # Для локального запуска (не используется на Render)

    app.run(port=5000)
