"""
Скрипт для первоначальной настройки профиля браузера
Запусти его, авторизуйся в ChatGPT, пройди капчу, затем закрой браузер
"""
import asyncio
from playwright.async_api import async_playwright

async def setup_profile():
    print("Запуск браузера для настройки профиля...")
    
    playwright = await async_playwright().start()
    
    # Запуск браузера с профилем
    browser = await playwright.chromium.launch_persistent_context(
        user_data_dir='./chromium_profile',
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    
    # Открываем ChatGPT
    page = browser.pages[0]
    await page.goto('https://chatgpt.com/')
    
    print("\n" + "="*60)
    print("Браузер открыт!")
    print("Авторизуйся в ChatGPT и пройди капчу")
    print("После этого можешь закрыть браузер")
    print("Профиль сохранится автоматически")
    print("="*60 + "\n")
    
    # Ждем пока пользователь не закроет браузер
    try:
        while True:
            await asyncio.sleep(1)
    except:
        pass
    
    await browser.close()
    await playwright.stop()
    print("Профиль сохранен!")

if __name__ == '__main__':
    asyncio.run(setup_profile())
