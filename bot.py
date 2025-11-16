import os
import logging
import re
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import NetworkError, TimedOut, RetryAfter
from browser_manager import BrowserManager
import asyncio

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Отключаем лишние логи для уменьшения шума
logging.getLogger('httpx').setLevel(logging.ERROR)
logging.getLogger('httpcore').setLevel(logging.ERROR)
logging.getLogger('apscheduler').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)

# Глобальный менеджер браузера
browser_manager = None

# Словарь для отслеживания активных запросов пользователей
active_requests = {}


def format_response_for_telegram(response: str) -> str:
    """
    Форматирование ответа ChatGPT для Telegram.
    Исправляет проблему склеивания кодовых блоков с текстом после них.
    """
    try:
        # Ищем паттерн "Копировать код" и извлекаем код после него
        if "Копировать код" in response or "Copy code" in response:
            # Разбиваем на части по "Копировать код"
            parts = re.split(r'(Копировать код|Copy code)', response)
            
            formatted_parts = []
            i = 0
            while i < len(parts):
                part = parts[i]
                
                # Если это текст "Копировать код"
                if part in ["Копировать код", "Copy code"]:
                    # Следующая часть содержит код
                    if i + 1 < len(parts):
                        code_block = parts[i + 1]
                        
                        # Извлекаем код до первого Q (Q1, Q2 и т.д.)
                        lines = code_block.split('\n')
                        
                        # Ищем где заканчивается код (первый Q)
                        code_lines = []
                        remaining_lines = []
                        found_q = False
                        
                        for idx, line in enumerate(lines):
                            # Если нашли строку начинающуюся с Q и цифры
                            if not found_q and re.match(r'^\s*Q\d+', line.strip(), re.IGNORECASE):
                                found_q = True
                                # Все что после Q - это обычный текст
                                remaining_lines = lines[idx:]
                                break
                            # Добавляем строку кода
                            code_lines.append(line)
                        
                        # Убираем пустые строки в начале кода
                        while code_lines and not code_lines[0].strip():
                            code_lines.pop(0)
                        
                        # Убираем пустые строки в конце кода
                        while code_lines and not code_lines[-1].strip():
                            code_lines.pop()
                        
                        # Форматируем код в markdown
                        if code_lines:
                            code_text = '\n'.join(code_lines)
                            formatted_parts.append(f"```\n{code_text}\n```")
                        
                        # Добавляем остальной текст после кода (вопросы Q1, Q2 и т.д.)
                        if remaining_lines:
                            remaining_text = '\n'.join(remaining_lines)
                            if remaining_text.strip():
                                formatted_parts.append(remaining_text.strip())
                        
                        i += 2  # Пропускаем "Копировать код" и блок кода
                        continue
                
                # Обычный текст
                if part.strip():
                    formatted_parts.append(part.strip())
                
                i += 1
            
            return '\n\n'.join(formatted_parts)
        
        # Если нет "Копировать код", возвращаем как есть
        return response
        
    except Exception as e:
        logger.error(f"Ошибка форматирования ответа: {e}")
        return response


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    welcome_message = (
        "🤖 <b>Добро пожаловать в ChatGPT Bot!</b>\n\n"
        "Я помогу вам общаться с ChatGPT прямо из Telegram.\n\n"
        "📝 <b>Возможности:</b>\n"
        "• Отправка текстовых запросов\n"
        "• Отправка изображений с описанием\n"
        "• Автоматическое создание проектов\n"
        "• Сохранение истории переписки\n\n"
        "⚡ <b>Команды:</b>\n"
        "/start - Показать это сообщение\n"
        "/help - Справка по использованию\n"
        "/status - Статус бота\n"
        "/clear - Очистить историю (скоро)\n\n"
        "💡 <b>Как использовать:</b>\n"
        "Просто отправьте мне текст или фото, и я передам запрос в ChatGPT!\n\n"
        "Для каждого пользователя создается отдельный проект."
    )
    await update.message.reply_text(welcome_message, parse_mode='HTML')


