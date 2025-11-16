"""
Скрипт для настройки профиля браузера для Docker
Запустите локально, авторизуйтесь в ChatGPT, затем скопируйте профиль в Docker
"""
import asyncio
from playwright.async_api import async_playwright
import os

async def setup_profile():
    print("="*60)
    print("Настройка профиля для Docker")
    print("="*60)
    
    profile_path = './chromium_profile'
    
    playwright = await async_playwright().start()
    
    # Запуск браузера с профилем (видимый режим)
    browser = await playwright.chromium.launch_persistent_context(
        user_data_dir=profile_path,
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    
    # Открываем ChatGPT
    page = browser.pages[0] if browser.pages else await browser.new_page()
    await page.goto('https://chatgpt.com/')
    
    print("\n" + "="*60)
    print("✅ Браузер открыт!")
    print("\nИнструкции:")
    print("1. Авторизуйтесь в ChatGPT")
    print("2. Пройдите капчу если нужно")
    print("3. Убедитесь что вы на главной странице ChatGPT")
    print("4. Закройте браузер")
    print("\nПрофиль сохранится в папке: chromium_profile")
    print("Этот профиль будет использоваться в Docker")
    print("="*60 + "\n")
    
    # Ждем пока пользователь не закроет браузер
    try:
        while True:
            await asyncio.sleep(1)
            if not browser.pages:
                break
    except:
        pass
    
    await browser.close()
    await playwright.stop()
    
    print("\n✅ Профиль сохранен!")
    print(f"📁 Путь: {os.path.abspath(profile_path)}")
    print("\nТеперь можете запустить Docker:")
    print("docker-compose up -d --build")

if __name__ == '__main__':
    asyncio.run(setup_profile())
