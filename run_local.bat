@echo off
chcp 65001 >nul
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Installing Playwright browsers...
playwright install chromium

echo.
echo Starting bot...
python bot.py
