# app.py — финальная рабочая версия для Render
import os
import threading
import asyncio
import requests
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

# === Создаём фоновый event loop ===
loop = asyncio.new_event_loop()
threading.Thread(target=loop.run_forever, daemon=True).start()

# === Обработчики ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я нейросеть-бот. Задай вопрос.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print(f"📩 Получено сообщение: '{user_text}'")
    
    try:
        # Запрос к Qwen3-1.7B через Hugging Face
        headers = {
            "Authorization": f"Bearer {os.getenv('HUGGINGFACE_API_KEY')}",
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": f"<|im_start|>system\nТы дружелюбный помощник.<|im_end|>\n<|im_start|>user\n{user_text}<|im_end|>\n<|im_start|>assistant",
            "parameters": {
                "max_new_tokens": 100,
                "temperature": 0.7,
                "return_full_text": False,
                "do_sample": True
            }
        }
        
        print("🔄 Отправляю запрос в Hugging Face...")
        response = requests.post(
            "https://api-inference.huggingface.co/models/Qwen/Qwen3-1.7B",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"📡 Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            # Обработка разных форматов ответа
            if isinstance(result, list) and len(result) > 0:
                answer = result[0].get("generated_text", "").strip()
            else:
                answer = result.get("generated_text", "").strip()
            
            print(f"✅ Ответ нейросети: '{answer}'")
            
            if not answer:
                answer = "Извините, я не смог сформулировать ответ. Попробуйте задать вопрос по-другому."
            
            await update.message.reply_text(answer)
        else:
            error_detail = response.json().get("error", "Неизвестная ошибка")
            print(f"❌ Ошибка API: {error_detail}")
            await update.message.reply_text(f"⚠️ Не удалось получить ответ: {error_detail}")
            
    except Exception as e:
        print(f"🔥 КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
        import traceback
        print(traceback.format_exc())
        await update.message.reply_text("🚨 Произошла внутренняя ошибка. Попробуй позже.")
# Регистрируем обработчики
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# === Вебхук: установка ===
@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    async def _set_hook():
        return await application.bot.set_webhook(WEBHOOK_URL)
    
    future = asyncio.run_coroutine_threadsafe(_set_hook(), loop)
    result = future.result()
    return f"✅ Webhook set to {WEBHOOK_URL}: {result}"

# === Вебхук: обработка ===
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    update = Update.de_json(data, application.bot)
    
    # Безопасно отправляем задачу в фоновый event loop
    asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
    return jsonify({"ok": True})

# === Проверка здоровья ===
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "webhook_url": WEBHOOK_URL,
        "event_loop": "running" if loop.is_running() else "stopped"
    })

if __name__ == "__main__":
    # Запускаем приложение
    app.run(host="0.0.0.0", port=PORT, threaded=True)


