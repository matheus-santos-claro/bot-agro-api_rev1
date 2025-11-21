# telegram_bot/config.py

import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Configurações do Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# URL da API
API_BASE_URL = os.getenv('API_BASE_URL', 'https://bot-agro-api_rev1.onrender.com')

# IDs dos administradores
ADMIN_IDS = [
    int(os.getenv('ADMIN_ID_1', '0')),  # Substitua pelo seu ID real no .env
]

# Configuração do banco de dados local
DATABASE_PATH = 'telegram_bot.db'
BACKUP_INTERVAL_HOURS = 2

# Configurações de logging
LOG_LEVEL = 'INFO'

# Configuração do Webhook de Backup
BACKUP_WEBHOOK_URL = os.getenv('BACKUP_WEBHOOK_URL')  # <------ ESTA LINHA FOI ADICIONADA

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN não definido nas variáveis de ambiente.")

if not BACKUP_WEBHOOK_URL:
    raise ValueError("BACKUP_WEBHOOK_URL não definido nas variáveis de ambiente.")

