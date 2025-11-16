FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Копирование requirements и установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY bot.py browser_manager.py ./

# Создание директорий для профилей и проектов
RUN mkdir -p /app/chromium_profile /app/user_projects /app/temp_photos

# Переменные окружения
ENV PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]
