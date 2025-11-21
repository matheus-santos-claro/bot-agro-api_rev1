# telegram_bot/config.py
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configurações do Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# URL da API - CORRIGIDA (sem underscore)
API_BASE_URL = os.getenv('API_BASE_URL', 'https://bot-agro-api-rev1.onrender.com')

# IDs dos administradores
ADMIN_IDS = [
    int(os.getenv('ADMIN_ID_1', '0')),  # Substitua pelo seu ID
]

# Configurações do banco
DATABASE_PATH = 'telegram_bot.db'
BACKUP_INTERVAL_HOURS = 2

# Configurações de backup - ADICIONADAS
BACKUP_WEBHOOK_URL = os.getenv('BACKUP_WEBHOOK_URL', '')  # URL opcional para webhook de backup
BACKUP_RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', '7'))  # Manter backups por 7 dias

# Configurações de logging
LOG_LEVEL = 'INFO'

# Configurações de rate limiting
MAX_REQUESTS_PER_MINUTE = int(os.getenv('MAX_REQUESTS_PER_MINUTE', '10'))
MAX_REQUESTS_PER_HOUR = int(os.getenv('MAX_REQUESTS_PER_HOUR', '100'))

# Configurações de cache
CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL_SECONDS', '300'))  # 5 minutos

# Configurações de timeout
API_TIMEOUT_SECONDS = int(os.getenv('API_TIMEOUT_SECONDS', '30'))
DATABASE_TIMEOUT_SECONDS = int(os.getenv('DATABASE_TIMEOUT_SECONDS', '10'))

# Configurações de desenvolvimento
DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
VERBOSE_LOGGING = os.getenv('VERBOSE_LOGGING', 'False').lower() == 'true'
