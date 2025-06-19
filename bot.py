import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Константы
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

BBC_CATEGORIES = {
    'world': 'Мир 🌍',
    'politics': 'Политика 🏛',
    'technology': 'Технологии 💻',
    'business': 'Бизнес 💼',
    'science': 'Наука 🔬',
    'health': 'Здоровье 🏥'
}

# Категории
BBC_CATEGORY_URLS = {
    'world': 'https://www.bbc.com/news/world',
    'politics': 'https://www.bbc.com/news/politics',
    'technology': 'https://www.bbc.com/news/technology',
    'business': 'https://www.bbc.com/news/business',
    'science': 'https://www.bbc.com/news/science_and_environment',
    'health': 'https://www.bbc.com/news/health'
}


class BBCNewsParser:
    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(30)

    def get_news_by_category(self, category_url, limit=5):
        try:
            self.driver.get(category_url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='card-text-wrapper']"))
            )
            time.sleep(2)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            news_items = soup.find_all('div', {'data-testid': 'card-text-wrapper'})[:limit]

            result = []
            for item in news_items:
                title_tag = item.find('h2')
                link_tag = item.find_parent('a')
                time_tag = item.find_next('span', {'data-testid': 'card-metadata-tag'})

                if not title_tag or not link_tag:
                    continue

                title = title_tag.get_text(strip=True)
                link = 'https://www.bbc.com'  + link_tag['href']
                time_str = time_tag.get_text(strip=True) if time_tag else "Сейчас"

                result.append({
                    'title': title,
                    'link': link,
                    'time': time_str
                })

            return result
        except Exception as e:
            logger.error(f"Ошибка при загрузке новостей: {e}")
            return []
        finally:
            self.driver.delete_all_cookies()

    def close(self):
        self.driver.quit()


class BBCNewsBot:
    def __init__(self, token):
        self.bot = Bot(token=token)
        self.parser = BBCNewsParser()
        self.dp = Dispatcher()

        # Регистрация команд
        self.dp.message.register(self.cmd_start, Command(commands=['start']))
        self.dp.callback_query.register(self.handle_callback)

    async def cmd_start(self, message: Message):
        await message.answer(
            "🗞️ <b>Добро пожаловать в BBC News Bot!</b>\n\n"
            "Выберите интересующую вас категорию:\n"
            "🌍 Мир • 🏛 Политика • 💻 Технологии • 💼 Бизнес • 🔬 Наука • 🏥 Здоровье",
            parse_mode='HTML',
            reply_markup=self.get_main_menu_keyboard()
        )

    def get_main_menu_keyboard(self):
        buttons = [
            [InlineKeyboardButton(text=BBC_CATEGORIES[cat], callback_data=f"category_{cat}")]
            for cat in BBC_CATEGORIES
        ]
        buttons.append([
            InlineKeyboardButton(text="🔔 Подписаться", callback_data="subscribe"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh")
        ])
        buttons.append([
            InlineKeyboardButton(text="❓ Помощь", callback_data="help")
        ])
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    async def handle_callback(self, callback: CallbackQuery):
        data = callback.data

        if data.startswith("category_"):
            category_key = data.replace("category_", "")
            category_name = BBC_CATEGORIES.get(category_key, "Неизвестная категория")
            category_url = BBC_CATEGORY_URLS.get(category_key)

            if not category_url:
                await callback.message.edit_text("⚠️ Категория не найдена.")
                return

            await callback.message.edit_text(
                f"⏳ Загружаю последние новости в категории <b>{category_name}</b>...",
                parse_mode='HTML'
            )

            news_list = self.parser.get_news_by_category(category_url, limit=5)

            if not news_list:
                await callback.message.edit_text("⚠️ Новости не найдены.")
                return

            await callback.message.edit_text(
                f"🗞️ <b>Новости: {category_name}</b>",
                parse_mode='HTML'
            )

            for news in news_list:
                await callback.message.answer(
                    f"<b>{news['title']}</b>\n"
                    f"🕒 {news['time']}\n"
                    f"🔗 <a href='{news['link']}'>Читать на BBC</a>",
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
                await asyncio.sleep(1)

            await callback.message.answer(
                "📌 Выберите следующее действие:",
                reply_markup=self.get_main_menu_keyboard()
            )

        elif data == "subscribe":
            await callback.message.edit_text(
                "🔔 Вы подписались на обновления!\n"
                "Вы будете получать самые свежие новости.",
                reply_markup=self.get_main_menu_keyboard()
            )

        elif data == "refresh":
            await callback.message.edit_text(
                "🔄 Обновляю список новостей...",
                parse_mode='HTML'
            )
            await callback.message.edit_text(
                "📌 Выберите категорию или действие:",
                reply_markup=self.get_main_menu_keyboard()
            )

        elif data == "help":
            await callback.message.edit_text(
                "ℹ️ <b>Как пользоваться ботом:</b>\n\n"
                "• Нажмите на категорию, чтобы получить новости\n"
                "• Используйте «Подписаться», чтобы получать обновления\n"
                "• Нажмите «Обновить», чтобы вернуться к списку",
                parse_mode='HTML',
                reply_markup=self.get_main_menu_keyboard()
            )

    async def shutdown(self):
        self.parser.close()


async def main():
    bot = BBCNewsBot(TELEGRAM_TOKEN)
    try:
        me = await bot.bot.get_me()
        logger.info(f"Бот запущен: @{me.username}")
        await bot.dp.start_polling(bot.bot)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())