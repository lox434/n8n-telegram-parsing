"""
Модуль для шифрования/дешифрования сообщений с ChatGPT
Использует Base64 + ROT13 для обфускации
"""

import base64


class CryptoModule:
    """Класс для шифрования и дешифрования текста"""
    
    @staticmethod
    def _rot13(text: str) -> str:
        """ROT13 шифрование (сдвиг на 13 позиций)"""
        result = []
        for char in text:
            if 'a' <= char <= 'z':
                result.append(chr((ord(char) - ord('a') + 13) % 26 + ord('a')))
            elif 'A' <= char <= 'Z':
                result.append(chr((ord(char) - ord('A') + 13) % 26 + ord('A')))
            else:
                result.append(char)
        return ''.join(result)
    
    @staticmethod
    def encrypt(text: str) -> str:
        """
        Шифрование текста: ROT13 -> Base64
        
        Args:
            text: Исходный текст
            
        Returns:
            Зашифрованный текст
        """
        # Применяем ROT13
        rot13_text = CryptoModule._rot13(text)
        
        # Кодируем в Base64
        base64_bytes = base64.b64encode(rot13_text.encode('utf-8'))
        encrypted_text = base64_bytes.decode('utf-8')
        
        return encrypted_text
    
    @staticmethod
    def decrypt(encrypted_text: str) -> str:
        """
        Дешифрование текста: Base64 -> ROT13
        
        Args:
            encrypted_text: Зашифрованный текст
            
        Returns:
            Расшифрованный текст
        """
        try:
            # Декодируем из Base64
            base64_bytes = encrypted_text.encode('utf-8')
            decoded_bytes = base64.b64decode(base64_bytes)
            rot13_text = decoded_bytes.decode('utf-8')
            
            # Применяем ROT13 (обратное преобразование)
            decrypted_text = CryptoModule._rot13(rot13_text)
            
            return decrypted_text
        except Exception as e:
            # Если не удалось расшифровать, возвращаем как есть
            return encrypted_text
    
    @staticmethod
    def create_encrypted_prompt(user_query: str) -> str:
        """
        Создает зашифрованный промпт с инструкцией для AI
        
        Args:
            user_query: Запрос пользователя
            
        Returns:
            Полный промпт с инструкцией и зашифрованным запросом
        """
        # Шифруем запрос пользователя
        encrypted_query = CryptoModule.encrypt(user_query)
        
        # Создаем промпт с инструкцией (упрощенная версия)
        prompt = f"""Decode: Base64 -> ROT13. Answer. Encode: ROT13 -> Base64. Reply only Base64:

{encrypted_query}"""
        
        return prompt
