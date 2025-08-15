import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

load_dotenv(encoding='utf-8')

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан в .env")

_admin_id_str = os.getenv("ADMIN_ID")
ADMIN_ID = int(_admin_id_str) if (_admin_id_str and _admin_id_str.isdigit()) else None

INVITE_CODE = os.getenv("INVITE_CODE", "default123")

storage = MemoryStorage()
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=storage)
