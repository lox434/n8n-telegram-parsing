"""
Тесты для модуля шифрования
"""

from crypto_module import CryptoModule


def test_basic_encryption():
    """Тест базового шифрования/дешифрования"""
    print("=== Тест 1: Базовое шифрование ===")
    
    original = "Hello, World!"
    print(f"Оригинал: {original}")
    
    encrypted = CryptoModule.encrypt(original)
    print(f"Зашифровано: {encrypted}")
    
    decrypted = CryptoModule.decrypt(encrypted)
    print(f"Расшифровано: {decrypted}")
    
    assert original == decrypted, "Ошибка: текст не совпадает после дешифрования!"
    print("✅ Тест пройден\n")


def test_russian_text():
    """Тест с русским текстом"""
    print("=== Тест 2: Русский текст ===")
    
    original = "Привет, мир! Как дела?"
    print(f"Оригинал: {original}")
    
    encrypted = CryptoModule.encrypt(original)
    print(f"Зашифровано: {encrypted}")
    
    decrypted = CryptoModule.decrypt(encrypted)
    print(f"Расшифровано: {decrypted}")
    
    assert original == decrypted, "Ошибка: текст не совпадает после дешифрования!"
    print("✅ Тест пройден\n")


def test_long_text():
    """Тест с длинным текстом"""
    print("=== Тест 3: Длинный текст ===")
    
    original = """Это длинный текст для проверки шифрования.
Он содержит несколько строк.
И различные символы: !@#$%^&*()
А также цифры: 1234567890"""
    
    print(f"Оригинал ({len(original)} символов):")
    print(original)
    
    encrypted = CryptoModule.encrypt(original)
    print(f"\nЗашифровано ({len(encrypted)} символов):")
    print(encrypted)
    
    decrypted = CryptoModule.decrypt(encrypted)
    print(f"\nРасшифровано ({len(decrypted)} символов):")
    print(decrypted)
    
    assert original == decrypted, "Ошибка: текст не совпадает после дешифрования!"
    print("✅ Тест пройден\n")


def test_encrypted_prompt():
    """Тест создания зашифрованного промпта"""
    print("=== Тест 4: Зашифрованный промпт ===")
    
    user_query = "Напиши короткое стихотворение про кота"
    print(f"Запрос пользователя: {user_query}")
    
    prompt = CryptoModule.create_encrypted_prompt(user_query)
    print(f"\nПолный промпт для AI:")
    print(prompt)
    print("✅ Тест пройден\n")


def test_special_characters():
    """Тест со специальными символами"""
    print("=== Тест 5: Специальные символы ===")
    
    original = "Test with emoji: 😀🎉🔥 and symbols: <>{}[]|\\/@#$%"
    print(f"Оригинал: {original}")
    
    encrypted = CryptoModule.encrypt(original)
    print(f"Зашифровано: {encrypted}")
    
    decrypted = CryptoModule.decrypt(encrypted)
    print(f"Расшифровано: {decrypted}")
    
    assert original == decrypted, "Ошибка: текст не совпадает после дешифрования!"
    print("✅ Тест пройден\n")


if __name__ == "__main__":
    print("Запуск тестов модуля шифрования\n")
    
    test_basic_encryption()
    test_russian_text()
    test_long_text()
    test_encrypted_prompt()
    test_special_characters()
    
    print("=" * 50)
    print("✅ Все тесты успешно пройдены!")
    print("=" * 50)
