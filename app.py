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
                "HTTP-Referer": "https://t.me/your_bot",
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
