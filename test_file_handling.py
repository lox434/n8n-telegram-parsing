"""
Тестовый скрипт для проверки функционала обработки файлов
"""
import asyncio
import os
from pathlib import Path

async def test_file_structure():
    """Проверка создания необходимых директорий"""
    print("🔍 Проверка структуры папок...")
    
    # Проверяем/создаем temp_downloads
    temp_downloads = Path("./temp_downloads")
    temp_downloads.mkdir(exist_ok=True)
    print(f"✅ Папка temp_downloads: {temp_downloads.absolute()}")
    
    # Проверяем/создаем temp_photos
    temp_photos = Path("./temp_photos")
    temp_photos.mkdir(exist_ok=True)
    print(f"✅ Папка temp_photos: {temp_photos.absolute()}")
    
    # Проверяем user_projects
    user_projects = Path("./user_projects")
    user_projects.mkdir(exist_ok=True)
    print(f"✅ Папка user_projects: {user_projects.absolute()}")
    
    print("\n✅ Все необходимые папки созданы!")

async def test_file_operations():
    """Тест операций с файлами"""
    print("\n🔍 Тестирование операций с файлами...")
    
    test_user = "test_user_123"
    download_path = Path(f"./temp_downloads/{test_user}")
    download_path.mkdir(parents=True, exist_ok=True)
    
    # Создаем тестовый файл
    test_file = download_path / "test_file.txt"
    test_file.write_text("Это тестовый файл для проверки функционала", encoding='utf-8')
    print(f"✅ Создан тестовый файл: {test_file}")
    
    # Проверяем чтение
    content = test_file.read_text(encoding='utf-8')
    print(f"✅ Содержимое файла: {content[:50]}...")
    
    # Проверяем удаление
    test_file.unlink()
    print(f"✅ Файл удален: {test_file}")
    
    # Очистка
    if download_path.exists() and not any(download_path.iterdir()):
        download_path.rmdir()
        print(f"✅ Пустая папка удалена: {download_path}")
    
    print("\n✅ Все операции с файлами работают корректно!")

async def test_imports():
    """Проверка импортов"""
    print("\n🔍 Проверка импортов...")
    
    try:
        from bot import browser_manager, active_requests
        print("✅ bot.py импортируется корректно")
    except Exception as e:
        print(f"❌ Ошибка импорта bot.py: {e}")
        return False
    
    try:
        from browser_manager import BrowserManager
        print("✅ browser_manager.py импортируется корректно")
    except Exception as e:
        print(f"❌ Ошибка импорта browser_manager.py: {e}")
        return False
    
    print("\n✅ Все импорты работают!")
    return True

async def main():
    """Главная функция тестирования"""
    print("=" * 60)
    print("🚀 ТЕСТИРОВАНИЕ ФУНКЦИОНАЛА ОБРАБОТКИ ФАЙЛОВ")
    print("=" * 60)
    
    await test_file_structure()
    await test_file_operations()
    
    imports_ok = await test_imports()
    
    print("\n" + "=" * 60)
    if imports_ok:
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    else:
        print("⚠️ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
