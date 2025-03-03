import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# Токен бота
TOKEN = os.getenv("TOKEN")