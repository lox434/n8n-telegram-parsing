"""
Скрипт для тестирования соединения с Telegram API
"""
import os
import asyncio
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import NetworkError, TimedOut

load_dotenv()

async def test_connection():
    """Тестирование соединения с Telegram"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN не установлен!")
        return
    
    print("🔄 Тестирование соединения с Telegram API...")
    
    try:
        bot = Bot(token=token)
        
        # Получаем информацию о боте
        me = await bot.get_me()
        print(f"✅ Соединение успешно!")
        print(f"   Имя бота: {me.first_name}")
        print(f"   Username: @{me.username}")
        print(f"   ID: {me.id}")
        
        # Проверяем webhook
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url:
            print(f"⚠️  Webhook установлен: {webhook_info.url}")
            print("   Для polling режима нужно удалить webhook:")
            print("   await bot.delete_webhook()")
        else:
            print("✅ Webhook не установлен (polling режим)")
        
        return True
        
    except NetworkError as e:
        print(f"❌ Сетевая ошибка: {e}")
        print("   Проверьте интернет-соединение")
        return False
        
    except TimedOut as e:
        print(f"❌ Таймаут соединения: {e}")
        print("   Telegram API может быть недоступен")
        return False
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == '__main__':
    asyncio.run(test_connection())
