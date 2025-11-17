import os
import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BrowserManager:
    def __init__(self, profile_path: str, headless: bool = False):
        self.profile_path = profile_path
        self.playwright = None
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.first_request = True  # Флаг для первого запроса
        self.headless = headless  # Режим работы браузера
        self.current_user_id = None  # Текущий активный пользователь
        
    async def _save_debug_snapshot(self, page: Page, action: str = ""):
        """Сохранение отладочного снимка страницы"""
        try:
            import os
            os.makedirs('./debug', exist_ok=True)
            
            # Сохраняем HTML
            html_content = await page.content()
            with open('./debug/current_page.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Сохраняем скриншот
            await page.screenshot(path='./debug/current_screenshot.png', full_page=True)
            
            # Сохраняем информацию
            with open('./debug/current_info.txt', 'w', encoding='utf-8') as f:
                f.write(f"Action: {action}\n")
                f.write(f"URL: {page.url}\n")
                f.write(f"Title: {await page.title()}\n")
            
            logger.debug(f"Debug snapshot saved: {action}")
        except Exception as e:
            logger.debug(f"Failed to save debug snapshot: {e}")
        
    async def start(self):
        """Запуск браузера с сохраненным профилем"""
        try:
            self.playwright = await async_playwright().start()
            
            # Запуск Chromium с профилем
            self.browser = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.profile_path,
                headless=self.headless,  # Видимый или headless режим
                slow_mo=500 if not self.headless else 0,  # Замедление только для видимого режима
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            )
            
            logger.info("Браузер успешно запущен")
            
            # Сразу открываем ChatGPT
            pages = self.browser.pages
            if pages:
                page = pages[0]
                logger.info("Открытие ChatGPT...")
                await page.goto('https://chatgpt.com/', wait_until='domcontentloaded', timeout=60000)
                
                # Ждем исчезновения спиннера загрузки
                logger.info("Ожидание завершения загрузки...")
                await asyncio.sleep(10)
                
                await self._save_debug_snapshot(page, "После открытия ChatGPT")
                
                # Проверяем и проходим капчу (с ожиданием загрузки)
                await self._check_and_solve_captcha(page)
                await self._save_debug_snapshot(page, "После проверки капчи")
                
                logger.info("ChatGPT открыт и готов к работе")
            else:
                logger.warning("Нет открытых страниц, создаем новую...")
                page = await self.browser.new_page()
                await page.goto('https://chatgpt.com/', wait_until='domcontentloaded', timeout=60000)
                await self._check_and_solve_captcha(page)
            
            return True
        except Exception as e:
            logger.error(f"Ошибка запуска браузера: {e}", exc_info=True)
            return False
    
    async def send_photo_query(self, username: str, photo_path: str, caption: str = "") -> tuple:
        """Отправка фото с текстом в ChatGPT
        
        Returns:
            tuple: (response_text, list_of_downloaded_files)
        """
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Создание директории проекта пользователя
                user_project_path = Path(f"./user_projects/{username}")
                user_project_path.mkdir(parents=True, exist_ok=True)
                
                # Используем существующую страницу
                pages = self.browser.pages
                if pages:
                    page: Page = pages[0]
                else:
                    page: Page = await self.browser.new_page()
                    await page.goto('https://chatgpt.com/', wait_until='domcontentloaded', timeout=60000)
                    await asyncio.sleep(3)
                
                logger.info(f"Отправка фото от пользователя {username}")
                
                # Обновление страницы только при первом запросе
                if self.first_request:
                    logger.info("Ожидание 5 секунд перед обновлением...")
                    await asyncio.sleep(5)
                    logger.info("Обновление страницы (F5)...")
                    await page.keyboard.press('F5')
                    logger.info("Ожидание полной загрузки страницы...")
                    
                    # Ждем исчезновения спиннера или появления поля ввода
                    for i in range(15):
                        await asyncio.sleep(1)
                        # Проверяем есть ли поле ввода
                        input_check = await page.query_selector('textarea, div[contenteditable="true"]')
                        if input_check:
                            logger.info(f"Страница загружена через {i+1} сек")
                            break
                        if i % 3 == 0:
                            logger.info(f"Ожидание загрузки... ({i+1} сек)")
                    
                    await self._save_debug_snapshot(page, "После обновления F5 (фото)")
                    self.first_request = False
                
                # Проверка и создание/открытие проекта (только если не в чате)
                project_exists = await self._check_and_open_project(page, username)
                await self._save_debug_snapshot(page, "После проверки проекта (фото)")
                
                if not project_exists:
                    logger.info(f"Создаем новый проект для {username}")
                    await self._create_new_project(page, username)
                else:
                    logger.info(f"Используем существующий чат для {username}")
                
                # Отправка фото с текстом
                response = await self._send_photo_and_get_response(page, photo_path, caption)
                
                # Проверяем наличие файлов и изображений в ответе
                downloaded_files = []
                
                # Сначала проверяем сгенерированные изображения
                images = await self._check_for_generated_images(page, log=True)
                if images:
                    download_path = f"./temp_downloads/{username}"
                    
                    for idx, share_button in enumerate(images):
                        filepath = await self._download_generated_image(page, share_button, download_path, idx)
                        if filepath:
                            downloaded_files.append(filepath)
                
                # Затем проверяем обычные файлы
                files = await self._check_for_files(page)
                if files:
                    logger.info(f"Обнаружено файлов для скачивания: {len(files)}")
                    download_path = f"./temp_downloads/{username}"
                    
                    for file_info in files:
                        filepath = await self._download_file(page, file_info, download_path)
                        if filepath:
                            downloaded_files.append(filepath)
                
                # Сохранение истории
                await self._save_conversation(user_project_path, f"[ФОТО] {caption}", response)
            
                return response, downloaded_files
                
            except Exception as e:
                logger.error(f"Ошибка при обработке фото (попытка {attempt + 1}/{max_retries}): {e}")
                
                # Если браузер упал, перезапускаем его
                if "Target crashed" in str(e) or "Target closed" in str(e):
                    logger.warning("Браузер упал, перезапускаем...")
                    try:
                        await self.stop()
                        await asyncio.sleep(2)
                        await self.start()
                        logger.info("Браузер перезапущен")
                        
                        # Если это не последняя попытка, пробуем снова
                        if attempt < max_retries - 1:
                            continue
                    except Exception as restart_error:
                        logger.error(f"Ошибка перезапуска браузера: {restart_error}")
                
                # Если это последняя попытка или другая ошибка
                if attempt == max_retries - 1:
                    return f"Произошла ошибка: {str(e)}", []
        
        return "Превышено количество попыток", []
    
    async def create_project_and_send_query(self, username: str, query: str) -> tuple:
        """Создание проекта для пользователя и отправка запроса в ChatGPT
        
        Returns:
            tuple: (response_text, list_of_downloaded_files)
        """
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Создание директории проекта пользователя
                user_project_path = Path(f"./user_projects/{username}")
                user_project_path.mkdir(parents=True, exist_ok=True)
                
                # Используем существующую страницу
                pages = self.browser.pages
                if pages:
                    page: Page = pages[0]
                else:
                    page: Page = await self.browser.new_page()
                    await page.goto('https://chatgpt.com/', wait_until='domcontentloaded', timeout=60000)
                    await asyncio.sleep(3)
                
                logger.info(f"Обработка запроса от {username}")
                
                # Обновление страницы только при первом запросе
                if self.first_request:
                    logger.info("Ожидание 5 секунд перед обновлением...")
                    await asyncio.sleep(5)
                    logger.info("Обновление страницы (F5)...")
                    await page.keyboard.press('F5')
                    logger.info("Ожидание полной загрузки страницы...")
                    
                    # Ждем исчезновения спиннера или появления поля ввода
                    for i in range(15):
                        await asyncio.sleep(1)
                        # Проверяем есть ли поле ввода
                        input_check = await page.query_selector('textarea, div[contenteditable="true"]')
                        if input_check:
                            logger.info(f"Страница загружена через {i+1} сек")
                            break
                        if i % 3 == 0:
                            logger.info(f"Ожидание загрузки... ({i+1} сек)")
                    
                    await self._save_debug_snapshot(page, "После обновления F5 (текст)")
                    self.first_request = False
                
                # Проверка и создание/открытие проекта (только если не в чате)
                project_exists = await self._check_and_open_project(page, username)
                await self._save_debug_snapshot(page, "После проверки проекта (текст)")
                
                if not project_exists:
                    # Создание нового проекта только если его нет
                    logger.info(f"Создаем новый проект для {username}")
                    await self._create_new_project(page, username)
                    await self._save_debug_snapshot(page, "После создания проекта")
                else:
                    logger.info(f"Используем существующий чат для {username}")
                
                # Отправка запроса
                response = await self._send_query_and_get_response(page, query)
                
                # Проверяем наличие файлов и изображений в ответе
                downloaded_files = []
                
                # Сначала проверяем сгенерированные изображения
                images = await self._check_for_generated_images(page, log=True)
                if images:
                    download_path = f"./temp_downloads/{username}"
                    
                    for idx, share_button in enumerate(images):
                        filepath = await self._download_generated_image(page, share_button, download_path, idx)
                        if filepath:
                            downloaded_files.append(filepath)
                
                # Затем проверяем обычные файлы
                files = await self._check_for_files(page)
                if files:
                    logger.info(f"Обнаружено файлов для скачивания: {len(files)}")
                    download_path = f"./temp_downloads/{username}"
                    
                    for file_info in files:
                        filepath = await self._download_file(page, file_info, download_path)
                        if filepath:
                            downloaded_files.append(filepath)
                
                # Сохранение истории
                await self._save_conversation(user_project_path, query, response)
            
                return response, downloaded_files
                
            except Exception as e:
                logger.error(f"Ошибка при обработке запроса (попытка {attempt + 1}/{max_retries}): {e}")
                
                # Если браузер упал, перезапускаем его
                if "Target crashed" in str(e) or "Target closed" in str(e):
                    logger.warning("Браузер упал, перезапускаем...")
                    try:
                        await self.stop()
                        await asyncio.sleep(2)
                        await self.start()
                        logger.info("Браузер перезапущен")
                        
                        # Если это не последняя попытка, пробуем снова
                        if attempt < max_retries - 1:
                            continue
                    except Exception as restart_error:
                        logger.error(f"Ошибка перезапуска браузера: {restart_error}")
                
                # Если это последняя попытка или другая ошибка
                if attempt == max_retries - 1:
                    return f"Произошла ошибка: {str(e)}", []
        
        return "Превышено количество попыток", []
    async def _check_and_solve_captcha(self, page: Page):
        """Проверка и автоматическое прохождение капчи"""
        try:
            logger.info("Ожидание загрузки капчи...")
            
            # Ждем появления текста капчи (до 5 секунд)
            captcha_text_found = False
            for i in range(5):
                await asyncio.sleep(1)
                captcha_text_found = await page.query_selector('text=Подтвердите, что вы человек')
                if captcha_text_found:
                    logger.info(f"Капча появилась через {i+1} сек")
                    break
            
            if not captcha_text_found:
                logger.info("Капча не найдена - страница загружена без проверки")
                return
            
            logger.info("Найдена Cloudflare капча! Ожидание загрузки чекбокса...")
            
            # Ждем появления чекбокса (он может грузиться дольше)
            checkbox = None
            checkbox_frame = page
            
            # Пробуем найти чекбокс в течение 10 секунд
            for attempt in range(10):
                await asyncio.sleep(1)
                
                # Способ 1: прямой поиск
                checkbox = await page.query_selector('input[type="checkbox"]')
                
                # Способ 2: через iframe (Cloudflare использует iframe)
                if not checkbox:
                    frames = page.frames
                    for frame in frames:
                        try:
                            checkbox = await frame.query_selector('input[type="checkbox"]')
                            if checkbox:
                                logger.info(f"Чекбокс найден во фрейме через {attempt+1} сек")
                                checkbox_frame = frame
                                break
                        except:
                            continue
                
                if checkbox:
                    break
                
                if attempt % 3 == 0:
                    logger.info(f"Ожидание чекбокса... ({attempt+1} сек)")
            
            if checkbox:
                logger.info("Чекбокс загружен! Выполняю клик с эмуляцией курсора...")
                
                # Небольшая пауза перед кликом
                await asyncio.sleep(1)
                
                # Получаем координаты элемента
                box = await checkbox.bounding_box()
                if box:
                    # Эмуляция естественного движения курсора
                    import random
                    
                    # Начальная точка (случайная)
                    start_x = random.randint(100, 300)
                    start_y = random.randint(100, 300)
                    
                    # Двигаем курсор к чекбоксу плавно
                    await checkbox_frame.mouse.move(start_x, start_y)
                    await asyncio.sleep(0.5)
                    
                    # Промежуточная точка
                    mid_x = (start_x + box['x'] + box['width'] / 2) / 2
                    mid_y = (start_y + box['y'] + box['height'] / 2) / 2
                    await checkbox_frame.mouse.move(mid_x, mid_y)
                    await asyncio.sleep(0.3)
                    
                    # Финальная позиция - центр чекбокса
                    final_x = box['x'] + box['width'] / 2
                    final_y = box['y'] + box['height'] / 2
                    await checkbox_frame.mouse.move(final_x, final_y)
                    await asyncio.sleep(0.4)
                    
                    # Клик
                    await checkbox_frame.mouse.click(final_x, final_y)
                    logger.info("✓ Клик по капче выполнен!")
                    
                    # Ждем обработки капчи
                    logger.info("Ожидание проверки Cloudflare...")
                    await asyncio.sleep(8)
                    
                    # Проверяем исчезла ли капча
                    captcha_still_there = await page.query_selector('text=Подтвердите, что вы человек')
                    if not captcha_still_there:
                        logger.info("✓ Капча успешно пройдена!")
                    else:
                        logger.warning("⚠ Капча все еще отображается, возможно требуется ручное вмешательство")
                else:
                    logger.error("Не удалось получить координаты чекбокса")
            else:
                logger.warning("⚠ Чекбокс не найден за 10 секунд, возможно требуется ручное прохождение")
            
        except Exception as e:
            logger.error(f"Ошибка при проверке капчи: {e}", exc_info=True)
            # Продолжаем работу даже если не удалось обработать капчу
    
    async def _check_and_open_project(self, page: Page, username: str) -> bool:
        """Проверка существования и открытие проекта пользователя"""
        try:
            logger.info(f"Проверка проекта для {username}...")
            
            # Проверяем находимся ли мы уже в нужном проекте
            # Смотрим на URL - если там есть /g/ значит мы в чате
            current_url = page.url
            
            # Если уже в чате - проверяем что это чат ЭТОГО пользователя
            if '/g/' in current_url or '/c/' in current_url:
                # Проверяем совпадает ли текущий пользователь с тем, кто был до этого
                if self.current_user_id == username:
                    logger.info(f"Уже находимся в чате пользователя {username}, продолжаем использовать его")
                    return True
                else:
                    logger.info(f"Смена пользователя: {self.current_user_id} -> {username}. Переключаемся на новый чат...")
                    # Обновляем текущего пользователя
                    self.current_user_id = username
                    # НЕ возвращаем True, чтобы создать/открыть проект для нового пользователя
            else:
                # Если не в чате, обновляем текущего пользователя
                self.current_user_id = username
            
            # Ищем проект с именем пользователя в списке проектов
            await asyncio.sleep(2)
            
            # Пытаемся найти текст с именем пользователя в проектах
            project_elements = await page.query_selector_all('text=' + username)
            
            if project_elements:
                logger.info(f"Найден существующий проект для {username}, открываем...")
                # Кликаем на проект
                await project_elements[0].click()
                await asyncio.sleep(3)
                return True
            
            logger.info(f"Проект для {username} не найден, нужно создать")
            return False
            
        except Exception as e:
            logger.error(f"Ошибка проверки проекта: {e}")
            return False
    
    async def _create_new_project(self, page: Page, username: str):
        """Создание нового проекта в ChatGPT"""
        try:
            logger.info(f"Создание нового проекта для {username}...")
            
            # Ищем кнопку "Новый проект" по тексту
            new_project_selectors = [
                'text=Новый проект',
                'text=New project',
                '[class*="menu-item"]:has-text("Новый проект")',
                'div:has-text("Новый проект")'
            ]
            
            new_project_button = None
            for selector in new_project_selectors:
                try:
                    logger.info(f"Ищу кнопку создания проекта: `{selector}`")
                    new_project_button = await page.wait_for_selector(selector, timeout=5000)
                    if new_project_button:
                        logger.info("Кнопка 'Новый проект' найдена")
                        break
                except:
                    continue
            
            if not new_project_button:
                logger.warning("Кнопка 'Новый проект' не найдена, обновляю страницу...")
                await page.keyboard.press('F5')
                await asyncio.sleep(3)
                
                # Повторная попытка после обновления
                for selector in new_project_selectors:
                    try:
                        new_project_button = await page.wait_for_selector(selector, timeout=5000)
                        if new_project_button:
                            logger.info("Кнопка 'Новый проект' найдена после обновления")
                            break
                    except:
                        continue
                
                if not new_project_button:
                    logger.warning("Кнопка 'Новый проект' не найдена даже после обновления, продолжаем без создания проекта")
                    return
            
            # Кликаем на кнопку
            await new_project_button.click()
            await asyncio.sleep(2)
            
            # Ищем поле ввода имени проекта
            name_input_selectors = [
                'input[placeholder*="название"]',
                'input[placeholder*="name"]',
                'input[type="text"]',
                'input'
            ]
            
            name_input = None
            for selector in name_input_selectors:
                try:
                    name_input = await page.wait_for_selector(selector, timeout=3000)
                    if name_input:
                        logger.info(f"Поле ввода имени найдено: `{selector}`")
                        break
                except:
                    continue
            
            if name_input:
                # Вводим имя пользователя как название проекта
                await name_input.fill(username)
                await asyncio.sleep(1)
                
                # Ищем кнопку подтверждения (Создать/Create/OK)
                confirm_selectors = [
                    'button:has-text("Создать")',
                    'button:has-text("Create")',
                    'button:has-text("OK")',
                    'button[type="submit"]'
                ]
                
                for selector in confirm_selectors:
                    try:
                        confirm_button = await page.query_selector(selector)
                        if confirm_button:
                            await confirm_button.click()
                            logger.info(f"Проект '{username}' создан")
                            await asyncio.sleep(2)
                            break
                    except:
                        continue
            else:
                logger.warning("Поле ввода имени проекта не найдено")
                
        except Exception as e:
            logger.error(f"Ошибка создания проекта: {e}")
            # Продолжаем работу даже если не удалось создать проект
    

    async def _check_for_generated_images(self, page: Page, log: bool = False) -> list:
        """Проверка наличия сгенерированных изображений в ответе ChatGPT"""
        try:
            # Ищем кнопки "Поделиться" для изображений
            share_buttons = await page.query_selector_all('button[aria-label*="Поделиться этим изображением"]')
            
            if not share_buttons:
                # Пробуем альтернативные селекторы
                share_buttons = await page.query_selector_all('button[aria-label*="Share this image"]')
            
            # Логируем только если запрошено
            if log and len(share_buttons) > 0:
                logger.info(f"Найдено изображений для скачивания: {len(share_buttons)}")
            
            return share_buttons
            
        except Exception as e:
            logger.error(f"Ошибка проверки изображений: {e}")
            return []
    
    async def _check_for_files(self, page: Page) -> list:
        """Проверка наличия файлов в ответе ChatGPT"""
        try:
            # Ищем ссылки на скачивание файлов в последнем ответе
            file_links = []
            
            # Селекторы для ссылок на файлы
            file_selectors = [
                'a[download]',
                'a[href*="blob:"]',
                'a[href*="download"]',
                'button[aria-label*="Download"]',
                'button[aria-label*="Скачать"]'
            ]
            
            for selector in file_selectors:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    try:
                        href = await element.get_attribute('href')
                        download_name = await element.get_attribute('download')
                        
                        if href:
                            file_links.append({
                                'element': element,
                                'href': href,
                                'name': download_name or 'file'
                            })
                            logger.info(f"Найден файл: {download_name or href}")
                    except:
                        continue
            
            return file_links
        except Exception as e:
            logger.error(f"Ошибка проверки файлов: {e}")
            return []
    
    async def _download_generated_image(self, page: Page, share_button, download_path: str, index: int = 0) -> str:
        """Скачивание сгенерированного изображения через кнопку 'Поделиться'"""
        try:
            logger.info(f"Скачивание изображения #{index + 1}...")
            
            # Создаем директорию для загрузок
            os.makedirs(download_path, exist_ok=True)
            
            # Нажимаем кнопку "Поделиться"
            logger.info("Нажатие кнопки 'Поделиться'...")
            await share_button.click()
            await asyncio.sleep(2)
            
            # Ищем кнопку "Скачать" в появившемся окне
            download_button = None
            download_selectors = [
                'button:has-text("Скачать")',
                'button:has-text("Download")',
                'div.flex.items-center.justify-center svg[viewBox="0 0 20 20"]',  # SVG иконка скачивания
            ]
            
            for selector in download_selectors:
                try:
                    # Ждем появления кнопки скачивания
                    download_button = await page.wait_for_selector(selector, timeout=5000, state='visible')
                    if download_button:
                        logger.info(f"Найдена кнопка скачивания: {selector}")
                        break
                except:
                    continue
            
            if not download_button:
                # Пробуем найти по структуре (div с иконкой скачивания)
                logger.info("Поиск кнопки скачивания по структуре...")
                download_containers = await page.query_selector_all('div.flex.h-16.w-16.items-center.justify-center')
                
                for container in download_containers:
                    # Проверяем есть ли внутри SVG с path содержащим координаты иконки скачивания
                    svg = await container.query_selector('svg')
                    if svg:
                        # Это наша кнопка скачивания
                        download_button = container
                        logger.info("Найдена кнопка скачивания по структуре")
                        break
            
            if not download_button:
                logger.error("Не найдена кнопка скачивания в окне 'Поделиться'")
                # Закрываем окно (ESC)
                await page.keyboard.press('Escape')
                return None
            
            # Настраиваем обработчик скачивания с увеличенным таймаутом
            logger.info("Ожидание скачивания файла...")
            
            try:
                async with page.expect_download(timeout=180000) as download_info:  # 3 минуты таймаут
                    # Кликаем на кнопку скачивания
                    await download_button.click()
                    logger.info("Клик по кнопке скачивания выполнен, ожидание файла...")
                
                download = await download_info.value
                
                # Получаем имя файла
                filename = download.suggested_filename or f'generated_image_{index + 1}.png'
                filepath = os.path.join(download_path, filename)
                
                # Сохраняем файл
                logger.info(f"Сохранение файла: {filepath}")
                await download.save_as(filepath)
                logger.info(f"✓ Изображение успешно скачано: {filepath}")
                
                # Закрываем окно "Поделиться"
                await page.keyboard.press('Escape')
                await asyncio.sleep(1)
                
                return filepath
                
            except asyncio.TimeoutError:
                logger.error("Таймаут при ожидании скачивания изображения (3 минуты)")
                await page.keyboard.press('Escape')
                return None
                
        except Exception as e:
            logger.error(f"Ошибка скачивания изображения: {e}", exc_info=True)
            # Пытаемся закрыть окно в случае ошибки
            try:
                await page.keyboard.press('Escape')
            except:
                pass
            return None
    
    async def _download_file(self, page: Page, file_info: dict, download_path: str) -> str:
        """Скачивание файла из ChatGPT"""
        try:
            logger.info(f"Скачивание файла: {file_info['name']}")
            
            # Создаем директорию для загрузок
            os.makedirs(download_path, exist_ok=True)
            
            # Если это blob URL, скачиваем через JavaScript
            if 'blob:' in file_info['href']:
                logger.info("Скачивание blob файла через JavaScript...")
                
                # Получаем содержимое blob через JavaScript
                content = await page.evaluate('''
                    async (url) => {
                        const response = await fetch(url);
                        const blob = await response.blob();
                        const reader = new FileReader();
                        return new Promise((resolve) => {
                            reader.onloadend = () => resolve(reader.result);
                            reader.readAsDataURL(blob);
                        });
                    }
                ''', file_info['href'])
                
                # Декодируем base64
                import base64
                if content.startswith('data:'):
                    # Убираем префикс data:mime/type;base64,
                    content = content.split(',', 1)[1]
                
                file_data = base64.b64decode(content)
                
                # Сохраняем файл
                filename = file_info['name'] if file_info['name'] != 'file' else 'downloaded_file.txt'
                filepath = os.path.join(download_path, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(file_data)
                
                logger.info(f"Blob файл сохранен: {filepath}")
                return filepath
            
            else:
                # Обычное скачивание через expect_download
                logger.info("Скачивание файла через download API...")
                
                async with page.expect_download(timeout=30000) as download_info:
                    # Кликаем на элемент для скачивания
                    await file_info['element'].click()
                
                download = await download_info.value
                
                # Получаем имя файла
                filename = download.suggested_filename or file_info['name']
                filepath = os.path.join(download_path, filename)
                
                # Сохраняем файл
                await download.save_as(filepath)
                logger.info(f"Файл сохранен: {filepath}")
                
                return filepath
                
        except Exception as e:
            logger.error(f"Ошибка скачивания файла: {e}", exc_info=True)
            
            # Попытка альтернативного метода - скачивание через содержимое элемента
            try:
                logger.info("Попытка альтернативного метода скачивания...")
                
                # Получаем текстовое содержимое из предыдущего блока кода
                code_blocks = await page.query_selector_all('pre code, pre, code')
                
                if code_blocks:
                    # Берем последний блок кода
                    last_code = code_blocks[-1]
                    code_content = await last_code.inner_text()
                    
                    if code_content and len(code_content) > 10:
                        filename = file_info['name'] if file_info['name'] != 'file' else 'code_file.txt'
                        filepath = os.path.join(download_path, filename)
                        
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(code_content)
                        
                        logger.info(f"Файл сохранен альтернативным методом: {filepath}")
                        return filepath
                        
            except Exception as alt_error:
                logger.error(f"Альтернативный метод тоже не сработал: {alt_error}")
            
            return None

    async def _send_query_and_get_response(self, page: Page, query: str) -> str:
        """Отправка запроса и получение ответа"""
        try:
            logger.info("Поиск поля ввода...")
            
            # Ждем загрузки страницы
            await asyncio.sleep(3)
            await self._save_debug_snapshot(page, "Перед поиском поля ввода")
            
            query_to_send = query
            
            # Увеличенное время ожидания и несколько вариантов селекторов
            input_selectors = [
                '#prompt-textarea',
                'textarea[placeholder*="Message"]',
                'textarea[placeholder*="message"]',
                'textarea[id*="prompt"]',
                'textarea[data-id*="root"]',
                'div[contenteditable="true"]',
                'textarea'
            ]
            
            input_selector_found = None
            for selector in input_selectors:
                try:
                    logger.info(f"Пробую селектор: `{selector}`")
                    await page.wait_for_selector(selector, timeout=10000, state='visible')
                    # Проверяем что элемент действительно есть и видим
                    test_element = await page.query_selector(selector)
                    if test_element:
                        is_visible = await test_element.is_visible()
                        if is_visible:
                            input_selector_found = selector
                            logger.info(f"Найден видимый элемент ввода: `{selector}`")
                            break
                except Exception as e:
                    logger.debug(f"Селектор `{selector}` не подошел: {e}")
                    continue
            
            if not input_selector_found:
                logger.error("Не найдено поле ввода")
                
                # Сохраняем скриншот для отладки
                try:
                    os.makedirs('./debug', exist_ok=True)
                    
                    screenshot_path = f"./debug/screenshot.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    logger.info(f"Скриншот сохранен: {screenshot_path}")
                    
                    # Сохраняем HTML для анализа
                    html_content = await page.content()
                    with open('./debug/page.html', 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    logger.info("HTML страницы сохранен: ./debug/page.html")
                    
                    # Сохраняем URL
                    with open('./debug/info.txt', 'w', encoding='utf-8') as f:
                        f.write(f"URL: {page.url}\n")
                        f.write(f"Title: {await page.title()}\n")
                    logger.info("Информация сохранена: ./debug/info.txt")
                except Exception as e:
                    logger.error(f"Ошибка сохранения отладочной информации: {e}")
                
                # Проверяем URL - возможно редирект на логин
                current_url = page.url
                logger.error(f"Текущий URL: {current_url}")
                
                if 'auth' in current_url or 'login' in current_url:
                    return "Ошибка: требуется авторизация в ChatGPT. Профиль не авторизован."
                
                return "Ошибка: не найдено поле ввода. Проверьте debug_screenshot.png и debug_page.html"
            
            # Клик по полю (используем селектор, а не сохраненный элемент)
            await page.click(input_selector_found)
            await asyncio.sleep(0.5)
            
            # Вводим текст (зашифрованный или обычный)
            await page.fill(input_selector_found, query_to_send)
            await asyncio.sleep(0.5)
            
            logger.info("Отправка запроса...")
            # Отправка (Enter)
            await page.keyboard.press('Enter')
            
            # Ожидание начала генерации
            await asyncio.sleep(3)
            
            # Поиск ответа
            response_selector = 'div[data-message-author-role="assistant"]'
            
            logger.info("Ожидание ответа от ChatGPT...")
            
            previous_length = 0
            stable_count = 0
            has_images = False
            
            # Ждем появления и завершения генерации ответа
            for i in range(120):
                await asyncio.sleep(1)
                
                # Проверяем наличие изображений (кнопки "Поделиться")
                images = await self._check_for_generated_images(page)
                if images and not has_images:
                    logger.info(f"✓ Обнаружена генерация изображения!")
                    has_images = True
                
                responses = await page.query_selector_all(response_selector)
                if responses:
                    last_response = responses[-1]
                    response_text = await last_response.inner_text()
                    current_length = len(response_text)
                    
                    # Если есть изображение и текст не растёт - генерация завершена
                    if has_images and current_length == previous_length:
                        stable_count += 1
                        if stable_count >= 5:
                            logger.info(f"✓ Генерация изображения завершена. Текст: {current_length} символов")
                            return response_text if current_length > 0 else "Изображение создано"
                    # Если только текст без изображений
                    elif current_length > 10 and current_length == previous_length:
                        stable_count += 1
                        # Если длина не меняется 5 секунд подряд - генерация завершена
                        if stable_count >= 5:
                            logger.info(f"✓ Генерация завершена. Длина ответа: {current_length}")
                            return response_text
                    else:
                        stable_count = 0
                    
                    previous_length = current_length
                    
                    if i % 10 == 0 and i > 0:
                        img_count = len(images) if images else 0
                        logger.info(f"Генерация продолжается... (текст: {current_length} симв.{', изображение: да' if img_count > 0 else ''})")
            
            # Если вышли по таймауту, возвращаем что есть
            if has_images:
                logger.info("Таймаут, но изображение сгенерировано")
                responses = await page.query_selector_all(response_selector)
                if responses:
                    response_text = await responses[-1].inner_text()
                    return response_text if len(response_text) > 0 else "Изображение создано"
                return "Изображение создано"
            
            if previous_length > 10:
                logger.info(f"Таймаут, но есть ответ: {previous_length} символов")
                responses = await page.query_selector_all(response_selector)
                if responses:
                    response_text = await responses[-1].inner_text()
                    
                    # Проверяем наличие файлов
                    files = await self._check_for_files(page)
                    if files:
                        response_text += f"\n\n📎 Обнаружено файлов: {len(files)}"
                    
                    return response_text
            
            return "Не удалось получить ответ от ChatGPT (таймаут)"
            
        except Exception as e:
            logger.error(f"Ошибка отправки запроса: {e}", exc_info=True)
            return f"Ошибка получения ответа: {str(e)}"
    
    async def _send_photo_and_get_response(self, page: Page, photo_path: str, caption: str = "") -> str:
        """Отправка фото с текстом и получение ответа"""
        try:
            logger.info("Поиск кнопки загрузки файла...")
            
            # Ищем кнопку загрузки файла (скрепка/плюс)
            upload_button_selectors = [
                'button[aria-label*="Attach"]',
                'button[aria-label*="прикрепить"]',
                'input[type="file"]',
                '[data-testid="upload-button"]'
            ]
            
            file_input = None
            
            # Ищем input[type="file"] напрямую или через кнопку
            for selector in upload_button_selectors:
                try:
                    if 'input[type="file"]' in selector:
                        file_input = await page.query_selector(selector)
                        if file_input:
                            logger.info("Найден input для загрузки файла")
                            break
                    else:
                        # Пробуем найти кнопку и получить связанный input
                        button = await page.query_selector(selector)
                        if button:
                            # Ищем input рядом с кнопкой
                            file_input = await page.query_selector('input[type="file"]')
                            if file_input:
                                logger.info(f"Найдена кнопка загрузки: `{selector}`")
                                break
                except:
                    continue
            
            # Если не нашли, ищем любой input[type="file"]
            if not file_input:
                file_input = await page.query_selector('input[type="file"]')
            
            if not file_input:
                logger.error("Не найдена кнопка загрузки файла")
                return "Ошибка: не найдена кнопка загрузки файла в ChatGPT"
            
            # Загружаем файл
            logger.info(f"Загрузка файла: {photo_path}")
            await file_input.set_input_files(photo_path)
            await asyncio.sleep(2)
            
            # Если есть текст, добавляем его
            if caption:
                logger.info(f"Добавление текста к фото: {caption}")
                
                input_selectors = [
                    '#prompt-textarea',
                    'textarea[placeholder*="Message"]',
                    'textarea[id*="prompt"]',
                    'textarea'
                ]
                
                for selector in input_selectors:
                    try:
                        await page.wait_for_selector(selector, timeout=3000, state='attached')
                        await page.fill(selector, caption)
                        logger.info(f"Текст добавлен через селектор: `{selector}`")
                        break
                    except:
                        continue
                
                await asyncio.sleep(1)
            
            # Отправка
            logger.info("Отправка фото...")
            await page.keyboard.press('Enter')
            
            # Ожидание ответа (используем ту же логику что и для текста)
            await asyncio.sleep(3)
            
            response_selector = 'div[data-message-author-role="assistant"]'
            logger.info("Ожидание ответа от ChatGPT...")
            
            previous_length = 0
            stable_count = 0
            has_images = False
            
            for i in range(120):
                await asyncio.sleep(1)
                
                # Проверяем наличие изображений (кнопки "Поделиться")
                images = await self._check_for_generated_images(page)
                if images and not has_images:
                    logger.info(f"✓ Обнаружена генерация изображения!")
                    has_images = True
                
                responses = await page.query_selector_all(response_selector)
                if responses:
                    last_response = responses[-1]
                    response_text = await last_response.inner_text()
                    current_length = len(response_text)
                    
                    # Если есть изображение и текст не растёт - генерация завершена
                    if has_images and current_length == previous_length:
                        stable_count += 1
                        if stable_count >= 5:
                            logger.info(f"✓ Генерация изображения завершена. Текст: {current_length} символов")
                            return response_text if current_length > 0 else "Изображение создано"
                    # Если только текст без изображений
                    elif current_length > 10 and current_length == previous_length:
                        stable_count += 1
                        if stable_count >= 5:
                            logger.info(f"✓ Генерация завершена. Длина ответа: {current_length}")
                            return response_text
                    else:
                        stable_count = 0
                    
                    previous_length = current_length
                    
                    if i % 10 == 0 and i > 0:
                        img_count = len(images) if images else 0
                        logger.info(f"Генерация продолжается... (текст: {current_length} симв.{', изображение: да' if img_count > 0 else ''})")
            
            # Если вышли по таймауту, возвращаем что есть
            if has_images:
                logger.info("Таймаут, но изображение сгенерировано")
                responses = await page.query_selector_all(response_selector)
                if responses:
                    response_text = await responses[-1].inner_text()
                    return response_text if len(response_text) > 0 else "Изображение создано"
                return "Изображение создано"
            
            if previous_length > 10:
                logger.info(f"Таймаут, но есть ответ: {previous_length} символов")
                responses = await page.query_selector_all(response_selector)
                if responses:
                    return await responses[-1].inner_text()
            
            return "Не удалось получить ответ от ChatGPT (таймаут)"
            
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}", exc_info=True)
            return f"Ошибка отправки фото: {str(e)}"
    
    async def _save_conversation(self, project_path: Path, query: str, response: str):
        """Сохранение переписки в файл"""
        try:
            conversation_file = project_path / "conversation.txt"
            with open(conversation_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"Запрос: {query}\n")
                f.write(f"Ответ: {response}\n")
        except Exception as e:
            logger.error(f"Ошибка сохранения переписки: {e}")
    
    async def stop(self):
        """Остановка браузера"""
        try:
            if self.browser:
                logger.info("Закрытие браузера...")
                try:
                    await asyncio.wait_for(self.browser.close(), timeout=3.0)
                except asyncio.TimeoutError:
                    logger.warning("Таймаут при закрытии браузера")
                except Exception as e:
                    logger.error(f"Ошибка при закрытии браузера: {e}")
                finally:
                    self.browser = None
                    
            if self.playwright:
                logger.info("Остановка Playwright...")
                try:
                    await asyncio.wait_for(self.playwright.stop(), timeout=3.0)
                except asyncio.TimeoutError:
                    logger.warning("Таймаут при остановке Playwright")
                except Exception as e:
                    logger.error(f"Ошибка при остановке Playwright: {e}")
                finally:
                    self.playwright = None
                    
            logger.info("Браузер остановлен")
        except Exception as e:
            logger.error(f"Ошибка остановки браузера: {e}")
