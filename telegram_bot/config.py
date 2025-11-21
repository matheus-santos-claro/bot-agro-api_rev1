# telegram_bot/config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Configurações do Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN não configurado nas variáveis de ambiente")

# Configurações da API
API_BASE_URL = os.getenv("API_BASE_URL", "https://bot-agro-api-rev1.onrender.com")

# Configurações do banco
DATABASE_PATH = os.getenv("DATABASE_PATH", "telegram_bot.db")

# Configurações de backup
BACKUP_WEBHOOK_URL = os.getenv("BACKUP_WEBHOOK_URL")  # Opcional
BACKUP_INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", "2"))

# IDs de administradores (adicione seu ID do Telegram)
ADMIN_IDS = [
    int(os.getenv("ADMIN_TELEGRAM_ID", "0"))  # Substitua pelo seu ID
]

# Configurações de logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

print(f"✅ Configurações carregadas:")
print(f"   - API URL: {API_BASE_URL}")
print(f"   - Database: {DATABASE_PATH}")
print(f"   - Backup interval: {BACKUP_INTERVAL_HOURS}h")
print(f"   - Admins: {len(ADMIN_IDS)} configurados")
