import os
import requests
import json
import traceback
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ============ НАСТРОЙКИ ============
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
PORT = int(os.getenv("PORT", 10000))
# ===================================

if not TELEGRAM_BOT_TOKEN or len(TELEGRAM_BOT_TOKEN.strip()) < 10:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN is missing or invalid!")
if not WEBHOOK_URL:
    raise ValueError("❌ WEBHOOK_URL must be set (e.g., https://your-app.onrender.com)")

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

user_modes = {}

def get_theme_buttons():
    keyboard = [
        [InlineKeyboardButton("🌱 Объясни просто", callback_data="explain")],
        [InlineKeyboardButton("💬 Эмоциональная поддержка", callback_data="emotional")],
        [InlineKeyboardButton("👨‍👩‍👧 Совет родителям", callback_data="parenting")],
        [InlineKeyboardButton("⚖️ Этическая дилемма", callback_data="ethics")]
    ]
    return InlineKeyboardMarkup(keyboard)

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
        if not OPENROUTER_API_KEY or len(OPENROUTER_API_KEY.strip()) < 10:
            await update.message.reply_text("⚠️ Сервис временно недоступен.")
            return

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

        if response.status_code == 200:
            answer = response.json()["choices"][0]["message"]["content"]
            await update.message.reply_text(answer)
        else:
            if response.status_code == 401:
                await update.message.reply_text("🔒 Неверный API-ключ OpenRouter.")
            elif response.status_code == 429:
                await update.message.reply_text("⏳ Слишком много запросов. Попробуй позже.")
            else:
                await update.message.reply_text("⚠️ Ошибка нейросети. Попробуй позже.")

    except requests.exceptions.Timeout:
        await update.message.reply_text("⏱️ Таймаут. Попробуй позже.")
    except requests.exceptions.ConnectionError:
        await update.message.reply_text("🌐 Нет связи с нейросетью.")
    except Exception as e:
        print(f"🚨 ERROR: {e}")
        traceback.print_exc()
        await update.message.reply_text("⚠️ Внутренняя ошибка.")

# === ГЛАВНОЕ: ИСПРАВЛЕННЫЙ ЗАПУСК ===
async def main():
    print("🚀 Starting Telegram bot...")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN.strip()).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(lambda u, c: print(f"⛔ Error: {c.error}"))

    # 🔑 КЛЮЧЕВОЕ: инициализируем Application (и его Updater)
    await application.initialize()

    print(f"🔗 Setting webhook: {WEBHOOK_URL}")
    await application.bot.set_webhook(url=WEBHOOK_URL)

    print(f"👂 Listening on 0.0.0.0:{PORT}")
    await application.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL,
        drop_pending_updates=True
    )
    await application.start()
    print("✅ Bot is running!")

    try:
        await asyncio.Event().wait()
    finally:
        await application.stop()
        await application.shutdown()

# === ЗАПУСК БЕЗ asyncio.run() ===
def main_wrapper():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()

if __name__ == "__main__":
    main_wrapper()