async def send_animated_text(update: Update, full_text: str, chunk_size: int = 100, delay: float = 0.5):
    """
    Отправляет текст с анимацией постепенного появления.
    Показывает индикатор 'печатает' и постепенно добавляет текст.
    """
    try:
        message = update.message
        bot = update.get_bot()
        
        # Показываем индикатор "печатает"
        await bot.send_chat_action(message.chat.id, "typing")
        
        # Отправляем начальное сообщение
        sent_message = await message.reply_text("✍️", parse_mode='Markdown')
        
        # Постепенно добавляем текст
        for i in range(0, len(full_text), chunk_size):
            # Показываем индикатор "печатает" перед каждым обновлением
            await bot.send_chat_action(message.chat.id, "typing")
            
            chunk = full_text[:i + chunk_size]
            try:
                await sent_message.edit_text(chunk, parse_mode='Markdown')
            except Exception as e:
                # Игнорируем ошибки если текст не изменился или слишком частые обновления
                logger.debug(f"Ошибка редактирования сообщения: {e}")
                pass
            
            await asyncio.sleep(delay)
        
        # Финальное обновление с полным текстом
        try:
            await sent_message.edit_text(full_text, parse_mode='Markdown')
        except:
            pass
            
    except Exception as e:
        logger.error(f"Ошибка анимации текста: {e}")
        # В случае ошибки просто отправляем текст обычным способом
        await message.reply_text(full_text, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "📖 <b>Справка по использованию</b>\n\n"
        "<b>Текстовые запросы:</b>\n"
        "Просто напишите свой вопрос, и я отправлю его в ChatGPT.\n"
        "Пример: <i>Расскажи про Python</i>\n\n"
        "<b>Изображения:</b>\n"
        "Отправьте фото с подписью или без.\n"
        "ChatGPT проанализирует изображение и ответит.\n\n"
        "<b>Проекты:</b>\n"
        "Для каждого пользователя автоматически создается проект.\n"
        "Вся история сохраняется в вашем проекте.\n\n"
        "⚠️ <b>Важно:</b>\n"
        "• Дождитесь ответа на предыдущий запрос\n"
        "• Генерация ответа может занять до 2 минут\n"
        "• История сохраняется локально\n\n"
        "❓ Возникли проблемы? Используйте /status"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /status"""
    user_id = str(update.effective_user.id)
    is_processing = user_id in active_requests and active_requests[user_id]
    
    status_text = (
        "📊 <b>Статус бота</b>\n\n"
        f"🔹 Браузер: {'✅ Активен' if browser_manager and browser_manager.browser else '❌ Не запущен'}\n"
        f"🔹 Ваш ID: <code>{user_id}</code>\n"
        f"🔹 Обработка запроса: {'⏳ Да' if is_processing else '✅ Нет'}\n"
        f"🔹 Активных запросов: {sum(1 for v in active_requests.values() if v)}\n\n"
        "Все системы работают нормально! 🚀"
    )
    await update.message.reply_text(status_text, parse_mode='HTML')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user = update.effective_user
    username = str(user.id)  # Используем Telegram ID
    query = update.message.text
    
    # Проверка на активный запрос
    if username in active_requests and active_requests[username]:
        await update.message.reply_text(
            "⏳ <b>Подождите!</b>\n\n"
            "Ваш предыдущий запрос еще обрабатывается.\n"
            "Пожалуйста, дождитесь ответа.",
            parse_mode='HTML'
        )
        return
    
    # Отмечаем что запрос в обработке
    active_requests[username] = True
    
    logger.info(f"Получен запрос от ID {username}: {query}")
    
    # Отправка уведомления о начале обработки
    processing_msg = await update.message.reply_text(
        "⏳ <b>Обрабатываю ваш запрос...</b>\n\n"
        "Это может занять до 2 минут.",
        parse_mode='HTML'
    )
    
    try:
        # Отправка запроса через браузер
        response, downloaded_files = await browser_manager.create_project_and_send_query(username, query)
        
        # Удаление сообщения о обработке
        await processing_msg.delete()
        
        # Форматируем ответ для Telegram
        formatted_response = format_response_for_telegram(response)
        
        # Отправка ответа с анимацией (разбиваем на части если слишком длинный)
        if len(formatted_response) > 4096:
            # Для очень длинных ответов отправляем по частям без анимации
            for i in range(0, len(formatted_response), 4096):
                await update.message.reply_text(formatted_response[i:i+4096], parse_mode='Markdown')
        else:
            # Для обычных ответов используем анимацию
            await send_animated_text(update, formatted_response)
        
        # Отправка файлов если есть
        if downloaded_files:
            await update.message.reply_text(f"📎 Отправляю {len(downloaded_files)} файл(ов)...")
            
            for filepath in downloaded_files:
                try:
                    # Отправляем файл в Telegram
                    with open(filepath, 'rb') as f:
                        await update.message.reply_document(document=f, filename=os.path.basename(filepath))
                    
                    logger.info(f"Файл отправлен: {filepath}")
                    
                    # Удаляем файл после отправки
                    os.remove(filepath)
                    logger.info(f"Файл удален: {filepath}")
                    
                except Exception as file_error:
                    logger.error(f"Ошибка отправки файла {filepath}: {file_error}")
                    await update.message.reply_text(f"⚠️ Не удалось отправить файл: {os.path.basename(filepath)}")
            
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        await processing_msg.edit_text(f"❌ <b>Произошла ошибка:</b>\n\n{str(e)}", parse_mode='HTML')
    finally:
        # Снимаем флаг обработки
        active_requests[username] = False


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий"""
    user = update.effective_user
    username = str(user.id)
    caption = update.message.caption or ""
    
    # Проверка на активный запрос
    if username in active_requests and active_requests[username]:
        await update.message.reply_text(
            "⏳ <b>Подождите!</b>\n\n"
            "Ваш предыдущий запрос еще обрабатывается.\n"
            "Пожалуйста, дождитесь ответа.",
            parse_mode='HTML'
        )
        return
    
    # Отмечаем что запрос в обработке
    active_requests[username] = True
    
    logger.info(f"Получено фото от ID {username}" + (f" с текстом: {caption}" if caption else ""))
    
    # Отправка уведомления о начале обработки
    processing_msg = await update.message.reply_text(
        "📸 <b>Обрабатываю фото...</b>\n\n"
        "Загружаю изображение в ChatGPT...",
        parse_mode='HTML'
    )
    
    try:
        # Получаем фото (берем самое большое разрешение)
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()
        
        # Скачиваем фото
        import os
        os.makedirs("temp_photos", exist_ok=True)
        photo_path = f"temp_photos/{username}_{photo.file_id}.jpg"
        await photo_file.download_to_drive(photo_path)
        
        logger.info(f"Фото сохранено: {photo_path}")
        
        # Отправка фото и текста в ChatGPT
        response, downloaded_files = await browser_manager.send_photo_query(username, photo_path, caption)
        
        # Удаление временного файла
        try:
            os.remove(photo_path)
        except:
            pass
        
        # Удаление сообщения о обработке
        await processing_msg.delete()
        
        # Отправка ответа
        if len(response) > 4096:
            for i in range(0, len(response), 4096):
                await update.message.reply_text(response[i:i+4096])
        else:
            await update.message.reply_text(f"🖼️ <b>Ответ ChatGPT:</b>\n\n{response}", parse_mode='HTML')
        
        # Отправка файлов если есть
        if downloaded_files:
            await update.message.reply_text(f"📎 Отправляю {len(downloaded_files)} файл(ов)...")
            
            for filepath in downloaded_files:
                try:
                    # Отправляем файл в Telegram
                    with open(filepath, 'rb') as f:
                        await update.message.reply_document(document=f, filename=os.path.basename(filepath))
                    
                    logger.info(f"Файл отправлен: {filepath}")
                    
                    # Удаляем файл после отправки
                    os.remove(filepath)
                    logger.info(f"Файл удален: {filepath}")
                    
                except Exception as file_error:
                    logger.error(f"Ошибка отправки файла {filepath}: {file_error}")
                    await update.message.reply_text(f"⚠️ Не удалось отправить файл: {os.path.basename(filepath)}")
            
    except Exception as e:
        logger.error(f"Ошибка обработки фото: {e}")
        await processing_msg.edit_text(f"❌ <b>Произошла ошибка:</b>\n\n{str(e)}", parse_mode='HTML')
    finally:
        # Снимаем флаг обработки
        active_requests[username] = False


async def post_init(application: Application):
    """Инициализация после запуска бота"""
    global browser_manager
    
    # Установка команд бота
    commands = [
        BotCommand("start", "Начать работу с ботом"),
        BotCommand("help", "Справка по использованию"),
        BotCommand("status", "Проверить статус бота"),
    ]
    await application.bot.set_my_commands(commands)
    
    profile_path = os.getenv('CHATGPT_PROFILE_PATH', './chromium_profile')
    # Определяем режим: headless для Docker, видимый для локального запуска
    is_docker = os.path.exists('/.dockerenv')
    headless_mode = is_docker or os.getenv('HEADLESS', 'false').lower() == 'true'
    
    browser_manager = BrowserManager(profile_path, headless=headless_mode)
    
    logger.info(f"Запуск браузера (headless={headless_mode})...")
    success = await browser_manager.start()
    
    if success:
        logger.info("Браузер успешно запущен и готов к работе")
    else:
        logger.error("Не удалось запустить браузер")


async def post_shutdown(application: Application):
    """Очистка ресурсов при остановке"""
    global browser_manager
    if browser_manager:
        try:
            logger.info("Остановка браузера...")
            await asyncio.wait_for(browser_manager.stop(), timeout=5.0)
            logger.info("Браузер успешно остановлен")
        except asyncio.TimeoutError:
            logger.warning("Таймаут при остановке браузера")
        except Exception as e:
            logger.error(f"Ошибка при остановке браузера: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик ошибок"""
    logger.error(f"Ошибка при обработке обновления: {context.error}")
    
    # Игнорируем сетевые ошибки - они обрабатываются автоматически
    if isinstance(context.error, (NetworkError, TimedOut)):
        logger.warning("Сетевая ошибка - повторная попытка будет выполнена автоматически")
        return
    
    # Обработка ошибки rate limit
    if isinstance(context.error, RetryAfter):
        logger.warning(f"Rate limit - ожидание {context.error.retry_after} секунд")
        return
    
    # Для других ошибок пытаемся уведомить пользователя
    if update and isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Произошла временная ошибка. Попробуйте еще раз через несколько секунд."
            )
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение об ошибке: {e}")


def main():
    """Запуск бота"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        return
    
    # Создание приложения с улучшенными настройками для стабильности
    application = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .get_updates_connect_timeout(30.0)
        .get_updates_read_timeout(30.0)
        .get_updates_write_timeout(30.0)
        .get_updates_pool_timeout(30.0)
        .build()
    )
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Регистрация обработчика ошибок
    application.add_error_handler(error_handler)
    
    # Запуск бота с улучшенными параметрами polling
    logger.info("Бот запущен...")
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,  # Игнорировать старые обновления при запуске
            pool_timeout=30.0,          # Таймаут для long polling
        )
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки (Ctrl+C)")
    finally:
        logger.info("Завершение работы бота...")


if __name__ == '__main__':
    main()
