# telegram_bot/config.py
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configurações do Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# URL da API - CORRIGIDA (sem underscore)
API_BASE_URL = os.getenv('API_BASE_URL', 'https://bot-agro-api_rev1.onrender.com')

# IDs dos administradores
ADMIN_IDS = [
    int(os.getenv('ADMIN_ID_1', '0')),  # Substitua pelo seu ID
]

# Configurações do banco
DATABASE_PATH = 'telegram_bot.db'
BACKUP_INTERVAL_HOURS = 2

# Configurações de logging
LOG_LEVEL = 'INFO'
